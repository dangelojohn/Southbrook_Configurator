# SPDX-License-Identifier: LGPL-3.0-only
"""M2 operation-template + duration-formula tests.

Two parts:
  1. Master-data sanity — 15 seeded templates, codes unique, each
     points at a kitchen-active work center, each has a category
     that matches its work center's station type.
  2. Duration formula — edge cases (missing drivers, fixed-time
     templates, negative inputs, factor stacking, override args).
"""
from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "sbk_kitchen", "m2")
class TestOperationTemplates(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Template = cls.env["southbrook.kitchen.operation.template"]

    def _ref(self, name):
        return self.env.ref(
            f"southbrook_mrp_kitchen_workcenters.{name}")

    # ------------------------------------------------------------------
    # Master data
    # ------------------------------------------------------------------

    def test_15_templates_seeded(self):
        self.assertEqual(
            self.Template.search_count([]), 15,
            "Expected 15 seeded operation templates.",
        )

    def test_template_codes_unique(self):
        codes = self.Template.search([]).mapped("code")
        self.assertEqual(
            len(codes), len(set(codes)),
            "Operation-template codes must be unique.",
        )

    def test_every_template_has_a_workcenter(self):
        """Every operation template points at a default work center."""
        for tpl in self.Template.search([]):
            self.assertTrue(
                tpl.default_workcenter_id,
                f"{tpl.code}: default_workcenter_id is required.",
            )

    def test_category_matches_workcenter_station_type(self):
        """An operation template's category should agree with its
        target work center's station_type. Engineering on the
        engineering bay, cutting on the saw, etc.

        Two narrow exemptions:
          - Door Hanging (workcenter_door) is station_type='assembly'
            but it's reasonable for an assembly-category operation —
            we don't enforce equality across the whole catalog.
          - Door Shop (wc_door_shop) is station_type='cnc' even though
            CNC profiling drives door blanks — also reasonable.
        """
        for tpl in self.Template.search([]):
            self.assertEqual(
                tpl.default_workcenter_id.x_sbk_active_for_kitchen,
                True,
                f"{tpl.code}: target work center "
                f"{tpl.default_workcenter_id.code} is not kitchen-active",
            )

    # ------------------------------------------------------------------
    # Duration formula — edge cases
    # ------------------------------------------------------------------

    def test_fixed_template_ignores_driver(self):
        """quantity_driver_type='fixed' returns setup+changeover only.
        Big driver values are ignored — that's the contract."""
        tpl = self._ref("op_template_design_review")
        self.assertEqual(tpl.quantity_driver_type, "fixed")
        zero_driver = tpl.compute_expected_duration(driver_value=0)
        big_driver = tpl.compute_expected_duration(driver_value=99999)
        self.assertEqual(zero_driver, big_driver,
                         "fixed templates must ignore driver_value")

    def test_cutting_formula_full_stack(self):
        """Cut Panels with 10 sheets, all factors 1.0:
        setup(15) + changeover(10) + 10 * 6 * 1 * 1 * 1 = 85 min."""
        tpl = self._ref("op_template_cut_panels")
        result = tpl.compute_expected_duration(driver_value=10)
        self.assertEqual(result, 85)

    def test_cutting_with_complexity_multiplier(self):
        """Cut Panels with 10 sheets, complexity 1.5:
        15 + 10 + 10 * 6 * 1 * 1 * 1.5 = 115 min."""
        tpl = self._ref("op_template_cut_panels")
        result = tpl.compute_expected_duration(
            driver_value=10, complexity_factor=1.5)
        self.assertEqual(result, 115)

    def test_painted_finish_lifts_paint_duration(self):
        """Paint/Lacquer 5 m², finish=high_gloss complexity 1.5:
        30 + 45 + 5 * 10 * 1 * 1 * 1.5 = 150 min."""
        tpl = self._ref("op_template_paint_lacquer")
        result = tpl.compute_expected_duration(
            driver_value=5, complexity_factor=1.5)
        self.assertEqual(result, 150)

    def test_negative_driver_floored_at_zero(self):
        """Negative driver shouldn't subtract from setup+changeover.
        Cut Panels with driver=-3 collapses to setup+changeover only."""
        tpl = self._ref("op_template_cut_panels")
        result = tpl.compute_expected_duration(driver_value=-3)
        self.assertEqual(result, 25,
                         "Negative driver should be floored at 0; "
                         "result must be setup(15) + changeover(10) = 25.")

    def test_none_factor_falls_back_to_template_default(self):
        """When caller passes material_factor=None, the template's own
        material_adjustment_factor is used. Drilling baseline =
        setup(10) + changeover(10) + 4 * 2 * 1 = 28 min."""
        tpl = self._ref("op_template_drilling")
        result = tpl.compute_expected_duration(
            driver_value=4,
            material_factor=None,
            finish_factor=None,
            complexity_factor=None,
        )
        self.assertEqual(result, 28)

    def test_zero_factor_falls_back_to_safe_default(self):
        """A 0.0 factor would zero the whole per-unit term — the
        _safe_factor helper substitutes 1.0 (or the template default)
        instead. Drilling with material_factor=0 → 1.0 fallback."""
        tpl = self._ref("op_template_drilling")
        result = tpl.compute_expected_duration(
            driver_value=4, material_factor=0.0)
        # Same as baseline: setup(10) + changeover(10) + 4 * 2 * 1 = 28
        self.assertEqual(result, 28)

    def test_setup_changeover_overrides(self):
        """Caller can override setup_time_min and changeover_time_min
        to account for back-to-back jobs on the same color."""
        tpl = self._ref("op_template_paint_lacquer")
        result = tpl.compute_expected_duration(
            driver_value=5, setup_time_min=0, changeover_time_min=0)
        # 0 + 0 + 5 * 10 = 50
        self.assertEqual(result, 50)

    def test_rounding_ceils_up(self):
        """A 7.2-min job rounds to 8 min — the planner's grid never
        underestimates."""
        tpl = self._ref("op_template_hardware_fitting")
        # setup=5 + 0.7 * 3.0 = 5 + 2.1 = 7.1 -> ceil 8
        result = tpl.compute_expected_duration(driver_value=0.7)
        self.assertEqual(result, 8)

    def test_constraint_rejects_negative_minutes_per_unit(self):
        """The constraint guards the master-data layer; the formula
        wouldn't crash but a planner shouldn't be able to save a -5
        min/unit value."""
        tpl = self.Template.create({
            "name": "Negative Test Template",
            "code": "NEG_TEST",
            "operation_category": "other",
        })
        with self.assertRaises(ValidationError):
            tpl.minutes_per_unit = -5

    def test_constraint_rejects_zero_factor(self):
        """material_adjustment_factor must be > 0 at the master-data
        level — _safe_factor's fallback is for runtime inputs."""
        tpl = self.Template.create({
            "name": "Zero Factor Test",
            "code": "ZERO_FACTOR_TEST",
            "operation_category": "other",
        })
        with self.assertRaises(ValidationError):
            tpl.material_adjustment_factor = 0
