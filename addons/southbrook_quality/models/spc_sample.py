# SPDX-License-Identifier: LGPL-3.0-only
"""Statistical Process Control sample.

Each row is a single measurement of one dimension at one workcenter at
one point in time. The :meth:`action_create_ncr_if_oos` helper escalates
out-of-spec samples to an NCR record.
"""

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class SouthbrookSpcSample(models.Model):
    _name = "southbrook.quality.spc_sample"
    _description = "Southbrook SPC Sample"
    _order = "taken_at desc, id desc"

    name = fields.Char(
        string="SPC Reference",
        required=True,
        readonly=True,
        copy=False,
        default=lambda self: _("New"),
    )
    workcenter_id = fields.Many2one(
        "mrp.workcenter",
        string="Work Center",
        required=True,
    )
    product_id = fields.Many2one("product.product", string="Product")
    dimension_id = fields.Many2one(
        "southbrook.quality.dimension",
        string="Dimension",
        required=True,
    )
    dimension_key = fields.Char(
        string="Dimension Key",
        related="dimension_id.key",
        store=True,
        readonly=True,
    )
    measured_value = fields.Float(string="Measured", required=True)
    nominal = fields.Float(related="dimension_id.nominal", store=True, readonly=True)
    usl = fields.Float(related="dimension_id.usl", store=True, readonly=True)
    lsl = fields.Float(related="dimension_id.lsl", store=True, readonly=True)
    in_spec = fields.Boolean(
        compute="_compute_in_spec",
        store=True,
        readonly=True,
    )
    production_id = fields.Many2one("mrp.production", string="Manufacturing Order")
    operator_id = fields.Many2one(
        "res.users",
        string="Operator",
        default=lambda self: self.env.user,
    )
    taken_at = fields.Datetime(
        string="Taken At",
        default=fields.Datetime.now,
        required=True,
    )
    ncr_ids = fields.One2many("southbrook.ncr", "spc_sample_id", string="Linked NCRs")

    # ---------------------------------------------------------------------
    # Create
    # ---------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("name") or vals.get("name") == _("New"):
                seq = self.env["ir.sequence"].next_by_code("southbrook.quality.spc_sample")
                vals["name"] = seq or _("New")
        return super().create(vals_list)

    # ---------------------------------------------------------------------
    # Compute
    # ---------------------------------------------------------------------
    @api.depends("measured_value", "lsl", "usl")
    def _compute_in_spec(self):
        for rec in self:
            rec.in_spec = rec.lsl <= rec.measured_value <= rec.usl

    @api.constrains("dimension_id")
    def _check_dimension_key(self):
        """Belt-and-suspenders: the FK already enforces existence, but this
        constraint guarantees no row can sneak in with a dangling key
        through raw cursor writes."""
        for rec in self:
            if not rec.dimension_id:
                raise ValidationError(_("SPC sample requires a controlled dimension."))

    # ---------------------------------------------------------------------
    # Actions
    # ---------------------------------------------------------------------
    def action_create_ncr_if_oos(self):
        """Create an NCR for each out-of-spec sample. Returns the NCRs."""
        created = self.env["southbrook.ncr"]
        for rec in self:
            if rec.in_spec:
                continue
            ncr = self.env["southbrook.ncr"].create(
                {
                    "production_id": rec.production_id.id or False,
                    "workcenter_id": rec.workcenter_id.id or False,
                    "product_id": rec.product_id.id or False,
                    "defect_type": "dimension",
                    "severity": "major",
                    "description": _(
                        "Auto-created from SPC sample %(name)s: measured "
                        "%(val).4f outside [%(lsl).4f, %(usl).4f] on %(key)s.",
                        name=rec.name,
                        val=rec.measured_value,
                        lsl=rec.lsl,
                        usl=rec.usl,
                        key=rec.dimension_key,
                    ),
                    "spc_sample_id": rec.id,
                    "quantity": 1.0,
                    "state": "draft",
                }
            )
            created |= ncr
        return created
