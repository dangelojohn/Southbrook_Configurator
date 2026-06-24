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
from odoo import api, fields, models


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
