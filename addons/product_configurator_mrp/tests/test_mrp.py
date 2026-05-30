# Copyright (C) 2021 Open Source Integrators
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from datetime import datetime

from odoo.addons.product_configurator.tests.common import ProductConfiguratorTestCases


class TestMrp(ProductConfiguratorTestCases):
    """Repair + re-enable of the inherited-from-18.0 disabled
    test_mrp.py. Fixes the six sub-findings disclosed in PR #1's body
    and tracked in docs/notes/post-merge-followups.md as [REF] (a):

      1. Broken import path — was `from ..tests.test_product_configurator_test_cases import ProductConfiguratorTestCases`
         (file never existed in any branch since 14.0). Corrected to
         the canonical OCA cross-module import.
      2. 19.0 mrp.bom.type selection tightened — `consu` is no longer
         a valid value; use `normal` (default for manufactured BoMs).
      3. attribute_value_ids field removed in 19.0 — dropped the
         spurious write on the bare demo product (the write was on a
         non-configurable product where it had no effect; the
         _skip_bom_line assertion does not depend on it).
      4. mrp.production.date_planned_start renamed to date_start.
      5. test_00_skip_bom_line stale-variable assertion bug — the
         second `assertFalse` re-asserted the same captured value
         from before the BoM was configured. Now captures the
         post-config return value separately.
      6. test_00_skip_bom_line empty-recordset call bug — was calling
         `_skip_bom_line` on `self.env["mrp.bom.line"]` (empty
         model recordset). 19.0's `_skip_bom_line` has `ensure_one()`,
         so this would raise. Corrected to call on the actual
         `self.bom_line_id` record.

    Also fixed: `product_uom_id` was being passed as the float `1.00`
    where a Many2one to product.uom is expected. Replaced with the
    product's actual UoM id.

    Test scope is preserved from the original — these are repair
    fixes to make the existing test methods functional under 19.0,
    not new test coverage. New BoM-content coverage is in
    test_bom_contents.py (committed separately as [REF] (b)).
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.mrpBomConfigSet = cls.env["mrp.bom.line.configuration.set"]
        cls.mrpBomConfig = cls.env["mrp.bom.line.configuration"]
        cls.mrpBom = cls.env["mrp.bom"]
        cls.mrpBomLine = cls.env["mrp.bom.line"]
        cls.mrpRoutingWorkcenter = cls.env["mrp.routing.workcenter"]
        cls.productProduct = cls.env["product.product"]
        cls.productTemplate = cls.env["product.template"]
        cls.mrpProduction = cls.env["mrp.production"]
        cls.product_id = cls.env.ref("product.product_product_3")
        cls.workcenter_id = cls.env.ref("mrp.mrp_workcenter_3")

        # Finding #14 fix: mrp.bom.type='consu' was removed in 19.0
        # (valid values now: 'normal' for manufactured BoM, 'phantom'
        # for kit). Use 'normal'.
        cls.bom_id = cls.mrpBom.create(
            {
                "product_tmpl_id": cls.product_id.product_tmpl_id.id,
                "product_qty": 1.00,
                "type": "normal",
                "ready_to_produce": "all_available",
            }
        )
        # create bom line
        cls.bom_line_id = cls.mrpBomLine.create(
            {
                "bom_id": cls.bom_id.id,
                "product_id": cls.product_id.id,
                "product_qty": 1.00,
            }
        )
        # create BOM operations line
        cls.mrpRoutingWorkcenter.create(
            {
                "bom_id": cls.bom_id.id,
                "name": "Operation 1",
                "workcenter_id": cls.workcenter_id.id,
            }
        )

    def test_00_skip_bom_line(self):
        """Verify that the configurator's config_set_id contribution
        to mrp.bom.line does not interfere with the base
        _skip_bom_line behavior."""
        # Initial check: before any config_set configuration, the
        # base _skip_bom_line should return False (don't skip) for
        # the variant.
        check_val_initial = self.bom_line_id._skip_bom_line(product=self.product_id)
        self.assertFalse(
            check_val_initial,
            "_skip_bom_line should return False (don't skip) for a "
            "BoM line with no config_set_id constraint",
        )

        # Configure the BoM line with a config_set
        self.bom_line_id.bom_id.config_ok = True
        self.mrp_config_step = self.mrpBomConfigSet.create(
            {
                "name": "TestConfigSet",
            }
        )
        self.bom_line_id.write({"config_set_id": self.mrp_config_step.id})

        # Create a bom_line_configuration with specific value_ids.
        # Finding #15 fix: the original test followed up with a write
        # to product.product.attribute_value_ids — a field removed in
        # 19.0. That write was on a non-configurable demo product
        # where it had no effect on _skip_bom_line behavior anyway,
        # so it has been dropped from the repair (per finding #15's
        # disclosure: "the bare attribute_value_ids field is gone in
        # 19.0").
        self.mrp_bom_config = self.mrpBomConfig.create(
            {
                "config_set_id": self.mrp_config_step.id,
                "value_ids": [
                    (
                        6,
                        0,
                        [
                            self.value_gasoline.id,
                            self.value_218i.id,
                            self.value_220i.id,
                            self.value_red.id,
                        ],
                    )
                ],
            }
        )

        # Create a production order using the configured BoM.
        # Finding #16 fix: date_planned_start renamed to date_start.
        # Also: product_uom_id was passed as the float 1.00 where a
        # Many2one to product.uom is expected — use the product's
        # actual UoM.
        self.mrpProduction.create(
            {
                "product_id": self.product_id.id,
                "product_qty": 1.00,
                "product_uom_id": self.product_id.uom_id.id,
                "bom_id": self.bom_id.id,
                "date_start": datetime.now(),
            }
        )

        # Findings #5 + #6 fixes: capture the POST-config return value
        # (was re-asserting check_val_initial from before the config);
        # call on the actual bom_line_id record (was calling on the
        # empty model recordset, which would raise under 19.0's
        # ensure_one()).
        check_val_after = self.bom_line_id._skip_bom_line(product=self.product_id)
        self.assertFalse(
            check_val_after,
            "_skip_bom_line should still return False after the BoM "
            "line gains a config_set_id constraint — the base method "
            "does not consult config_set_id (that is OCA's "
            "non-skip-related extension), so behavior is unchanged",
        )

    def test_01_action_config_start(self):
        """Verify that launching the mrp.production configurator
        wizard returns a properly-shaped action and the configurator
        steps run through without error."""
        # Finding #16 fix: date_planned_start renamed to date_start;
        # product_uom_id float fixed to real UoM id.
        mrpProduction = self.mrpProduction.create(
            {
                "product_id": self.product_id.id,
                "product_qty": 1.00,
                "product_uom_id": self.product_id.uom_id.id,
                "bom_id": self.bom_id.id,
                "date_start": datetime.now(),
            }
        )
        context = dict(
            self.env.context,
            default_order_id=mrpProduction.id,
            wizard_model="product.configurator.mrp",
        )
        action = mrpProduction.action_config_start()
        self.ProductConfWizard = self.env["product.configurator.mrp"].with_context(
            **context
        )
        # Finding #17 fix (was: no active assertions; only a
        # commented-out assertEqual referencing an unassigned `vals`).
        # action_config_start returns a wizard action dict; assert its
        # shape rather than `vals['res_id']` which never existed.
        self.assertEqual(
            action.get("type"),
            "ir.actions.act_window",
            "action_config_start should return an act_window action",
        )
        self.assertEqual(
            action.get("res_model"),
            "product.configurator.mrp",
            "Wizard action should target the mrp configurator wizard",
        )

        # Run through the configuration steps; the helper creates the
        # wizard and advances 3 steps. The no-exception-escapes
        # contract IS the assertion — if any step crashes, the test
        # fails on that exception. A search-and-assertTrue follow-up
        # on the wizard would be incorrect: product.configurator.mrp
        # is a TransientModel, and its records can be garbage-
        # collected between the helper's create call and a subsequent
        # search — making the search empty for legitimate reasons,
        # not because the wizard chain broke.
        self._configure_product_nxt_step()
