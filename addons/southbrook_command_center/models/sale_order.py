# SPDX-License-Identifier: LGPL-3.0-only
"""``sale.order`` — Central Command hooks for two known workflow defects
(DELIVERABLE_6_WORKFLOW.md): the production-approval circular gate
(``approval_gate_stall``) and the silent no-BoM skip (``bom_skip``).

Phase-2, HIGHEST-risk file — it overrides ``write()`` (the hot path). Two
safety properties this file guarantees:
  1. ``super()`` runs FIRST in every override; every side effect is
     ``try/except``-wrapped and logged — a materialize/publish failure never
     rolls back the sale-order write.
  2. Kill-switch (``_cc_hooks_enabled()``): when off, every override is a
     pure pass-through. The ``write()`` override additionally does *zero*
     Central Command work unless ``force_production_release`` is in the vals,
     so the common-case write cost is one dict lookup.

Verified against ``addons/southbrook_mrp_pm/models/sale_order.py``:
production_approval_state, force_production_release, action_request/approve/
reject_production, action_send_to_production (silently continues on no-BoM
lines), _get_unapproved_manufacturing_lines. Detection is read-only and
reuses those methods; this file writes only to southbrook.command.exception.
"""
import logging

from odoo import models

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def _cc_on(self):
        return self.env["southbrook.command.exception"]._cc_hooks_enabled()

    # -- approval_gate_stall: open on request, resolve on approve/reject/force -
    def action_request_production(self):
        result = super().action_request_production()
        if not self._cc_on():
            return result
        for so in self:
            try:
                so._sb_cc_open_approval_gate_stall()
            except Exception:  # noqa: BLE001
                _logger.exception(
                    "Central Command materialize failed for approval_gate_stall "
                    "on sale.order %s — non-fatal", so.id,
                )
        return result

    def action_approve_production(self):
        result = super().action_approve_production()
        if self._cc_on():
            self._sb_cc_resolve_gate_each()
        return result

    def action_reject_production(self):
        result = super().action_reject_production()
        if self._cc_on():
            self._sb_cc_resolve_gate_each()
        return result

    def write(self, vals):
        result = super().write(vals)
        # Hot path: only act when a force-release is being written AND hooks on.
        if vals.get("force_production_release") and self._cc_on():
            self._sb_cc_resolve_gate_each()
        return result

    def _sb_cc_resolve_gate_each(self):
        for so in self:
            try:
                so._sb_cc_resolve_approval_gate_stall()
            except Exception:  # noqa: BLE001
                _logger.exception(
                    "Central Command resolve failed for approval_gate_stall "
                    "on sale.order %s — non-fatal", so.id,
                )

    # -- bom_skip: recompute after every Send-to-Production pass --------------
    def action_send_to_production(self):
        result = super().action_send_to_production()
        if not self._cc_on():
            return result
        try:
            self._sb_cc_materialize_bom_skip(result)
        except Exception:  # noqa: BLE001
            _logger.exception(
                "Central Command materialize failed for bom_skip on "
                "sale.order %s — non-fatal", self.id,
            )
        return result

    # -- helpers: read-only detection + upsert/resolve/publish ---------------
    def _sb_cc_owner_id(self):
        self.ensure_one()
        owner = self.user_id or self.create_uid
        return owner.id if owner else self.env.uid

    def _sb_cc_open_approval_gate_stall(self):
        self.ensure_one()
        owner_id = self._sb_cc_owner_id()
        unapproved = self._get_unapproved_manufacturing_lines()
        impact_summary = (
            "Order %s has %d line(s) requiring production approval but cannot "
            "be confirmed — approval gate is circular for this order (state=%s)."
            % (self.name, len(unapproved), self.production_approval_state)
        )[:280]
        why_text = (
            "production_approval_state=%s, state=%s, force_production_release=%s, "
            "%d unapproved manufacturing line(s): %s"
            % (self.production_approval_state, self.state,
               self.force_production_release, len(unapproved),
               ", ".join(unapproved.mapped("product_id.display_name")) or "(none)")
        )
        vals = {
            "severity": "high",
            "severity_rank": 1,
            "owner_id": owner_id,
            "sale_order_id": self.id,
            "company_id": self.company_id.id,
            "impact_summary": impact_summary,
            "recommended_action": (
                "Either (a) have a Sales Manager set Force Production Release "
                "to bypass for this one-off, or (b) if approval was already "
                "granted out-of-band, have an admin correct "
                "production_approval_state, then re-attempt Confirm."
            ),
            "why_text": why_text,
        }
        Exception = self.env["southbrook.command.exception"]
        exc = Exception._upsert_exception(
            "approval_gate_stall", "sale.order", self.id, vals, reactivate=True
        )
        exc._publish(
            "sb_cc_exceptions", "exception_upsert",
            {
                "exception_id": exc.id, "exception_type": "approval_gate_stall",
                "severity": vals["severity"], "severity_rank": vals["severity_rank"],
                "state": exc.state, "owner_id": owner_id, "mo_id": False,
                "task_id": False, "company_id": vals["company_id"],
                "write_date": exc.write_date.isoformat() if exc.write_date else None,
            },
        )

    def _sb_cc_resolve_approval_gate_stall(self):
        self.ensure_one()
        Exception = self.env["southbrook.command.exception"]
        exc = Exception._resolve_exception("approval_gate_stall", "sale.order", self.id)
        if exc:
            exc._publish(
                "sb_cc_exceptions", "exception_resolved",
                {
                    "exception_id": exc.id, "exception_type": "approval_gate_stall",
                    "state": exc.state, "sale_order_id": self.id,
                    "company_id": self.company_id.id,
                },
            )

    def _sb_cc_materialize_bom_skip(self, mos):
        self.ensure_one()
        manufacturable_lines = self.order_line.filtered(
            lambda l: l.product_id and not l.display_type
        )
        if not manufacturable_lines:
            return
        covered_line_ids = set(
            self.env["mrp.production"].sudo()
            .search([("sale_line_id", "in", manufacturable_lines.ids)])
            .mapped("sale_line_id").ids
        )
        skipped = manufacturable_lines.filtered(lambda l: l.id not in covered_line_ids)
        Exception = self.env["southbrook.command.exception"]
        if not skipped:
            exc = Exception._resolve_exception("bom_skip", "sale.order", self.id)
            if exc:
                exc._publish(
                    "sb_cc_exceptions", "exception_resolved",
                    {
                        "exception_id": exc.id, "exception_type": "bom_skip",
                        "state": exc.state, "sale_order_id": self.id,
                        "company_id": self.company_id.id,
                    },
                )
            return

        skipped_value = sum(skipped.mapped("price_subtotal"))
        pct_of_order = (
            100.0 * skipped_value / self.amount_total if self.amount_total else 0.0
        )
        severity = "critical" if pct_of_order >= 25.0 else "high"
        severity_rank = 0 if severity == "critical" else 1

        task = self.env["project.task"]
        if mos:
            task = task.sudo().search([("production_ids", "in", mos.ids)], limit=1)
        owner_id = task.pm_id.id if (task and task.pm_id) else (
            self.create_uid.id or self.env.uid)

        impact_summary = (
            "Order %s: %d line(s) skipped at Send-to-Production — no BoM "
            "resolved, no MO created, no error shown. Skipped value: $%.2f "
            "(%.1f%% of order)."
            % (self.name, len(skipped), skipped_value, pct_of_order)
        )[:280]
        why_text = (
            "action_send_to_production found no resolvable mrp.bom for %d "
            "line(s) (product_ids: %s)."
            % (len(skipped),
               ", ".join(str(pid) for pid in skipped.mapped("product_id").ids))
        )
        vals = {
            "severity": severity,
            "severity_rank": severity_rank,
            "owner_id": owner_id,
            "mo_id": mos[:1].id if mos else False,
            "task_id": task.id if task else False,
            "sale_order_id": self.id,
            "company_id": self.company_id.id,
            "impact_summary": impact_summary,
            "recommended_action": (
                "Add or fix the mrp.bom for: %s, then re-run Send to Production "
                "(idempotent — only creates MOs for previously-skipped lines)."
                % ", ".join(skipped.mapped("product_id.display_name"))
            ),
            "why_text": why_text,
        }
        exc = Exception._upsert_exception(
            "bom_skip", "sale.order", self.id, vals, reactivate=True
        )
        exc._publish(
            "sb_cc_exceptions", "exception_upsert",
            {
                "exception_id": exc.id, "exception_type": "bom_skip",
                "severity": severity, "severity_rank": severity_rank,
                "state": exc.state, "owner_id": owner_id, "mo_id": vals["mo_id"],
                "task_id": vals["task_id"], "company_id": vals["company_id"],
                "write_date": exc.write_date.isoformat() if exc.write_date else None,
            },
        )
