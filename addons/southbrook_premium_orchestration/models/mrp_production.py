# SPDX-License-Identifier: LGPL-3.0-only
"""Hook MO lifecycle transitions into the Kitchen Ops activity feed,
and gate MO confirm on component availability (SAMI PRD MO-08).

DESIGN:
  - action_confirm override blocks confirm when components can't be
    fully reserved. Two escape hatches (system parameter + context
    flag) so unusual flows can override.
  - button_mark_done override emits the mo_done ops event for the
    activity feed.
"""
from odoo import _, models
from odoo.exceptions import UserError


class MrpProduction(models.Model):
    _inherit = "mrp.production"

    def action_confirm(self):
        """SAMI PRD MO-08 — block confirm when components are short.

        Standard Odoo lets an MO confirm even if components aren't
        reserved; the surprise lands on the shop floor. This override
        runs action_assign immediately after the parent confirm and
        raises UserError listing every move that's still 'confirmed'
        or 'partially_available' (i.e. not fully reserved).

        Escape hatches:
          - ir.config_parameter `southbrook.mo_availability_gate.enabled`
            set to "0" disables the gate globally (manager override
            for unusual circumstances like back-fill from offsite).
          - context flag `bypass_availability_gate=True` per-call,
            used by system-driven flows like the order-analytics cron
            backfill where MOs are being recreated retroactively.

        Raising UserError after super().action_confirm() relies on
        the surrounding transaction rollback — the MO falls back to
        draft state, no half-confirmed MOs.
        """
        Param = self.env["ir.config_parameter"].sudo()
        gate_on = Param.get_param(
            "southbrook.mo_availability_gate.enabled", "1") == "1"
        bypass = self.env.context.get("bypass_availability_gate", False)
        result = super().action_confirm()
        if not gate_on or bypass:
            return result
        # action_assign tries to reserve every component. State after:
        #   'assigned'              — fully reserved (good)
        #   'partially_available'   — partial — still a short
        #   'confirmed'             — no reservation made at all
        #   'done' / 'cancel'       — terminal (ignored)
        self.action_assign()
        gaps = []
        for mo in self:
            for move in mo.move_raw_ids:
                if move.state in ("done", "cancel", "draft", "assigned"):
                    continue
                gaps.append({
                    "mo": mo.name,
                    "product": move.product_id.display_name,
                    "demand": move.product_uom_qty,
                    "uom": move.product_uom.name,
                    "state": move.state,
                })
        if gaps:
            lines = "\n".join(
                f"  • {g['mo']}: {g['product']} — "
                f"{g['demand']:.2f} {g['uom']} needed (move state: {g['state']})"
                for g in gaps
            )
            raise UserError(_(
                "Cannot confirm — %(n)d component move(s) cannot be "
                "fully reserved:\n\n%(lines)s\n\n"
                "Bring stock in (receipt, internal transfer, scrap "
                "reversal) and retry. Manager override: set the system "
                "parameter 'southbrook.mo_availability_gate.enabled' "
                "to '0', or pass context bypass_availability_gate=True.",
                n=len(gaps), lines=lines,
            ))
        return result

    def button_mark_done(self):
        result = super().button_mark_done()
        for mo in self:
            try:
                self.env["southbrook.ops.event"].emit(
                    "mo_done",
                    f"MO {mo.name} marked done"
                    + (f" (for {mo.product_id.name})"
                       if mo.product_id else ""),
                    res_model="mrp.production",
                    res_id=mo.id,
                    severity="info",
                )
            except Exception:  # noqa: BLE001
                pass
        return result
