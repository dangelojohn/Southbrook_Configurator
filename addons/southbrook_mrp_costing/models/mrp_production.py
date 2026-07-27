# SPDX-License-Identifier: LGPL-3.0-only
"""Manufacturing cost layers for Southbrook, CE-native.

Replaces the standard/planned/actual costing of the proprietary
``mrp_product_costing``. Three deliberate departures from it:

1. **No shop-floor-control dependency.** The vendor module read the
   setup/working/teardown split from ``mrp_shop_floor_control``'s additions
   to ``mrp.workcenter.productivity``. Its own actual-cost compute already
   fell back to plain ``time.duration`` when those were absent, which proves
   the split is an enhancement rather than a requirement. This module reads
   native ``duration`` only, folding setup and run time together.

2. **A zero-output order is not silently costed as one unit.** The vendor
   ``_get_qty_produced`` ended ``return qty_produced or 1.0``, so an order
   that produced nothing got per-unit costs computed against a fabricated
   quantity of 1. Here the produced quantity is reported honestly and unit
   costs are left at zero, with ``costing_note`` saying why.

3. **``industrial_cost`` does not wait on a financial close.** In the vendor
   design it was written only by ``button_closure``, which is gated on
   company accounts that are unset — so it read 0.0 forever while
   Command Center used it for job margin. Here it is a stored field
   maintained alongside actual cost, so margin reflects reality without
   depending on GL configuration.

CONTRACT — these two field names are read by Southbrook via
``getattr(..., 0.0)`` in ``southbrook_project_mrp/models/project_task.py``
and ``southbrook_command_center/models/command_center.py``:

    mrp.production.planned_direct_cost
    mrp.production.industrial_cost

The ``getattr`` default means a rename does not raise — it silently reports
a zero cost, so an at-risk job displays as free. Do not rename either field
without changing both consumers in the same commit.
"""

from odoo import _, api, fields, models

# Costs are held as plain floats in company currency, matching the module
# this replaces. Monetary would pull currency_id into every compute for no
# gain — manufacturing cost is never expressed in a customer currency here.
COST_DIGITS = "Product Price"


