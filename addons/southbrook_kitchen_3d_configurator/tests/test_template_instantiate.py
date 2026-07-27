# SPDX-License-Identifier: LGPL-3.0-only
"""Task 2 (kitchen templates) — resolver + action_instantiate.

Covers the instantiation contract from the spec:
- canonical design lines + poses from the EXISTING auto-arrange engine,
- appliance slots become design lines (dropdown width wins),
- unresolved slots land as VISIBLE placeholders (never dropped/substituted),
- no silent room growth (savepoint-atomic failure),
- module_width_in is a real parameter.
"""
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook",
        "southbrook_kitchen_3d_configurator", "kitchen_templates")
class TestTemplateInstantiate(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Tpl = cls.env["southbrook.kitchen.template"]
        Slot = cls.env["southbrook.kitchen.template.line"]
        base = cls.env.ref("southbrook_estimating.base_2dr")
        sink = cls.env.ref("southbrook_estimating.sink_base")
        wall = cls.env.ref("southbrook_estimating.wall_2dr")
        cls.tpl = Tpl.create({
            "name": "T2 Straight 10ft", "code": "T2-SW-10",
            "layout_shape": "straight",
            "default_room_width_in": 120.0, "default_room_depth_in": 96.0,
            "default_room_height_in": 96.0, "default_module_width_in": 24.0,
            "min_cabinet_count": 2,
        })
        Slot.create([
            {"template_id": cls.tpl.id, "slot_code": "SINK", "cabinet_type": "base",
             "wall": "back", "run_seq": 10, "product_id": sink.product_variant_id.id},
            {"template_id": cls.tpl.id, "slot_code": "B1", "cabinet_type": "base",
             "wall": "back", "run_seq": 20, "repeat_ok": True,
             "product_id": base.product_variant_id.id},
            {"template_id": cls.tpl.id, "slot_code": "RANGE",
             "cabinet_type": "appliance", "appliance_type": "range",
             "wall": "back", "run_seq": 30, "nominal_width_in": 30.0},
            {"template_id": cls.tpl.id, "slot_code": "W1", "cabinet_type": "wall",
             "wall": "back", "run_seq": 10,
             "product_id": wall.product_variant_id.id},
        ])

    def test_instantiate_creates_canonical_lines_with_engine_poses(self):
        design = self.tpl.action_instantiate()
        self.assertEqual(design.state, "configured")
        self.assertEqual(design.room_width_in, 120.0)  # template defaults, untouched
        canon = design.cabinet_line_ids.filtered(
            lambda l: l.layout_role == "canonical")
        self.assertGreaterEqual(len(canon), 4)
        xs = sorted(canon.filtered(lambda l: l.cabinet_type == "base")
                    .mapped("x_position_in"))
        self.assertEqual(len(xs), len(set(xs)),
                         "base run x positions must be distinct")

    def test_appliance_slot_becomes_design_line(self):
        design = self.tpl.action_instantiate(
            appliance_widths={"range": 36.0})
        appl = design.cabinet_line_ids.filtered(
            lambda l: l.cabinet_type == "appliance")
        self.assertEqual(len(appl), 1)
        self.assertEqual(appl.zone, "accessory")
        self.assertEqual(appl.width_in, 36.0)  # dropdown width wins
        self.assertEqual(appl.appliance_type, "range")
        self.assertIn("APPLIANCE", appl.position_label)

    def test_unresolved_slot_is_visible_placeholder(self):
        arch = self.env["southbrook.cabinet.archetype"].create({
            "code": "T2-NOPRODUCT", "name": "T2 ghost archetype",
            "collection": "other", "body_class": "base",
            "cabinet_type": "XX"})
        self.env["southbrook.kitchen.template.line"].create({
            "template_id": self.tpl.id, "slot_code": "GHOST",
            "cabinet_type": "base", "wall": "back", "run_seq": 40,
            "archetype_id": arch.id})
        design = self.tpl.action_instantiate()
        ghost = design.cabinet_line_ids.filtered(lambda l: l.is_unresolved)
        self.assertEqual(len(ghost), 1, "unresolved slot must land as a line")
        self.assertTrue(ghost.position_label.startswith("UNRESOLVED"))
        issues = design._check_production_ready()
        self.assertIn("UNRESOLVED_SLOT", [i["code"] for i in issues])

    def test_no_silent_room_growth(self):
        before = self.env["southbrook.kitchen.design"].search_count([])
        with self.assertRaises(UserError):
            self.tpl.action_instantiate(cabinet_count=40)  # can't fit 10 ft
        self.assertEqual(
            self.env["southbrook.kitchen.design"].search_count([]), before,
            "failed instantiation must not leave a half-built design")

    def test_module_width_parametric(self):
        design = self.tpl.action_instantiate(module_width_in=21.0)
        b1 = design.cabinet_line_ids.filtered(
            lambda l: l.template_slot_code == "B1")
        self.assertEqual(b1.width_in, 21.0)
