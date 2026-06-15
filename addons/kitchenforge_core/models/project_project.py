# SPDX-License-Identifier: LGPL-3.0-only
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class Project(models.Model):
    _inherit = "project.project"

    is_template = fields.Boolean(
        string="Is Template",
        index=True,
        default=False,
        help="A reusable project shape (Full Kitchen, Partial Reno, etc.) "
             "instantiated by the KitchenForge wizard. Templates do not appear "
             "in the active-project list.",
    )
    kitchenforge_kind = fields.Selection(
        [
            ("full_kitchen", "Full Kitchen"),
            ("partial_reno", "Partial Renovation"),
            ("single_custom", "Single Custom Cabinet"),
            ("vanity", "Vanity"),
            ("commercial", "Commercial"),
        ],
        string="Template Kind",
    )
    template_so_product_id = fields.Many2one(
        "product.product",
        string="Template Service Product",
        domain="[('type','=','service')]",
        help="Service product representing the project as a single SO line "
             "(used for fixed-price or T&M kitchens). Optional.",
    )
    default_cabinet_zone_ids = fields.One2many(
        "kitchenforge.template.line",
        "template_project_id",
        string="Default Cabinet Zones",
        copy=True,
        help="Cabinet zones pre-populated when this template is instantiated.",
    )
    cut_spec_id = fields.Many2one(
        "southbrook.cut.spec",
        string="Locked Cut Spec",
        help="Snapshot of the active shop cut-spec at instantiation time. "
             "In-flight projects are immune to subsequent ECO changes.",
    )
    bom_version_lock = fields.Integer(
        string="BoM Version Lock",
        help="Snapshot of the active template BoM version at instantiation.",
    )
    instantiated_from_template_id = fields.Many2one(
        "project.project",
        string="Instantiated From",
        domain="[('is_template','=',True)]",
        index=True,
        readonly=True,
    )
    sale_order_id = fields.Many2one(
        "sale.order",
        string="Sale Order",
        index=True,
        readonly=True,
        help="Sale order created alongside this project at instantiation.",
    )

    @api.model
    def _kitchenforge_active_cut_spec(self):
        """Return the active shop cut-spec to snapshot onto a new project."""
        return self.env["southbrook.cut.spec"].search(
            [("active", "=", True)], limit=1, order="id desc")

    def kitchenforge_instantiate(self, partner, dims=None, target_date=None,
                                  origin_channel="backend"):
        """Atomic: copy template -> Project, create draft SO with
        pre-populated configurator lines, link them. Used by the wizard,
        the REST API, and the AI-agent toolkit. Returns the new Project."""
        self.ensure_one()
        if not self.is_template:
            raise UserError(_(
                "Project %s is not a template; cannot instantiate.") % self.name)
        dims = dims or {}

        cut_spec = self._kitchenforge_active_cut_spec()
        proj_vals = {
            "name": _("Job: %s — %s") % (partner.name, self.name),
            "is_template": False,
            "partner_id": partner.id,
            "instantiated_from_template_id": self.id,
            "cut_spec_id": cut_spec.id if cut_spec else False,
        }
        new_proj = self.copy(default=proj_vals)

        SO = self.env["sale.order"]
        so_lines = []
        for tline in self.default_cabinet_zone_ids:
            so_lines.append((0, 0, tline._to_so_line_vals(dims=dims)))

        so_vals = {
            "partner_id": partner.id,
            "origin": new_proj.name,
            "kitchenforge_project_id": new_proj.id,
            "kitchenforge_template_id": self.id,
            "order_line": so_lines,
        }
        if target_date:
            so_vals["commitment_date"] = target_date
        so = SO.create(so_vals)
        new_proj.sale_order_id = so.id
        new_proj.message_post(body=_(
            "Instantiated from template <b>%s</b> via %s. "
            "Sale Order: <a href='#' data-oe-model='sale.order' "
            "data-oe-id='%d'>%s</a>") % (self.name, origin_channel, so.id, so.name))
        return new_proj
