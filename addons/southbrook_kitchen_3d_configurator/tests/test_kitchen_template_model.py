# SPDX-License-Identifier: LGPL-3.0-only
"""Kitchen Templates T1 — southbrook.kitchen.template model regression pins.

Covers: slot create + zone default from cabinet_type, is_appliance_slot
compute, the layout_shape lexicon being reused verbatim from
southbrook.room (never a parallel enum), and the unique-code constraint
via models.Constraint (v19 idiom, not _sql_constraints).
"""
from psycopg2.errors import UniqueViolation

from odoo.tests import TransactionCase, tagged
from odoo.tools import mute_logger


@tagged("post_install", "-at_install", "southbrook",
        "southbrook_kitchen_3d_configurator", "kitchen_templates")
class TestKitchenTemplateModel(TransactionCase):

    def _mk_template(self, code, shape="straight"):
        return self.env["southbrook.kitchen.template"].create({
            "name": "T1 fixture %s" % code,
            "code": code,
            "layout_shape": shape,
            "default_room_width_in": 120.0,
            "default_room_depth_in": 96.0,
            "default_room_height_in": 96.0,
            "default_module_width_in": 24.0,
            "min_cabinet_count": 3,
            "max_cabinet_count": 8,
        })

    def test_template_and_slot_create(self):
        tpl = self._mk_template("T1-SW-A")
        slot = self.env["southbrook.kitchen.template.line"].create({
            "template_id": tpl.id,
            "slot_code": "SINK",
            "cabinet_type": "base",
            "wall": "back",
            "run_seq": 10,
            "nominal_width_in": 0.0,   # 0 = takes module width
        })
        self.assertEqual(slot.zone, "base_run")   # zone defaults from type
        self.assertFalse(slot.is_appliance_slot)
        appl = self.env["southbrook.kitchen.template.line"].create({
            "template_id": tpl.id,
            "slot_code": "RANGE",
            "cabinet_type": "appliance",
            "appliance_type": "range",
            "wall": "back",
            "run_seq": 20,
            "nominal_width_in": 30.0,
        })
        self.assertTrue(appl.is_appliance_slot)
        self.assertEqual(appl.zone, "accessory")

    def test_shape_lexicon_is_the_room_lexicon(self):
        tpl = self._mk_template("T1-SW-B")
        room_keys = {k for k, _ in
                     self.env["southbrook.room"]._fields["layout_shape"].selection}
        tpl_keys = {k for k, _ in tpl._fields["layout_shape"].selection}
        self.assertEqual(tpl_keys, room_keys,
                          "template layout_shape must reuse _LAYOUT_SHAPES verbatim")

    @mute_logger("odoo.sql_db")
    def test_code_unique(self):
        self._mk_template("T1-DUP")
        with self.assertRaises(UniqueViolation), self.env.cr.savepoint():
            self._mk_template("T1-DUP")
