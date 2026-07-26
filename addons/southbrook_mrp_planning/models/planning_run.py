# SPDX-License-Identifier: LGPL-3.0-only
"""Demand-driven requirements planning for make-to-order production.

Contrast with the vendor engine this replaces
(``openvalue_mrp_planning_engine``), which iterates
``stock.warehouse.orderpoint`` and filters its sales-demand path on
``product_id.is_storable``. Southbrook has no reorder points and models
every finished-goods cabinet as a non-storable consumable, so both paths
yield nothing. Measured on production 2026-07-26: 2 historical runs, 0
lines, 0 orderpoints, 0 of 27 confirmed sale-order lines surviving the
storability filter.

Here demand comes from confirmed sales orders and storability gates only
*netting*, never demand recognition.
"""

import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# Hard ceiling on BoM recursion. Cabinet BoMs are shallow (carcass → panels
# → sheet stock, ~4 levels), so anything approaching this indicates a cycle
# that _explode's own seen-set failed to catch.
MAX_BOM_DEPTH = 20


class SouthbrookPlanningRun(models.Model):
    _name = "southbrook.planning.run"
    _description = "Southbrook Requirements Planning Run"
    _order = "date desc, id desc"

    name = fields.Char(
        "Reference", required=True, copy=False, readonly=True,
        default=lambda self: _("New"))
    date = fields.Date(
        "Planning Date", required=True, default=fields.Date.context_today)
    company_id = fields.Many2one(
        "res.company", "Company", required=True,
        default=lambda self: self.env.company)
    warehouse_id = fields.Many2one(
        "stock.warehouse", "Warehouse", required=True,
        default=lambda self: self.env["stock.warehouse"].search(
            [("company_id", "=", self.env.company.id)], limit=1))
    state = fields.Selection(
        [("draft", "Draft"), ("done", "Computed")],
        default="draft", required=True, readonly=True)
    line_ids = fields.One2many(
        "southbrook.planning.line", "run_id", "Requirements", readonly=True)
    line_count = fields.Integer("Requirements", compute="_compute_counts")
    released_count = fields.Integer("Released", compute="_compute_counts")
    horizon_days = fields.Integer(
        "Demand Horizon (days)", default=0,
        help="Only consider sales-order lines committed within this many "
             "days. Zero means no horizon limit — plan the whole open book.")
    note = fields.Text("Run Log", readonly=True)

    @api.depends("line_ids", "line_ids.released")
        # released is a plain stored boolean on the line, so depending on it
        # is sufficient; no need to depend on generated_mo/po.
    def _compute_counts(self):
        for run in self:
            run.line_count = len(run.line_ids)
            run.released_count = len(run.line_ids.filtered("released"))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", _("New")) == _("New"):
                vals["name"] = self.env["ir.sequence"].next_by_code(
                    "southbrook.planning.run") or _("New")
        return super().create(vals_list)

    # ------------------------------------------------------------------
    # Demand collection
    # ------------------------------------------------------------------
    def _demand_domain(self):
        """Confirmed, undelivered sales demand for this company.

        Deliberately *no* ``is_storable`` filter — that is the defect this
        module exists to correct. A non-storable made-to-order cabinet is
        real demand even though it never sits in stock.
        """
        self.ensure_one()
        domain = [
            ("order_id.state", "=", "sale"),
            ("display_type", "=", False),
            ("company_id", "=", self.company_id.id),
            ("product_id", "!=", False),
        ]
        if self.horizon_days:
            limit = fields.Date.add(self.date, days=self.horizon_days)
            domain.append(("order_id.commitment_date", "<=", limit))
        return domain

    def _collect_gross_demand(self):
        """Return {product: qty} of independent (finished-goods) demand."""
        self.ensure_one()
        demand = {}
        lines = self.env["sale.order.line"].search(self._demand_domain())
        for line in lines:
            remaining = line.product_uom_qty - line.qty_delivered
            if remaining <= 0:
                continue
            # Normalise to the product's own UoM so BoM maths is coherent.
            # v19 renamed sale.order.line.product_uom -> product_uom_id.
            qty = line.product_uom_id._compute_quantity(
                remaining, line.product_id.uom_id) if line.product_uom_id \
                else remaining
            if qty > 0:
                demand[line.product_id] = demand.get(line.product_id, 0.0) + qty
        return demand

    # ------------------------------------------------------------------
    # Supply netting
    # ------------------------------------------------------------------
    def _open_production_qty(self, product):
        """Quantity still to be produced on open manufacturing orders.

        This is the only supply signal available for a non-storable product:
        it never enters stock, so ``qty_available``/``incoming_qty`` are
        structurally blind to an MO that is already running for it. Without
        this, releasing a requirement and then recomputing would propose the
        same work a second time.
        """
        self.ensure_one()
        mos = self.env["mrp.production"].search([
            ("product_id", "=", product.id),
            ("company_id", "=", self.company_id.id),
            ("state", "not in", ("done", "cancel")),
        ])
        outstanding = 0.0
        for mo in mos:
            outstanding += max(mo.product_qty - mo.qty_produced, 0.0)
        return outstanding

    def _available_supply(self, product):
        """Supply already committed to satisfying demand for *product*.

        Storable: free stock plus inbound. ``free_qty`` rather than
        ``qty_available`` deliberately — on-hand that is already reserved
        against another operation is not available to this plan, and using
        the gross figure lets two demands net against the same physical
        units.

        Non-storable: stock quantities are meaningless (the product never
        enters stock), so supply is whatever open manufacturing orders will
        deliver. A cabinet built for a previous order cannot satisfy this
        one, but a cabinet currently *being* built for this demand can.
        """
        self.ensure_one()
        if not product.is_storable:
            return self._open_production_qty(product)
        # v19 stock reads the 'warehouse_id' context key (see
        # product._get_domain_locations); a plain 'warehouse' key is silently
        # ignored and the figures fall back to every warehouse in
        # env.companies, overstating supply in a multi-warehouse company.
        scoped = product.with_context(warehouse_id=self.warehouse_id.id)
        return scoped.free_qty + scoped.incoming_qty

    # ------------------------------------------------------------------
    # BoM explosion
    # ------------------------------------------------------------------
    def _explode(self, product, qty, depth, seen, requirements):
        """Accumulate dependent demand for *product* into *requirements*.

        ``seen`` carries the product ids on the current branch only, so a
        component legitimately reachable by two different paths is still
        summed, while a genuine cycle terminates.
        """
        self.ensure_one()
        if depth > MAX_BOM_DEPTH:
            raise UserError(_(
                "Bill-of-materials nesting exceeded %(max)s levels while "
                "exploding %(product)s. This almost certainly indicates a "
                "circular BoM.",
                max=MAX_BOM_DEPTH, product=product.display_name))
        bom = self.env["mrp.bom"]._bom_find(product)[product]
        if not bom:
            return
        # _explode returns (bom_lines, line_values); we only need the lines
        # and their consumed quantities.
        factor = qty / (bom.product_qty or 1.0)
        exploded, _lines = bom.explode(product, factor)
        for bom_line, line_vals in _lines:
            component = bom_line.product_id
            needed = line_vals.get("qty", 0.0)
            if needed <= 0:
                continue
            # bom.explode reports the quantity in the BoM LINE's UoM, which is
            # not necessarily the component's own UoM. Netting compares against
            # stock figures expressed in component.uom_id, and the recursive
            # factor divides by the sub-BoM's product_qty (also component UoM),
            # so convert once here rather than mixing units downstream.
            line_uom = bom_line.product_uom_id
            if line_uom and line_uom != component.uom_id:
                needed = line_uom._compute_quantity(needed, component.uom_id)
                if needed <= 0:
                    continue
            requirements[component] = requirements.get(component, 0.0) + needed
            if component.id in seen:
                _logger.warning(
                    "southbrook.planning: cycle guard tripped on %s",
                    component.display_name)
                continue
            self._explode(
                component, needed, depth + 1, seen | {component.id},
                requirements)

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------
    def action_compute(self):
        self.ensure_one()
        # Released lines are an audit record of work that was actually put
        # into the system, and they are pointed at by a live MO or PO. Only
        # the unreleased proposals are recomputed. Wiping released lines here
        # would both lose that trail and — because supply for a non-storable
        # product is derived from open MOs — let the same demand be released
        # twice, over-producing.
        self.line_ids.filtered(lambda l: not l.released).unlink()
        Line = self.env["southbrook.planning.line"]
        Bom = self.env["mrp.bom"]

        gross = self._collect_gross_demand()
        if not gross:
            self.write({
                "state": "done",
                "note": _("No confirmed sales demand found for %s.",
                          self.warehouse_id.display_name),
            })
            return True

        # Independent demand first, then dependent demand from BoMs.
        requirements = dict(gross)
        for product, qty in gross.items():
            self._explode(product, qty, 0, {product.id}, requirements)

        created = 0
        skipped_covered = 0
        vals_list = []
        for product, needed in requirements.items():
            supply = self._available_supply(product)
            net = needed - supply
            if net <= 0:
                skipped_covered += 1
                continue
            bom = Bom._bom_find(product)[product]
            vals_list.append({
                "run_id": self.id,
                "product_id": product.id,
                "gross_qty": needed,
                "supply_qty": supply,
                "net_qty": net,
                "is_independent": product in gross,
                "supply_type": "manufacture" if bom else "buy",
                "planned_date": self.date,
            })
            created += 1
        if vals_list:
            Line.create(vals_list)

        self.write({
            "state": "done",
            "note": _(
                "Planned %(demand)s finished-goods lines of demand into "
                "%(reqs)s distinct products; %(created)s require action, "
                "%(covered)s already covered by stock.",
                demand=len(gross), reqs=len(requirements),
                created=created, covered=skipped_covered),
        })
        return True