class MrpProduction(models.Model):
    _inherit = "mrp.production"

    # ------------------------------------------------------------------
    # Quantity basis
    # ------------------------------------------------------------------
    qty_costed = fields.Float(
        "Costed Quantity", digits="Product Unit of Measure",
        compute="_compute_qty_costed", store=True,
        help="Quantity the unit costs are divided by: what was actually "
             "produced once the order is done, otherwise what is planned.")
    costing_note = fields.Char("Costing Note", compute="_compute_qty_costed",
                               store=True)

    @api.depends("state", "qty_produced", "product_qty")
    def _compute_qty_costed(self):
        for mo in self:
            if mo.state == "done":
                qty = mo.qty_produced
                note = False
                if not qty:
                    # Deliberately NOT defaulted to 1.0. A finished order that
                    # produced nothing has no meaningful unit cost, and
                    # inventing a denominator hides a real data problem.
                    note = _("Order is done but produced nothing — unit costs "
                             "are not meaningful and are left at zero.")
            else:
                qty = mo.product_qty
                note = False
            mo.qty_costed = qty
            mo.costing_note = note

    def _unit(self, total):
        """Per-unit figure, or 0.0 when there is no honest denominator."""
        self.ensure_one()
        return total / self.qty_costed if self.qty_costed else 0.0

    # ------------------------------------------------------------------
    # Standard cost — live, from the bill of materials
    # ------------------------------------------------------------------
    # Deliberately NOT stored. Standard cost is a reference valuation of the
    # BoM at today's prices, and its inputs are component standard_price
    # values reached through a recursive explosion — a dependency Odoo cannot
    # track. Stored, the figure silently goes stale the moment a component is
    # repriced, which is how the module this replaces behaved. Computing on
    # read costs one explosion and is always truthful. The trade-off is that
    # these fields cannot be searched, sorted or summed in a list view; the
    # planned and actual layers below are stored and serve that purpose.
    std_mat_cost = fields.Float("Standard Material", digits=COST_DIGITS,
                                compute="_compute_standard_costs")
    std_var_cost = fields.Float("Standard Variable", digits=COST_DIGITS,
                                compute="_compute_standard_costs")
    std_fixed_cost = fields.Float("Standard Fixed", digits=COST_DIGITS,
                                  compute="_compute_standard_costs")
    std_direct_cost = fields.Float("Standard Direct", digits=COST_DIGITS,
                                   compute="_compute_standard_costs")
    std_direct_cost_unit = fields.Float(
        "Standard Direct / Unit", digits=COST_DIGITS,
        compute="_compute_standard_costs")

    @api.depends("bom_id", "product_qty", "product_id", "qty_costed")
    def _compute_standard_costs(self):
        for mo in self:
            mat = var = fixed = 0.0
            bom = mo.bom_id
            if bom and mo.product_id:
                factor = mo.product_qty / (bom.product_qty or 1.0)
                _boms, lines = bom.explode(mo.product_id, factor)
                for bom_line, line_vals in lines:
                    qty = line_vals.get("qty", 0.0)
                    if qty <= 0:
                        continue
                    uom = bom_line.product_uom_id
                    comp = bom_line.product_id
                    if uom and uom != comp.uom_id:
                        qty = uom._compute_quantity(qty, comp.uom_id)
                    mat += qty * comp.standard_price
                var, fixed = mo._routing_costs(bom, factor)
            mo.std_mat_cost = mat
            mo.std_var_cost = var
            mo.std_fixed_cost = fixed
            mo.std_direct_cost = mat + var + fixed
            mo.std_direct_cost_unit = mo._unit(mat + var + fixed)

    def _routing_costs(self, bom, factor):
        """Variable and fixed routing cost for *bom* scaled by *factor*.

        Variable follows cycle time against ``costs_hour`` (native to ``mrp``);
        fixed is the workcenter's per-operation setup and cleanup allowance
        against ``costs_hour_fixed``, which this module defines itself in
        ``mrp_workcenter.py`` because it was a ``mrp_product_costing``
        addition rather than core. No shop-floor-control involvement either
        way.
        """
        self.ensure_one()
        var = fixed = 0.0
        for op in bom.operation_ids:
            wc = op.workcenter_id
            if not wc:
                continue
            minutes = (op.time_cycle_manual or 0.0) * factor
            var += (minutes / 60.0) * (wc.costs_hour or 0.0)
            setup = (wc.time_start or 0.0) + (wc.time_stop or 0.0)
            fixed += (setup / 60.0) * (wc.costs_hour_fixed or 0.0)
        return var, fixed

    # ------------------------------------------------------------------
    # Planned cost — frozen snapshot taken at confirmation
    # ------------------------------------------------------------------
    planned_mat_cost = fields.Float("Planned Material", digits=COST_DIGITS,
                                    readonly=True, copy=False)
    planned_var_cost = fields.Float("Planned Variable", digits=COST_DIGITS,
                                    readonly=True, copy=False)
    planned_fixed_cost = fields.Float("Planned Fixed", digits=COST_DIGITS,
                                      readonly=True, copy=False)
    planned_direct_cost = fields.Float(
        "Planned Direct Cost", digits=COST_DIGITS, readonly=True, copy=False,
        help="Frozen at confirmation. Read by Command Center and Project "
             "job-margin scoring — see the module docstring before renaming.")
    planned_direct_cost_unit = fields.Float(
        "Planned Direct / Unit", digits=COST_DIGITS, readonly=True, copy=False)

    def _snapshot_planned_costs(self):
        """Freeze the plan as it stands now.

        Taken from the order's real component moves and work orders rather
        than from the BoM, so a plan edited between draft and confirm is
        captured as it will actually be executed.
        """
        for mo in self:
            mat = 0.0
            for move in mo.move_raw_ids:
                qty = move.product_uom_qty
                uom = move.product_uom
                if uom and uom != move.product_id.uom_id:
                    qty = uom._compute_quantity(qty, move.product_id.uom_id)
                mat += qty * move.product_id.standard_price
            var = fixed = 0.0
            for wo in mo.workorder_ids:
                wc = wo.workcenter_id
                if not wc:
                    continue
                var += ((wo.duration_expected or 0.0) / 60.0) * (wc.costs_hour or 0.0)
                setup = (wc.time_start or 0.0) + (wc.time_stop or 0.0)
                fixed += (setup / 60.0) * (wc.costs_hour_fixed or 0.0)
            if not mo.workorder_ids and mo.bom_id:
                # No routing exploded (e.g. a BoM without operations): fall
                # back to the standard routing figure so planned cost is not
                # silently short by all labour.
                factor = mo.product_qty / (mo.bom_id.product_qty or 1.0)
                var, fixed = mo._routing_costs(mo.bom_id, factor)
            total = mat + var + fixed
            mo.write({
                "planned_mat_cost": mat,
                "planned_var_cost": var,
                "planned_fixed_cost": fixed,
                "planned_direct_cost": total,
                "planned_direct_cost_unit": mo._unit(total),
            })

    def action_confirm(self):
        res = super().action_confirm()
        self._snapshot_planned_costs()
        return res

    def _split_productions(self, amounts=False, cancel_remaining_qty=False,
                           set_consumed_qty=False):
        """Re-snapshot after a backorder split.

        Splitting rewrites quantities and moves, so a planned cost frozen
        against the pre-split order no longer describes either resulting
        order.
        """
        productions = super()._split_productions(
            amounts=amounts, cancel_remaining_qty=cancel_remaining_qty,
            set_consumed_qty=set_consumed_qty)
        productions.filtered(
            lambda m: m.state not in ("draft", "cancel")
        )._snapshot_planned_costs()
        return productions

    # ------------------------------------------------------------------
    # Actual cost, and the industrial figure Southbrook consumes
    # ------------------------------------------------------------------
    actual_mat_cost = fields.Float("Actual Material", digits=COST_DIGITS,
                                   compute="_compute_actual_costs", store=True)
    actual_var_cost = fields.Float("Actual Labour", digits=COST_DIGITS,
                                   compute="_compute_actual_costs", store=True)
    industrial_cost = fields.Float(
        "Industrial Cost", digits=COST_DIGITS,
        compute="_compute_actual_costs", store=True,
        help="Actual direct cost once consumption and time are recorded, "
             "falling back to the planned figure while the order is open. "
             "Read by Command Center job-margin scoring — see the module "
             "docstring before renaming.")
    industrial_cost_unit = fields.Float(
        "Industrial Cost / Unit", digits=COST_DIGITS,
        compute="_compute_actual_costs", store=True)
    delta_direct_cost = fields.Float(
        "Variance vs Plan", digits=COST_DIGITS,
        compute="_compute_actual_costs", store=True,
        help="Actual industrial cost less planned direct cost. Positive means "
             "the order cost more than planned.")

    @api.depends("state", "qty_costed", "planned_direct_cost",
                 "move_raw_ids.state", "move_raw_ids.quantity",
                 "workorder_ids.state", "workorder_ids.time_ids.duration")
    def _compute_actual_costs(self):
        for mo in self:
            mat = 0.0
            for move in mo.move_raw_ids.filtered(lambda m: m.state == "done"):
                qty = move.quantity
                uom = move.product_uom
                if uom and uom != move.product_id.uom_id:
                    qty = uom._compute_quantity(qty, move.product_id.uom_id)
                mat += qty * move.product_id.standard_price
            var = 0.0
            for wo in mo.workorder_ids:
                wc = wo.workcenter_id
                if not wc:
                    continue
                # Native duration only. mrp_shop_floor_control split this into
                # setup/working/teardown; that split is not required to get a
                # correct total, so this module does not depend on it.
                minutes = sum(wo.time_ids.mapped("duration"))
                var += (minutes / 60.0) * (wc.costs_hour or 0.0)
            recorded = bool(mat or var)
            industrial = (mat + var) if recorded else mo.planned_direct_cost
            mo.actual_mat_cost = mat
            mo.actual_var_cost = var
            mo.industrial_cost = industrial
            mo.industrial_cost_unit = mo._unit(industrial)
            mo.delta_direct_cost = industrial - mo.planned_direct_cost
