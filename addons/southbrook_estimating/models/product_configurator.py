# SPDX-License-Identifier: LGPL-3.0-only
"""Wizard polish: rename last-step Next button to Confirm.

End-to-end test 2026-06-22 (Bug #4): the OCA configurator wizard's
final step still showed "Next" — confusing because the click actually
materialised the variant and closed the wizard. Customers expected
"Confirm" or "Done" on the terminal step.

Fix: add a computed `is_last_step` to the wizard, then the view layer
swaps the Next button for a Confirm button when true. Both buttons
call the same `action_next_step` method — the OCA implementation
already routes to `action_config_done()` when no next step exists.

The compute is deliberately defensive: it returns False whenever the
wizard isn't on a real step yet (template-picker state, no session,
no template), so first-load never lights up the Confirm button. Any
unexpected error → False (Next stays visible) to avoid masking the
forward path on a broken state.
"""
import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class ProductConfigurator(models.TransientModel):
    _inherit = "product.configurator"

    is_last_step = fields.Boolean(
        compute="_compute_is_last_step",
        help="True when the wizard is on its terminal configuration "
             "step. Drives the Confirm-vs-Next button swap.",
    )

    @api.depends("state", "value_ids", "product_tmpl_id",
                 "config_session_id")
    def _compute_is_last_step(self):
        for wiz in self:
            wiz.is_last_step = False
            session = wiz.config_session_id
            tmpl = wiz.product_tmpl_id
            if not session or not tmpl or wiz.state == "select":
                continue
            try:
                adj = session.get_adjacent_steps(
                    value_ids=session.value_ids.ids,
                )
                # Empty dict = template has no config_step_lines
                # (one-page wizard) → first action_next_step click IS
                # the confirm. Otherwise next_step is the recordset
                # or None.
                if not adj:
                    wiz.is_last_step = True
                else:
                    wiz.is_last_step = not adj.get("next_step")
            except Exception:
                wiz.is_last_step = False

    # ------------------------------------------------------------------
    # Hide single-value attribute lines that have a backfilled default_val.
    #
    # Phase 3 follow-up (2026-06-24): the wizard renders one field per
    # attribute_line, including lines where the template carries exactly
    # one value (e.g. attr_family on every Q8 template carries one Family
    # value). The user has to click through these no-choice pickers.
    #
    # _backfill_single_value_attribute_defaults (see __init__.py) sets
    # default_val on those lines so OCA's session.create() auto-applies
    # the value to value_ids. This override post-processes the wizard
    # view arch and adds invisible="1" to the matching fields — BUT only
    # when default_val is set, so a line that never got backfilled stays
    # visible and the user is never stranded with no way to submit.
    # ------------------------------------------------------------------
    @api.model
    def add_dynamic_fields(self, res, dynamic_fields, wiz):
        mod_view = super().add_dynamic_fields(res, dynamic_fields, wiz)
        if not wiz.product_tmpl_id:
            return mod_view
        field_prefix = self._prefixes.get("field_prefix")
        AttrLine = self.env["product.template.attribute.line"].sudo()
        # Build attribute_id -> attr_line map once per render.
        line_by_attr = {
            line.attribute_id.id: line
            for line in wiz.product_tmpl_id.attribute_line_ids
        }
        for field in mod_view.xpath(f"//field[starts-with(@name, '{field_prefix}')]"):
            name = field.get("name") or ""
            try:
                attr_id = int(name[len(field_prefix):])
            except (ValueError, TypeError):
                continue
            line = line_by_attr.get(attr_id)
            if not line:
                continue
            if len(line.value_ids) == 1 and line.default_val:
                # Both safe-to-hide gates met.
                field.set("invisible", "1")
        return mod_view
