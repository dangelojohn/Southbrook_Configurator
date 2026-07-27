# SPDX-License-Identifier: LGPL-3.0-only
"""Workcenter capacity, the daily load table, and warehouse floating times.

CE-native replacement for the corresponding parts of the proprietary
``mrp_shop_floor_control``. Field and method names are preserved exactly
where another module consumes them — see the module README for the audited
contract.
"""

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class StockWarehouse(models.Model):
    _inherit = "stock.warehouse"

    calendar_id = fields.Many2one(
        "resource.calendar", "Working Schedule",
        help="Calendar used to walk working hours when scheduling work "
             "orders in this warehouse. Falls back to the company calendar.")


class MrpFloatingTimes(models.Model):
    _name = "mrp.floating.times"
    _description = "Manufacturing Floating Times"
    _rec_name = "warehouse_id"

    warehouse_id = fields.Many2one(
        "stock.warehouse", "Warehouse", required=True, ondelete="cascade")
    company_id = fields.Many2one(
        related="warehouse_id.company_id", store=True, index=True)
    mrp_release_time = fields.Float("Release Time (Hours)", default=1.0)
    mrp_ftbp_time = fields.Float(
        "Floating Time Before Production (Hours)", default=1.0)
    mrp_ftap_time = fields.Float(
        "Floating Time After Production (Hours)", default=1.0)

    _warehouse_uniq = models.Constraint(
        "unique(warehouse_id)",
        "Floating times are already configured for this warehouse.")

    @api.model
    def _get_for_warehouse(self, warehouse):
        """Return the row for *warehouse*, creating a default if absent.

        The vendor implementation raised a UserError when the row was
        missing, which turned a first-time scheduling attempt into a dead
        end with no way forward from the UI. Defaults of 1.0 hour match what
        that module seeded anyway, so auto-creating is both compatible and
        less hostile.
        """
        if not warehouse:
            raise UserError(_(
                "Cannot resolve floating times: the manufacturing order has "
                "no warehouse."))
        rec = self.search([("warehouse_id", "=", warehouse.id)], limit=1)
        if not rec:
            rec = self.create({"warehouse_id": warehouse.id})
        return rec


class MrpWorkcenter(models.Model):
    _inherit = "mrp.workcenter"

    def _sfc_capacity(self, product=None):
        """Flat capacity scalar for this workcenter.

        Consumed by the costing layer and the finite-capacity scheduling
        engine, which call it both with and without a product — so the
        signature and the scalar return type are part of the contract.

        Odoo 19 removed the scalar ``mrp.workcenter.capacity`` field;
        capacity is now per-product through ``capacity_ids``. Core
        ``_get_capacity(product, unit, default_capacity=1)`` returns a
        **tuple** of ``(capacity, time_start, time_stop)``, so the first
        element is taken. Calling it with one argument raises TypeError, and
        treating the tuple as a number silently poisons every downstream
        cost and duration — both mistakes were made and caught here.
        """
        self.ensure_one()
        if product:
            return self._get_capacity(
                product, product.uom_id, default_capacity=1)[0] or 1.0
        return 1.0

    def _sfc_calendar(self):
        """Calendar to walk when scheduling on this workcenter."""
        self.ensure_one()
        return (self.resource_calendar_id
                or self.company_id.resource_calendar_id
                or self.env.company.resource_calendar_id)


class MrpWorkcenterProductivity(models.Model):
    _inherit = "mrp.workcenter.productivity"

    # The costing layer reads this split. Native Odoo records a single
    # `duration`; the vendor module classified each time log into setup,
    # working or teardown. Reproduced because mrp_product_costing (and its
    # CE replacement's optional path) consume the field names.
    setup_duration = fields.Float(
        "Setup Duration", compute="_compute_duration_split", store=True)
    working_duration = fields.Float(
        "Working Duration", compute="_compute_duration_split", store=True)
    teardown_duration = fields.Float(
        "Cleanup Duration", compute="_compute_duration_split", store=True)
    overall_duration = fields.Float(
        "Overall Duration", compute="_compute_duration_split", store=True)

    @api.depends("duration", "loss_id")
    def _compute_duration_split(self):
        """Classify a time log by its productivity-loss reason.

        Native Odoo tags every log with a ``loss_id`` whose ``loss_type`` is
        productive or one of the loss categories. There is no native notion
        of setup versus run, so the split keys off the loss reason's name
        where it is recognisable and otherwise treats the time as working.
        This is a best-effort classification, and ``overall_duration`` — the
        figure costing actually needs — is exact regardless.
        """
        for rec in self:
            duration = rec.duration or 0.0
            name = (rec.loss_id.name or "") if rec.loss_id else ""
            label = name.lower() if isinstance(name, str) else ""
            setup = teardown = working = 0.0
            if "setup" in label or "set-up" in label:
                setup = duration
            elif "clean" in label or "teardown" in label or "tear-down" in label:
                teardown = duration
            else:
                working = duration
            rec.setup_duration = setup
            rec.working_duration = working
            rec.teardown_duration = teardown
            rec.overall_duration = duration


class MrpWorkcenterLoad(models.Model):
    _name = "mrp.workcenter.load"
    _description = "Workcenter Daily Load"
    _order = "date_planned, workcenter_id"

    workcenter_id = fields.Many2one(
        "mrp.workcenter", "Workcenter", required=True, ondelete="cascade",
        index=True)
    workorder_id = fields.Many2one(
        "mrp.workorder", "Work Order", required=True, ondelete="cascade",
        index=True)
    production_id = fields.Many2one(
        related="workorder_id.production_id", store=True, index=True)
    product_id = fields.Many2one(related="production_id.product_id", store=True)
    product_qty = fields.Float(related="workorder_id.qty_production")
    date_planned = fields.Datetime("Planned Date", index=True)
    week_nro = fields.Char("Week", compute="_compute_week_number", store=True)
    wo_capacity_requirements = fields.Float("Required (hours)")

    @api.depends("date_planned")
    def _compute_week_number(self):
        for rec in self:
            if rec.date_planned:
                iso = rec.date_planned.isocalendar()
                rec.week_nro = "%s-W%02d" % (iso[0], iso[1])
            else:
                rec.week_nro = False
