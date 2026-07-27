# SPDX-License-Identifier: LGPL-3.0-only
"""P5 — Lossless, collision-proof auto-SKU.

The pre-audit SKU was SB-{Width3}-{Series3}-{Finish3}, which collided
when two configurations differed only in drawer construction (joinery
style) or in slide brand. The audit named both as load-bearing collision
cases.

The extended grammar appends short stable codes for:
  - drawer count       e.g. "3DR"
  - drawer construction e.g. "DT" (Dovetail)
  - slide model         e.g. "KS21SC" (King Slide K2832 21" Soft-Close)

Backward compat: the legacy 3-segment SKU is a strict prefix; configs
that don't expose drawers or slides still resolve to SB-24I-CON-WHI.

Tests assert:
  1. Two configs differing only in Drawer Construction produce
     different SKUs.
  2. Two configs differing only in Drawer Slide produce different SKUs.
  3. A small enumeration matrix produces 0 collisions across the
     dimensions the audit covers.
  4. The legacy 3-segment SKU is a prefix when no drawer / slide pick.
"""
from odoo.tests.common import TransactionCase, tagged

from odoo.addons.southbrook_configurator_ux.controllers.main import (
    SouthbrookConfiguratorAPI,
)


@tagged("post_install", "-at_install", "southbrook", "configurator_ux", "p5",
        "sku_lossless")
class TestP5SkuLossless(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.api = SouthbrookConfiguratorAPI()
        cls.Attribute = cls.env["product.attribute"]
        cls.AttributeValue = cls.env["product.attribute.value"]
        cls.Tmpl = cls.env["product.template"]
        cls.TmplAttrLine = cls.env["product.template.attribute.line"]
        cls.Session = cls.env["product.config.session"]

    def _attr(self, name, values):
        a = self.Attribute.create({"name": name, "create_variant": "always"})
        vals = [
            self.AttributeValue.create({"name": v, "attribute_id": a.id})
            for v in values
        ]
        return a, vals

    def _make_tmpl(self, attr_values_map):
        tmpl = self.Tmpl.create({
            "name": "P5 SKU test", "type": "consu", "is_storable": True,
        })
        captured = {}
        for attr_name, value_names in attr_values_map.items():
            attr, vals = self._attr(attr_name, value_names)
            self.TmplAttrLine.create({
                "product_tmpl_id": tmpl.id,
                "attribute_id": attr.id,
                "value_ids": [(6, 0, [v.id for v in vals])],
            })
            captured[attr_name] = vals
        tmpl._create_variant_ids()
        return tmpl, captured

    def _session_for(self, tmpl, picks):
        s = self.Session.create({
            "product_tmpl_id": tmpl.id, "user_id": self.env.user.id,
        })
        s.value_ids = [(6, 0, [v.id for v in picks])]
        return s

    # ------------------------------------------------------------------
    # Acceptance — drawer construction differences produce different SKUs
    # ------------------------------------------------------------------
    def test_drawer_construction_difference_distinguishes_sku(self):
        tmpl, vals = self._make_tmpl({
            "Width": ["24 in"],
            "Series": ["Contemporary"],
            "Finish": ["White"],
            "Drawer Construction": [
                "Dovetail Solid Hardwood",
                "5/8 in Plywood (Routed)",
            ],
        })
        s_dt = self._session_for(tmpl, [
            vals["Width"][0], vals["Series"][0], vals["Finish"][0],
            vals["Drawer Construction"][0],
        ])
        s_pr = self._session_for(tmpl, [
            vals["Width"][0], vals["Series"][0], vals["Finish"][0],
            vals["Drawer Construction"][1],
        ])
        self.assertNotEqual(
            self.api._compute_sku_from_session(s_dt),
            self.api._compute_sku_from_session(s_pr),
            "Dovetail vs Plywood must produce different SKUs (P5 collision)")

    # ------------------------------------------------------------------
    # Acceptance — slide brand differences produce different SKUs
    # ------------------------------------------------------------------
    def test_slide_brand_difference_distinguishes_sku(self):
        tmpl, vals = self._make_tmpl({
            "Width": ["24 in"],
            "Series": ["Contemporary"],
            "Finish": ["White"],
            "Drawer Construction": ["Dovetail Solid Hardwood"],
            "Drawer Slide": [
                "King Slide K2832 21\" Soft-Close",
                "Blum MOVENTO 450",
            ],
        })
        s_k = self._session_for(tmpl, [
            vals["Width"][0], vals["Series"][0], vals["Finish"][0],
            vals["Drawer Construction"][0], vals["Drawer Slide"][0],
        ])
        s_b = self._session_for(tmpl, [
            vals["Width"][0], vals["Series"][0], vals["Finish"][0],
            vals["Drawer Construction"][0], vals["Drawer Slide"][1],
        ])
        self.assertNotEqual(
            self.api._compute_sku_from_session(s_k),
            self.api._compute_sku_from_session(s_b),
            "King Slide vs MOVENTO must produce different SKUs (P5)")

    # ------------------------------------------------------------------
    # Acceptance — matrix of 0 collisions
    # ------------------------------------------------------------------
    def test_collision_matrix_zero_dupes(self):
        # 2 widths × 2 series × 2 finishes × 4 constructions × 5 slides = 160 cells.
        tmpl, vals = self._make_tmpl({
            "Width":   ["18 in", "24 in"],
            "Series":  ["Contemporary", "Elegance"],
            "Finish":  ["White", "Maple Stain"],
            "Drawer Construction": [
                "Melamine Particleboard", "5/8 in Plywood (Routed)",
                "Dovetail Solid Hardwood", "Metal (Blum Legrabox)",
            ],
            "Drawer Slide": [
                "King Slide K2832 21\" Soft-Close",
                "King Slide 3032 18\" Ball-Bearing",
                "Blum MOVENTO 450",
                "Hettich Actro 5D 500",
                "Salice Progressa+ (PR-602728)",
            ],
        })
        seen = {}
        for w in vals["Width"]:
            for s in vals["Series"]:
                for f in vals["Finish"]:
                    for c in vals["Drawer Construction"]:
                        for sl in vals["Drawer Slide"]:
                            session = self._session_for(
                                tmpl, [w, s, f, c, sl])
                            sku = self.api._compute_sku_from_session(session)
                            self.assertNotIn(
                                sku, seen,
                                f"collision: '{sku}' generated by "
                                f"({w.name},{s.name},{f.name},{c.name},"
                                f"{sl.name}) and "
                                f"({seen.get(sku)})")
                            seen[sku] = (
                                w.name, s.name, f.name, c.name, sl.name)
        self.assertEqual(len(seen), 2 * 2 * 2 * 4 * 5,
                         "expected 160 unique SKUs from the 160-cell matrix")

    # ------------------------------------------------------------------
    # Backwards-compat — legacy 3-segment SKU is a prefix
    # ------------------------------------------------------------------
    def test_legacy_3_segment_sku_is_prefix(self):
        # Template with only Width/Series/Finish — no drawer attributes.
        tmpl, vals = self._make_tmpl({
            "Width": ["24 in"],
            "Series": ["Contemporary"],
            "Finish": ["White"],
        })
        session = self._session_for(tmpl, [
            vals["Width"][0], vals["Series"][0], vals["Finish"][0],
        ])
        sku = self.api._compute_sku_from_session(session)
        # No extension segments when no drawer / slide picks.
        self.assertEqual(sku, "SB-24I-CON-WHI",
                         "no drawer pick -> legacy 3-segment SKU stands")
