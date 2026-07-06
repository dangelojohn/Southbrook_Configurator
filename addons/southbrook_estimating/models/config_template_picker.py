# SPDX-License-Identifier: LGPL-3.0-only
"""C1 fix (2026-07-06): a plain template picker for "Configure Product".

Root cause (reproduced/confirmed via odoo-shell on the dev stack): the OCA
header-button flow, `sale.order.action_config_start`, opened the
`product.configurator` wizard on a **virtual (unsaved) record**
(`res_id: None`). On that record `product_tmpl_id` is a *delegated*
(`_inherits` product.config.session) field, and the Odoo 19 web client
renders it disabled/greyed — the user cannot commit a template, and clicking
Next hits the create() guard ("Please select a Configurable Template").

We cannot pre-create the wizard template-less: product.config.session's
`product_tmpl_id` is NOT NULL, so an _inherits parent can't exist without a
template — the picker step is inherently a virtual record and can't be fixed
by "persist it first".

Fix: don't use the configurator's own virtual-record picker at all. Open a
tiny transient whose `product_tmpl_id` is a **plain** Many2one (no
delegation → nothing to grey), and on confirm hand off to
`product.template.create_config_wizard(...)` — the exact ORM path every OTHER
entry point (per-line Reconfigure, product.template.configure_product) uses
successfully, and which is proven end-to-end (persisted wizard, session
created, action_next_step advances to a real step). The configurator then
opens on a REAL record with the template pre-set (product_tmpl_id_readonly),
so the delegated-field-on-virtual-record problem cannot occur.
"""
from odoo import api, fields, models
from odoo.exceptions import UserError


class SouthbrookConfigTemplatePicker(models.TransientModel):
    _name = "southbrook.config.template.picker"
    _description = "Configure Product — Template Picker"

    order_id = fields.Many2one(
        "sale.order", required=True, ondelete="cascade",
        help="Order the newly configured product line will be added to.",
    )
    product_tmpl_id = fields.Many2one(
        "product.template",
        string="Configurable Template",
        required=True,
        domain=[("config_ok", "=", True)],
        help="Pick the cabinet template to configure. Only configurable "
             "templates are listed.",
    )

    def action_configure(self):
        """Hand off to the proven create_config_wizard path on the chosen
        template, attaching the resulting configuration to the order."""
        self.ensure_one()
        if not self.product_tmpl_id:
            raise UserError(self.env._(
                "Please select a Configurable Template before continuing."))
        return self.product_tmpl_id.with_context(
            product_tmpl_id_readonly=True,
        ).create_config_wizard(
            model_name="product.configurator.sale",
            extra_vals={"order_id": self.order_id.id},
            click_next=False,
        )

    @api.model
    def action_open_for_order(self, order_id):
        """Return the act_window that opens this picker as a dialog for the
        given order. Called by sale.order.action_config_start."""
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Configure Product"),
            "res_model": "southbrook.config.template.picker",
            "view_mode": "form",
            "target": "new",
            "context": {"default_order_id": order_id},
        }
