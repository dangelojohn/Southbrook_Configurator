# SPDX-License-Identifier: LGPL-3.0-only
"""mrp.workorder extension — tool readiness gate.

The readiness check enumerates:

 1. the operation_tool_requirement_ids for this workorder's operation
    (most-specific rule first), and
 2. the workcenter_tool_requirement_ids for the workorder's work center
    (catch-all fallback for operations that didn't declare their own).

For each requirement it asks: how many AVAILABLE assets exist in the
serving tool cribs (or anywhere in the workcenter when no crib filter)
that satisfy this requirement? If less than ``quantity`` and the
requirement is mandatory, the readiness state goes ``blocked``. If
all mandatory requirements are met but some non-mandatory ones are
under-stocked, the state is ``warning``. Otherwise ``ready``.

Availability = ``southbrook.tool.asset.is_available`` plus
``lifecycle_state not in ('needs_sharpening','needs_calibration','needs_cleaning')``
because those states still pass ``is_available`` (the asset has not
been pulled) but they are not work-order-ready.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError


READINESS_STATE_SELECTION = [
    ("not_checked", "Not Checked"),
    ("ready", "Ready"),
    ("warning", "Ready with Warnings"),
    ("blocked", "Blocked"),
]


class MrpWorkorder(models.Model):
    _inherit = "mrp.workorder"

    southbrook_tool_readiness_state = fields.Selection(
        READINESS_STATE_SELECTION,
        string="Tool Readiness",
        default="not_checked",
        readonly=True,
        copy=False,
    )
    southbrook_tool_readiness_msg = fields.Text(
        string="Tool Readiness Detail",
        readonly=True,
        copy=False,
    )

    # ──────────────────────────────────────────────────────────────────
    # Readiness check
    # ──────────────────────────────────────────────────────────────────
    def _collect_tool_requirements(self):
        """Return (operation_reqs, workcenter_reqs) for self."""
        self.ensure_one()
        op_reqs = self.operation_id.southbrook_tool_requirement_ids \
            if self.operation_id else self.env[
                "southbrook.operation.tool.requirement"
            ]
        wc_reqs = self.workcenter_id.southbrook_tool_requirement_ids \
            if self.workcenter_id else self.env[
                "southbrook.workcenter.tool.requirement"
            ]
        return op_reqs, wc_reqs

    def _available_asset_count(self, category, product, workcenter):
        """How many available assets satisfy this requirement?"""
        Asset = self.env["southbrook.tool.asset"]
        domain = [("is_available", "=", True)]
        # Pull out states that pass is_available but aren't work-ready
        domain.append(
            ("lifecycle_state", "not in", (
                "needs_sharpening", "needs_calibration", "needs_cleaning",
            )),
        )
        if product:
            domain.append(("product_id", "=", product.id))
        elif category:
            # accept any descendant of the requirement's category
            cat_ids = (
                category | category.child_ids
            ).ids if hasattr(category, "child_ids") else [category.id]
            domain.append(("tool_category_id", "in", cat_ids))
        if workcenter:
            domain.append("|")
            domain.append(("workcenter_id", "=", workcenter.id))
            domain.append(("workcenter_id", "=", False))
        return Asset.search_count(domain)

    def action_check_tool_readiness(self):
        """Recompute readiness for the selected work orders."""
        for wo in self:
            op_reqs, wc_reqs = wo._collect_tool_requirements()
            problems = []
            warnings = []
            all_reqs = [(r, "op") for r in op_reqs] + \
                       [(r, "wc") for r in wc_reqs]
            for req, source in all_reqs:
                have = wo._available_asset_count(
                    req.tool_category_id,
                    req.product_id,
                    wo.workcenter_id,
                )
                if have < req.quantity:
                    target = (
                        req.product_id.display_name
                        or req.tool_category_id.complete_name
                        or "?"
                    )
                    line = "%s — need %d, have %d" % (
                        target, req.quantity, have,
                    )
                    if req.is_mandatory:
                        problems.append(line)
                    else:
                        warnings.append(line)
            if problems:
                state = "blocked"
                msg = _("Blocked:\n") + "\n".join(problems)
                if warnings:
                    msg += _("\n\nAlso warning:\n") + "\n".join(warnings)
            elif warnings:
                state = "warning"
                msg = _("Warnings:\n") + "\n".join(warnings)
            else:
                state = "ready"
                msg = _("All required tools are available.")
            wo.southbrook_tool_readiness_state = state
            wo.southbrook_tool_readiness_msg = msg

    # Gate the workorder start when blocked.
    def button_start(self):
        for wo in self:
            if wo.southbrook_tool_readiness_state == "blocked":
                raise UserError(_(
                    "Cannot start work order %s — tool readiness is "
                    "BLOCKED:\n\n%s"
                ) % (wo.display_name, wo.southbrook_tool_readiness_msg))
        return super().button_start()
