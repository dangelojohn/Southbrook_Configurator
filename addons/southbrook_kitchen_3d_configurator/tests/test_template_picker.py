# SPDX-License-Identifier: LGPL-3.0-only
"""Templates T3 — the four-dropdown picker + thumbnails + compat."""
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook",
        "southbrook_kitchen_3d_configurator", "kitchen_templates")
class TestTemplatePicker(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Tpl = cls.env["southbrook.kitchen.template"]
        Slot = cls.env["southbrook.kitchen.template.line"]
        base = cls.env.ref("southbrook_estimating.base_2dr")
        sink = cls.env.ref("southbrook_estimating.sink_base")
        cls.tpl = Tpl.create({
            "name": "T3 Picker 10ft", "code": "T3-SW-10",
            "layout_shape": "straight",
            "default_room_width_in": 120.0, "default_room_depth_in": 96.0,
            "default_room_height_in": 96.0, "default_module_width_in": 24.0,
        })
        Slot.create([
            {"template_id": cls.tpl.id, "slot_code": "SINK",
             "cabinet_type": "base", "wall": "back", "run_seq": 10,
             "product_id": sink.product_variant_id.id},
            {"template_id": cls.tpl.id, "slot_code": "B1",
             "cabinet_type": "base", "wall": "back", "run_seq": 20,
             "repeat_ok": True, "product_id": base.product_variant_id.id},
            {"template_id": cls.tpl.id, "slot_code": "RANGE",
             "cabinet_type": "appliance", "appliance_type": "range",
             "wall": "back", "run_seq": 30, "nominal_width_in": 30.0},
        ])

    def test_confirm_instantiates_and_opens_configurator(self):
        picker = self.env["kitchen.design.template.picker"].create({
            "template_id": self.tpl.id,
            "module_width_in": "24",
            "range_width_in": "36",
        })
        action = picker.action_create()
        # action_open_configurator returns the client action for the canvas
        self.assertEqual(action.get("tag"), "southbrook_kitchen_configurator")
        design = self.env["southbrook.kitchen.design"].search(
            [], order="id desc", limit=1)
        self.assertTrue(design.cabinet_line_ids)
        appl = design.cabinet_line_ids.filtered(
            lambda l: l.cabinet_type == "appliance")
        self.assertEqual(appl.width_in, 36.0)

    def test_count_is_live_bounded(self):
        picker = self.env["kitchen.design.template.picker"].create({
            "template_id": self.tpl.id, "module_width_in": "24"})
        self.assertGreater(picker.count_max, 0)
        picker.cabinet_count = picker.count_max + 5
        picker._onchange_parametrics()
        self.assertLessEqual(picker.cabinet_count, picker.count_max)

    def test_empty_preset_creates_plain_draft(self):
        # legacy-compat: 'empty' = plain draft design, no template consulted
        picker = self.env["kitchen.design.template.picker"].create(
            {"preset": "empty"})
        action = picker.action_create()
        self.assertEqual(action.get("tag"), "southbrook_kitchen_configurator")
        design = self.env["southbrook.kitchen.design"].search(
            [], order="id desc", limit=1)
        self.assertFalse(design.cabinet_line_ids)
        self.assertEqual(design.state, "draft")

    def test_thumbnail_svg_generated(self):
        svg = self.tpl._generate_thumbnail_svg()
        self.assertTrue(svg.startswith("<svg"))
        self.assertIn("<rect", svg)
