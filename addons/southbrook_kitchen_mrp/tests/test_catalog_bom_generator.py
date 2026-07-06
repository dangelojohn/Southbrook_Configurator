# SPDX-License-Identifier: LGPL-3.0-only
"""M4 — catalog-wide cabinet BoM generator.

Verifies mrp.bom._southbrook_generate_catalog_boms():
  * creates a BoM with real, non-empty bom_line_ids for a cabinet
    template that had none — both a boxed cabinet (panel raw materials +
    real Marathon hardware SKUs) and a pure filler/accessory (minimal
    sensible single-panel BoM, per the task's ambiguity guard),
  * is idempotent (re-running creates nothing new),
  * never mutates a template that already has a BoM (empty stub or not).
"""
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "kitchen_mrp",
        "catalog_bom_generator")
class TestCatalogBomGenerator(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Template = cls.env["product.template"]
        cls.Bom = cls.env["mrp.bom"]
        # southbrook_is_cabinet is owned by southbrook_kitchen_3d_
        # configurator, which is NOT a hard dependency of
        # southbrook_kitchen_mrp (see mrp_bom_catalog.py's own defensive
        # check). If it isn't installed alongside this module in the test
        # database, the generator has nothing in scope — skip gracefully
        # rather than failing on a missing field.
        cls._flag_missing = "southbrook_is_cabinet" not in cls.Template._fields

    def setUp(self):
        super().setUp()
        if self._flag_missing:
            self.skipTest(
                "southbrook_is_cabinet field not present — "
                "southbrook_kitchen_3d_configurator not installed in this "
                "database"
            )

    def _new_cabinet_template(self, name, cabinet_type, w_in, h_in, d_in, code):
        return self.Template.create({
            "name": name,
            "default_code": code,
            "sale_ok": True,
            "purchase_ok": True,
            "southbrook_is_cabinet": True,
            "southbrook_cabinet_type": cabinet_type,
            "southbrook_width_in": w_in,
            "southbrook_height_in": h_in,
            "southbrook_depth_in": d_in,
        })

    def _normal_boms(self, tmpl):
        return tmpl.with_context(active_test=False).bom_ids.filtered(
            lambda b: b.type == "normal"
        )

    # ------------------------------------------------------------------
    # Creation — real, non-empty bom_line_ids
    # ------------------------------------------------------------------
    def test_creates_real_bom_for_boxed_cabinet(self):
        """A 24in base cabinet with no BoM gets one, with materialized
        (non-empty) bom_line_ids covering both panel raw materials and
        real Marathon hardware SKUs — not an empty stub."""
        tmpl = self._new_cabinet_template(
            "M4 Test Base 24", "base", 24.0, 34.5, 24.0, "M4-B24"
        )
        self.assertFalse(self._normal_boms(tmpl))

        result = self.Bom._southbrook_generate_catalog_boms()
        self.assertGreaterEqual(result["created"], 1)

        boms = self._normal_boms(tmpl)
        self.assertEqual(len(boms), 1, "exactly one BoM created")
        bom = boms[0]
        self.assertTrue(
            bom.bom_line_ids, "bom_line_ids must be materialized, not empty"
        )

        codes = bom.bom_line_ids.mapped("product_id.default_code")
        self.assertTrue(
            any((c or "").startswith("RM-") for c in codes),
            "expected at least one materialized panel raw-material line",
        )
        skus = bom.bom_line_ids.mapped("product_id.x_marathon_sku")
        self.assertTrue(
            any(skus), "expected at least one real Marathon hardware SKU line"
        )

    def test_creates_minimal_bom_for_filler_accessory(self):
        """A filler panel (e.g. FP3) — a pure accessory with no boxed
        carcass — gets a minimal, sensible one-line BoM rather than being
        left BoM-less, and rather than a wrongly-synthesized full 6-panel
        box."""
        tmpl = self._new_cabinet_template(
            "M4 Test Filler Panel", "filler", 3.0, 34.5, 0.75, "M4-FP3"
        )
        self.assertFalse(self._normal_boms(tmpl))

        result = self.Bom._southbrook_generate_catalog_boms()
        self.assertGreaterEqual(result["created"], 1)

        boms = self._normal_boms(tmpl)
        self.assertEqual(len(boms), 1)
        self.assertTrue(boms[0].bom_line_ids)

    # ------------------------------------------------------------------
    # Idempotency
    # ------------------------------------------------------------------
    def test_idempotent_second_run_creates_nothing_new(self):
        tmpl = self._new_cabinet_template(
            "M4 Test Wall 30", "wall", 30.0, 30.0, 12.0, "M4-W30"
        )
        first = self.Bom._southbrook_generate_catalog_boms()
        self.assertGreaterEqual(first["created"], 1)
        boms_after_first = self._normal_boms(tmpl)
        self.assertEqual(len(boms_after_first), 1)

        second = self.Bom._southbrook_generate_catalog_boms()
        self.assertEqual(
            second["created"], 0,
            "second run must create nothing new — every template already "
            "has a BoM",
        )
        boms_after_second = self._normal_boms(tmpl)
        self.assertEqual(
            len(boms_after_second), 1,
            "must still be exactly one BoM — no duplicate created",
        )
        self.assertEqual(boms_after_first.id, boms_after_second.id)

    # ------------------------------------------------------------------
    # Conservatism — never touch an existing BoM
    # ------------------------------------------------------------------
    def test_never_touches_existing_bom(self):
        """A template that already has a (possibly empty stub) BoM must
        be left completely untouched — counted as skipped, no mutation."""
        tmpl = self._new_cabinet_template(
            "M4 Test Pre-existing Stub", "tall", 24.0, 84.0, 24.0,
            "M4-TALL-STUB",
        )
        stub = self.Bom.create({
            "product_tmpl_id": tmpl.id,
            "type": "normal",
            "product_qty": 1.0,
            "code": "PreexistingStub",
            "bom_line_ids": [],
        })
        self.Bom._southbrook_generate_catalog_boms()

        boms = self._normal_boms(tmpl)
        self.assertEqual(len(boms), 1, "no second BoM created")
        self.assertEqual(boms.id, stub.id, "the original stub BoM, untouched")
        self.assertFalse(
            boms.bom_line_ids,
            "generator must never mutate an existing BoM's lines",
        )