class SouthbrookPlanningLine(models.Model):
    _name = "southbrook.planning.line"
    _description = "Southbrook Planning Requirement"
    _order = "is_independent desc, product_id"

    run_id = fields.Many2one(
        "southbrook.planning.run", "Run", required=True, ondelete="cascade",
        index=True)
    company_id = fields.Many2one(
        related="run_id.company_id", store=True, index=True)
    product_id = fields.Many2one("product.product", "Product", required=True)
    is_independent = fields.Boolean(
        "Sold Item", help="Demand came directly from a sales order, rather "
                          "than from a bill of materials.")
    gross_qty = fields.Float("Required", digits="Product Unit of Measure")
    supply_qty = fields.Float("Available", digits="Product Unit of Measure")
    net_qty = fields.Float("To Supply", digits="Product Unit of Measure")
    supply_type = fields.Selection(
        [("manufacture", "Manufacture"), ("buy", "Buy")], required=True)
    planned_date = fields.Date("Planned Date")
    released = fields.Boolean("Released", copy=False, readonly=True)
    generated_ref = fields.Reference(
        selection=[("mrp.production", "Manufacturing Order"),
                   ("purchase.order", "Purchase Order")],
        string="Created Document", copy=False, readonly=True)

    def action_release(self):
        """Create the real supply document for each unreleased line.

        The rows are locked before the released flag is re-read. Without the
        lock, two concurrent callers — two users, a double-clicked button, or
        a user racing a scheduled job — can both pass the ``released`` check
        before either commits, and each creates a document. A duplicate
        purchase order is real money, so this is a lock rather than a
        best-effort check.
        """
        if not self:
            return True
        self.env.cr.execute(
            "SELECT id FROM southbrook_planning_line WHERE id IN %s FOR UPDATE",
            (tuple(self.ids),))
        self.invalidate_recordset(["released", "generated_ref"])
        for line in self:
            if line.released:
                continue
            if line.supply_type == "manufacture":
                line._release_manufacture()
            else:
                line._release_buy()
        return True

    def _release_manufacture(self):
        self.ensure_one()
        bom = self.env["mrp.bom"]._bom_find(self.product_id)[self.product_id]
        if not bom:
            raise UserError(_(
                "%s has no bill of materials, so it cannot be manufactured. "
                "Change the line to Buy.", self.product_id.display_name))
        vals = {
            "product_id": self.product_id.id,
            "product_qty": self.net_qty,
            "product_uom_id": self.product_id.uom_id.id,
            "bom_id": bom.id,
            "company_id": self.company_id.id,
            "origin": self.run_id.name,
        }
        # Pin the MO to the warehouse the plan was netted against. Left to
        # its own devices the precomputed picking type resolves by a
        # limit=1 search, which in a multi-warehouse company can land the
        # order somewhere other than where the requirement was calculated.
        manu_type = self.run_id.warehouse_id.manu_type_id
        if manu_type:
            vals["picking_type_id"] = manu_type.id
        mo = self.env["mrp.production"].create(vals)
        self.write({"released": True, "generated_ref": f"mrp.production,{mo.id}"})

    def _release_buy(self):
        self.ensure_one()
        seller = self.product_id.seller_ids[:1]
        if not seller:
            raise UserError(_(
                "%s has no vendor configured, so a purchase order cannot be "
                "raised. Add a vendor on the product, or manufacture it "
                "instead.", self.product_id.display_name))
        po = self.env["purchase.order"].create({
            "partner_id": seller.partner_id.id,
            "company_id": self.company_id.id,
            "origin": self.run_id.name,
            "order_line": [(0, 0, {
                "product_id": self.product_id.id,
                "product_qty": self.net_qty,
                "product_uom_id": self.product_id.uom_id.id,
                "price_unit": seller.price,
                "date_planned": fields.Datetime.to_datetime(self.planned_date),
                "name": self.product_id.display_name,
            })],
        })
        self.write({"released": True, "generated_ref": f"purchase.order,{po.id}"})
