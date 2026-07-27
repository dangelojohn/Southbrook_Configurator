# SPDX-License-Identifier: LGPL-3.0-only
"""Task 4 (kitchen templates) — the shipped starter catalog.

Every ACTIVE shipped template must instantiate fully resolved at its
defaults (honesty: a starter template that lands placeholder lines is
data-broken, not "close enough"). Inactive rows (PEN-10X10, H-14X12)
are honest placeholders for engine capabilities that don't exist yet.
"""
from odoo.tests import TransactionCase, tagged

# Test-authored templates from the T2/T3 suites use these prefixes.
_TEST_CODE_PREFIXES = ("T1-", "T2-", "T3-")


@tagged("post_install", "-at_install", "southbrook",
        "southbrook_kitchen_3d_configurator", "kitchen_templates")
class TestShippedTemplateCatalog(TransactionCase):

    def _shipped(self, active_test=True):
        tpls = self.env["southbrook.kitchen.template"].with_context(
            active_test=active_test).search([])
        return tpls.filtered(
            lambda t: not t.code.startswith(_TEST_CODE_PREFIXES))

    def test_every_active_shipped_template_instantiates(self):
        templates = self._shipped()
        self.assertGreaterEqual(
            len(templates), 4, "T4 ships 4 active starter templates")
        for tpl in templates:
            with self.subTest(template=tpl.code):
                design = tpl.action_instantiate()
                self.assertTrue(design.cabinet_line_ids)
                self.assertFalse(
                    design.cabinet_line_ids.filtered("is_unresolved"),
                    "%s: shipped templates must fully resolve at their "
                    "defaults" % tpl.code)
                self.assertGreater(design.estimated_price, 0.0)
                # No silent room growth — defaults land verbatim.
                self.assertEqual(design.room_width_in,
                                 tpl.default_room_width_in)
                self.assertEqual(design.room_depth_in,
                                 tpl.default_room_depth_in)
                if tpl.layout_shape in ("l_shape", "u_shape", "g_shape"):
                    self.assertTrue(design.cabinet_line_ids.filtered(
                        lambda l: l.layout_role == "derived"
                        and l.cabinet_type == "corner"),
                        "%s: corner must be ENGINE-derived" % tpl.code)

    def test_galley_lands_on_both_walls(self):
        gal = self._shipped().filtered(lambda t: t.code == "GAL-10")
        self.assertTrue(gal, "GAL-10 must ship active")
        design = gal.action_instantiate()
        walls = set(design.cabinet_line_ids.mapped("wall"))
        self.assertIn("back", walls)
        self.assertIn("front", walls)
        appl = design.cabinet_line_ids.filtered(
            lambda l: l.cabinet_type == "appliance")
        self.assertEqual(sorted(appl.mapped("appliance_type")),
                         ["fridge", "range"])

    def test_per_wall_fit_rejects_run_overflow(self):
        # A 96" range cannot share GAL-08's 96" back wall with a 33"
        # sink — the per-wall guard must refuse, never grow the room.
        gal = self._shipped().filtered(lambda t: t.code == "GAL-08")
        self.assertTrue(gal, "GAL-08 must ship active")
        fit = gal.parametric_fit(appliance_widths={"range": 96.0})
        self.assertFalse(fit["ok"])
        self.assertIn("back wall", fit["message"])

    def test_no_corner_or_filler_slots_templated(self):
        # Corners are engine-derived; fillers aren't even a valid slot
        # type (impossible state by schema). Starter set ships neither.
        slots = self.env["southbrook.kitchen.template.line"].with_context(
            active_test=False).search([])
        shipped = slots.filtered(
            lambda s: not s.template_id.code.startswith(_TEST_CODE_PREFIXES))
        self.assertTrue(shipped)
        self.assertFalse(
            shipped.filtered(lambda s: s.cabinet_type == "corner"),
            "corners are engine-derived — never templated (starter set)")

    def test_engine_blocked_shapes_ship_inactive(self):
        placeholders = self._shipped(active_test=False).filtered(
            lambda t: t.code in ("PEN-10X10", "H-14X12"))
        self.assertEqual(len(placeholders), 2)
        for tpl in placeholders:
            with self.subTest(template=tpl.code):
                self.assertFalse(tpl.active)
                self.assertIn("INACTIVE", tpl.notes or "")

    def test_compat_galley_code_resolves(self):
        # T3 legacy-compat map must point at a REAL shipped code.
        picker = self.env["kitchen.design.template.picker"]
        code = picker._COMPAT_PRESET_CODES["galley"]
        tpl = self.env["southbrook.kitchen.template"].search(
            [("code", "=", code)], limit=1)
        self.assertTrue(tpl, "compat galley code %s must be shipped" % code)
        self.assertTrue(tpl.active)
