# SPDX-License-Identifier: LGPL-3.0-only
"""M4 — catalog-wide cabinet BoM generator.

Verifies mrp.bom._southbrook_generate_catalog_boms():
  * creates a BoM with real, non-empty bom_line_ids for a cabinet
    template that had none — both a boxed cabinet (panel raw materials +
    real Marathon hardware SKUs) and a pure filler/accessory (minimal
    sensible single-panel BoM, per the task's ambiguity guard),
  * is idempotent (re-running creates nothing new),
  * never mutates a template that already has a BoM (empty stub or not),
  * NEVER creates a BoM (empty or otherwise) for a config_ok=True
    (per-variant-configured) template — see the confirmed prod defect
    documented in mrp_bom_catalog.py's module docstring.

Also verifies mrp.bom._southbrook_cleanup_empty_catalog_boms():
  * deletes an empty, auto-seeded (KitchenAutoSeed-*/CatalogAutoBOM-*)
    stub BoM,
  * refuses to delete one referenced by an mrp.production,
  * never touches an empty BoM that isn't auto-seeded (hand-built),
  * is idempotent.
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

    # ------------------------------------------------------------------
    # config_ok=True — never create a BoM at all, empty or otherwise
    # ------------------------------------------------------------------
    def test_configurable_template_gets_no_bom_not_even_empty(self):
        """The confirmed prod defect: SB-BASE-1DR et al are config_ok=True
        catalog templates whose real per-cabinet dimensions are chosen
        per-VARIANT at config time. The template-level scalar dims are
        only ever a midpoint fallback, so the generator must hard-skip
        these — never build a BoM from that fallback, and CERTAINLY
        never leave an empty stub sitting on them (an empty template-
        level BoM is worse than none: any MO against any variant would
        find it and silently produce zero components)."""
        tmpl = self._new_cabinet_template(
            "M4 Test Configurable Base", "base", 24.0, 34.5, 24.0,
            "M4-CFG-BASE",
        )
        tmpl.write({"config_ok": True})
        self.assertFalse(self._normal_boms(tmpl))

        result = self.Bom._southbrook_generate_catalog_boms()

        self.assertFalse(
            self._normal_boms(tmpl),
            "config_ok template must end up with NO BoM at all — not "
            "an empty one",
        )
        self.assertGreaterEqual(result["skipped_configurable"], 1)
        # Not double-counted as an "empty build" skip — it was never
        # attempted.
        self.assertEqual(
            len([d for d in result["details"] if d["template_id"] == tmpl.id]),
            0,
        )

    def test_configurable_accessory_also_gets_no_bom(self):
        """Same guard for the config_ok accessory family (SB-ACCESSORY),
        which would otherwise take the single-panel minimal-BoM branch
        and materialize a (wrong, midpoint-dimensioned) line."""
        tmpl = self._new_cabinet_template(
            "M4 Test Configurable Accessory", "panel", 3.0, 34.5, 0.75,
            "M4-CFG-ACCESSORY",
        )
        tmpl.write({"config_ok": True})

        self.Bom._southbrook_generate_catalog_boms()

        self.assertFalse(self._normal_boms(tmpl))

    # ------------------------------------------------------------------
    # Cleanup — remove empty auto-seeded stubs, refuse in-use ones
    # ------------------------------------------------------------------
    def _new_empty_stub(self, tmpl, code):
        return self.Bom.create({
            "product_tmpl_id": tmpl.id,
            "type": "normal",
            "product_qty": 1.0,
            "code": code,
            "bom_line_ids": [],
        })

    def test_cleanup_deletes_empty_stub_but_refuses_in_use_one(self):
        tmpl_orphan = self._new_cabinet_template(
            "M4 Test Orphan Empty Stub", "base", 24.0, 34.5, 24.0,
            "M4-CLEANUP-ORPHAN",
        )
        orphan_stub = self._new_empty_stub(
            tmpl_orphan, "KitchenAutoSeed-M4-CLEANUP-ORPHAN"
        )

        tmpl_inuse = self._new_cabinet_template(
            "M4 Test In-Use Empty Stub", "base", 24.0, 34.5, 24.0,
            "M4-CLEANUP-INUSE",
        )
        inuse_stub = self._new_empty_stub(
            tmpl_inuse, "CatalogAutoBOM-M4-CLEANUP-INUSE"
        )
        variant = tmpl_inuse.product_variant_ids[:1]
        self.env["mrp.production"].create({
            "product_id": variant.id,
            "product_qty": 1.0,
            "bom_id": inuse_stub.id,
        })

        result = self.Bom._southbrook_cleanup_empty_catalog_boms()

        self.assertFalse(orphan_stub.exists(), "orphaned empty stub deleted")
        self.assertTrue(
            inuse_stub.exists(),
            "empty stub referenced by an mrp.production must be refused",
        )
        self.assertEqual(result["deleted"], 1)
        self.assertEqual(len(result["refused_in_use"]), 1)
        self.assertEqual(result["refused_in_use"][0]["bom_id"], inuse_stub.id)

    def test_cleanup_never_deletes_non_autoseeded_empty_bom(self):
        """An empty BoM without one of the two known auto-seed code
        prefixes is presumed hand-built (or Hermes-applied) and must
        never be touched, even though it's empty."""
        tmpl = self._new_cabinet_template(
            "M4 Test Hand-Built Empty Stub", "base", 24.0, 34.5, 24.0,
            "M4-CLEANUP-HANDBUILT",
        )
        hand_built = self._new_empty_stub(tmpl, "HandBuiltPlaceholder")

        result = self.Bom._southbrook_cleanup_empty_catalog_boms()

        self.assertTrue(hand_built.exists())
        self.assertEqual(result["deleted"], 0)
        self.assertEqual(result["refused_in_use"], [])

    def test_cleanup_idempotent(self):
        tmpl = self._new_cabinet_template(
            "M4 Test Cleanup Idempotent", "base", 24.0, 34.5, 24.0,
            "M4-CLEANUP-IDEMPOTENT",
        )
        self._new_empty_stub(tmpl, "KitchenAutoSeed-M4-CLEANUP-IDEMPOTENT")

        first = self.Bom._southbrook_cleanup_empty_catalog_boms()
        self.assertEqual(first["deleted"], 1)

        second = self.Bom._southbrook_cleanup_empty_catalog_boms()
        self.assertEqual(
            second["deleted"], 0,
            "second run must find nothing left to delete",
        )
