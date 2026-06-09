# SPDX-License-Identifier: LGPL-3.0-only
"""Hardware-resolution tests — the bridge calls
env['southbrook.hardware.catalog'].resolve(...) and gets a deterministic
list back. These tests pin the contract for downstream Module 2 work
that appends hardware lines to the BoM."""
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "hardware_catalog", "resolution")
class TestHardwareResolution(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Catalog = cls.env["southbrook.hardware.catalog"]

    def _sku_set(self, picks):
        """Convert a list of (product, qty) tuples into a dict {sku: qty}
        for stable comparison."""
        return {p.x_marathon_sku: qty for p, qty in picks}

    # ------------------------------------------------------------------
    # Canonical carcass shapes
    # ------------------------------------------------------------------
    def test_base_1door_2shelf_soft_close(self):
        picks = self.Catalog.resolve(
            cabinet_family="base",
            door_count=1, drawer_count=0, shelf_count=2,
            soft_close=True,
        )
        skus = self._sku_set(picks)
        self.assertEqual(skus.get("BLM-110-SC"), 2, "Need 2 soft-close hinges for 1 door")
        self.assertEqual(skus.get("MRH-HDL-PUL128"), 1, "Need 1 handle per door")
        self.assertEqual(skus.get("MRH-DOORBUMP-CL"), 2, "Need 2 bumper dots per door")
        self.assertEqual(skus.get("MRH-SHLFPIN-5MM"), 8, "Need 4 pins per shelf × 2 shelves")
        self.assertEqual(skus.get("MRH-LVL-50"), 4, "Need 4 levelers per cabinet")
        self.assertEqual(skus.get("MRH-CAMLOCK-KIT"), 1)
        self.assertEqual(skus.get("MRH-MTGSCR-25PK"), 1)
        self.assertNotIn("BLM-110-NSC", skus, "Non-soft-close hinge must NOT appear")

    def test_base_2door_2shelf_soft_close(self):
        picks = self.Catalog.resolve(
            cabinet_family="base",
            door_count=2, drawer_count=0, shelf_count=2,
            soft_close=True,
        )
        skus = self._sku_set(picks)
        self.assertEqual(skus.get("BLM-110-SC"), 4, "2 hinges × 2 doors")
        self.assertEqual(skus.get("MRH-HDL-PUL128"), 2, "1 handle × 2 doors")
        self.assertEqual(skus.get("MRH-DOORBUMP-CL"), 4)

    def test_drawer_bank_3_drawer(self):
        picks = self.Catalog.resolve(
            cabinet_family="drawer",
            door_count=0, drawer_count=3, shelf_count=0,
            soft_close=True,
        )
        skus = self._sku_set(picks)
        self.assertEqual(skus.get("BLM-MOV-450"), 3, "1 slide pair per drawer")
        self.assertEqual(skus.get("MRH-HDL-PUL128"), 3, "1 handle per drawer")
        self.assertNotIn("BLM-110-SC", skus, "No hinges on a drawer bank")
        self.assertNotIn("MRH-SHLFPIN-5MM", skus, "No shelves in a drawer bank")

    def test_bifold_corner_no_soft_close(self):
        """Rule 4 (family → soft-close): bi-fold corner cabinets ship with
        non-soft-close hinges."""
        picks = self.Catalog.resolve(
            cabinet_family="corner",
            door_count=1, drawer_count=0, shelf_count=1,
            soft_close=False,
        )
        skus = self._sku_set(picks)
        self.assertEqual(skus.get("BLM-110-NSC"), 2, "Non-soft-close hinge for bi-fold")
        self.assertNotIn("BLM-110-SC", skus, "Soft-close hinge must NOT appear")

    def test_tall_pantry_extra_levelers(self):
        """Tall pantry doubles the leveler count — base 4 + family extra 4 = 8."""
        picks = self.Catalog.resolve(
            cabinet_family="tall",
            door_count=2, drawer_count=0, shelf_count=3,
            soft_close=True,
        )
        skus = self._sku_set(picks)
        self.assertEqual(skus.get("MRH-LVL-50"), 8, "Tall = 4 base + 4 family extra")
        self.assertEqual(skus.get("MRH-SHLFPIN-5MM"), 12, "4 × 3 shelves")

    def test_sink_base_extra_water_barrier(self):
        picks = self.Catalog.resolve(
            cabinet_family="sink",
            door_count=2, drawer_count=0, shelf_count=0,
            soft_close=True,
        )
        skus = self._sku_set(picks)
        self.assertEqual(
            skus.get("MRH-WATERBARRIER-1M"), 1,
            "Sink-base family must include water barrier",
        )

    def test_unknown_family_doesnt_crash(self):
        """An unfamiliar family should resolve to the common per_door /
        per_cabinet rules without a per_family bonus."""
        picks = self.Catalog.resolve(
            cabinet_family="bogus",
            door_count=1, drawer_count=0, shelf_count=1,
            soft_close=True,
        )
        skus = self._sku_set(picks)
        self.assertIn("BLM-110-SC", skus)
        self.assertNotIn("MRH-WATERBARRIER-1M", skus)

    # ------------------------------------------------------------------
    # Catalog-level guarantees
    # ------------------------------------------------------------------
    def test_resolution_picks_only_present_skus(self):
        """All SKUs referenced by the resolution map must actually exist
        in the catalog — no orphan references that would lead to silent
        skips at runtime."""
        Product = self.env["product.product"]
        hardware_map = self.Catalog._hardware_map()
        referenced_skus = set()
        for key in ("per_door_soft_close", "per_door", "per_drawer",
                    "per_shelf", "per_cabinet"):
            referenced_skus.update((hardware_map.get(key) or {}).keys())
        for fam_rules in (hardware_map.get("per_family") or {}).values():
            referenced_skus.update(fam_rules.keys())

        missing = []
        for sku in referenced_skus:
            if not Product.search_count([("x_marathon_sku", "=", sku)]):
                missing.append(sku)
        self.assertFalse(
            missing,
            f"hardware_map references SKUs absent from the catalog: {missing}",
        )
