# SPDX-License-Identifier: LGPL-3.0-only
"""southbrook.placement.rule — M1 rules-as-data layer
(docs/research/corner-engine/09-rule-engine-spec.md §6-7).

Covers: the hand-rolled payload constraint (junction-anchor required
keys, min-leg >= leg, host_leg enum), engine_dicts()'s plain-dict
bridge shape, and that the 3 M1 seed rules land correctly via the
data/placement_rules.xml -> _seed_default_rules() install path.
"""
from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase, tagged


_VALID_JUNCTION_PAYLOAD = {
    "leg_x_mm": 914.0,
    "leg_z_mm": 914.0,
    "height_mm": 876.0,
    "min_leg_x_mm": 1143.0,
    "min_leg_z_mm": 1143.0,
}


@tagged("post_install", "-at_install", "southbrook", "southbrook_placement_rule")
class TestPlacementRule(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Rule = cls.env["southbrook.placement.rule"]
        cls.tmpl = cls.env.ref("southbrook_estimating.corner")

    def test_constraint_rejects_payload_missing_leg_x_mm(self):
        payload = dict(_VALID_JUNCTION_PAYLOAD)
        del payload["leg_x_mm"]
        with self.assertRaises(ValidationError):
            self.Rule.create({
                "name": "Missing leg_x_mm",
                "product_tmpl_id": self.tmpl.id,
                "corner_type_id": "diagonal-corner-lazy-susan",
                "anchor_class": "junction",
                "tier": "base",
                "payload": payload,
            })

    def test_constraint_rejects_invalid_host_leg(self):
        payload = dict(_VALID_JUNCTION_PAYLOAD, host_leg="q")
        with self.assertRaises(ValidationError):
            self.Rule.create({
                "name": "Bad host_leg",
                "product_tmpl_id": self.tmpl.id,
                "corner_type_id": "diagonal-corner-lazy-susan",
                "anchor_class": "junction",
                "tier": "base",
                "payload": payload,
            })

    def test_constraint_rejects_min_leg_below_leg(self):
        payload = dict(_VALID_JUNCTION_PAYLOAD, min_leg_x_mm=500.0)
        with self.assertRaises(ValidationError):
            self.Rule.create({
                "name": "min_leg_x_mm too small",
                "product_tmpl_id": self.tmpl.id,
                "corner_type_id": "diagonal-corner-lazy-susan",
                "anchor_class": "junction",
                "tier": "base",
                "payload": payload,
            })

    def test_constraint_accepts_valid_junction_payload(self):
        rule = self.Rule.create({
            "name": "Valid junction rule",
            "product_tmpl_id": self.tmpl.id,
            "corner_type_id": "diagonal-corner-lazy-susan",
            "anchor_class": "junction",
            "tier": "base",
            "payload": _VALID_JUNCTION_PAYLOAD,
        })
        self.assertTrue(rule.id)
        self.assertEqual(rule.payload["leg_x_mm"], 914.0)

    def test_constraint_skips_non_junction_anchor_classes(self):
        # anchor_class=free carries no required junction keys — an
        # empty-ish payload must not raise.
        rule = self.Rule.create({
            "name": "Free-anchored, no junction keys required",
            "product_tmpl_id": self.tmpl.id,
            "anchor_class": "free",
            "tier": "base",
            "payload": {"note": "island cabinet"},
        })
        self.assertTrue(rule.id)

    def test_engine_dicts_returns_sku_sequence_and_payload_keys(self):
        rule = self.Rule.create({
            "name": "engine_dicts fixture",
            "product_tmpl_id": self.tmpl.id,
            "corner_type_id": "diagonal-corner-lazy-susan",
            "anchor_class": "junction",
            "tier": "base",
            "sequence": 42,
            "payload": _VALID_JUNCTION_PAYLOAD,
        })
        dicts = rule.engine_dicts()
        self.assertEqual(len(dicts), 1)
        d = dicts[0]
        self.assertEqual(d["rule_id"], "spr-%d" % rule.id)
        self.assertEqual(d["sku"], self.tmpl.default_code)
        self.assertEqual(d["sku"], "SB-CORNER")
        self.assertEqual(d["tier"], "base")
        self.assertEqual(d["sequence"], 42)
        for key in ("leg_x_mm", "leg_z_mm", "height_mm",
                    "min_leg_x_mm", "min_leg_z_mm"):
            self.assertEqual(d[key], _VALID_JUNCTION_PAYLOAD[key])

    def test_seeded_susan_base_corner_rule(self):
        rule = self.Rule.search([
            ("corner_type_id", "=", "diagonal-corner-lazy-susan"),
            ("tier", "=", "base"),
        ], limit=1)
        self.assertTrue(rule, "seed rule 1 (diagonal susan) missing")
        self.assertEqual(rule.sequence, 10)
        self.assertEqual(rule.anchor_class, "junction")
        self.assertEqual(rule.payload["leg_x_mm"], 914.0)
        self.assertEqual(rule.payload["leg_z_mm"], 914.0)
        self.assertEqual(rule.payload["height_mm"], 876.0)
        self.assertEqual(rule.payload["min_leg_x_mm"], 1143.0)
        self.assertEqual(rule.payload["min_leg_z_mm"], 1143.0)

    def test_seeded_blind_base_corner_rule(self):
        rule = self.Rule.search([
            ("corner_type_id", "=", "blind-corner-basic"),
            ("tier", "=", "base"),
        ], limit=1)
        self.assertTrue(rule, "seed rule 2 (blind corner) missing")
        self.assertEqual(rule.sequence, 20)
        self.assertEqual(rule.anchor_class, "junction")
        self.assertEqual(rule.payload["leg_x_mm"], 610.0)
        self.assertEqual(rule.payload["leg_z_mm"], 1143.0)
        self.assertEqual(rule.payload["min_leg_x_mm"], 610.0)
        self.assertEqual(rule.payload["min_leg_z_mm"], 1372.0)
        self.assertEqual(rule.payload["host_leg"], "z")

    def test_seeded_pie_cut_wall_corner_rule(self):
        rule = self.Rule.search([
            ("corner_type_id", "=", "pie-cut-wall-corner"),
            ("tier", "=", "wall"),
        ], limit=1)
        self.assertTrue(rule, "seed rule 3 (pie-cut wall corner) missing")
        self.assertEqual(rule.sequence, 10)
        self.assertEqual(rule.anchor_class, "junction")
        self.assertEqual(rule.payload["leg_x_mm"], 610.0)
        self.assertEqual(rule.payload["leg_z_mm"], 610.0)
        self.assertEqual(rule.payload["height_mm"], 762.0)
        self.assertEqual(rule.payload["min_leg_x_mm"], 762.0)
        self.assertEqual(rule.payload["min_leg_z_mm"], 762.0)

    def test_seed_is_idempotent(self):
        # Re-running the seeder (as -u would) must not create duplicates.
        before = self.Rule.search_count([])
        self.Rule._seed_default_rules()
        after = self.Rule.search_count([])
        self.assertEqual(before, after)
