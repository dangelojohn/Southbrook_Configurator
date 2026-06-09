# SPDX-License-Identifier: LGPL-3.0-only
"""sb.cutlist generation — turn a shared.southbrook_dims panel_cut_list
into sb.cutlist.line rows. The most important contract: toe_kick is
NEVER emitted as a cutlist line (its panel_dict value is a metadata
dict, not a panel tuple)."""
from odoo.tests.common import TransactionCase, tagged

from southbrook_dims import panel_cut_list


@tagged("post_install", "-at_install", "southbrook", "kitchen_mrp", "cutlist")
class TestCutlistGeneration(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Cutlist = cls.env["sb.cutlist"]
        cls.Product = cls.env["product.product"]

    def _new_mo(self, name="G1 test cabinet"):
        product = self.Product.create({
            "name": name, "type": "consu", "is_storable": True,
        })
        self.env["mrp.bom"].create({
            "product_tmpl_id": product.product_tmpl_id.id,
            "product_qty": 1.0,
        })
        return self.env["mrp.production"].create({
            "product_id": product.id, "product_qty": 1.0,
        })

    def test_base_cabinet_emits_six_panels_plus_door(self):
        """600x720x580 base 2-door 2-shelf must produce:
        side_L, side_R, top, bottom, back, adjustable_shelf, door
        = 7 line types. shelf qty = 2."""
        mo = self._new_mo()
        cutlist = self.Cutlist.create({"mo_id": mo.id})
        panel_dict = panel_cut_list(600, 720, 580, family="base", door_count=2)
        self.Cutlist.generate_lines_from_panel_dict(cutlist, panel_dict)

        line_panels = sorted(cutlist.line_ids.mapped("panel_name"))
        self.assertEqual(line_panels, [
            "adjustable_shelf", "back", "bottom", "door",
            "side_L", "side_R", "top",
        ])
        # Shelf qty inherits from panel_cut_list shelf_count (2 for 720mm).
        shelf_line = cutlist.line_ids.filtered(
            lambda l: l.panel_name == "adjustable_shelf"
        )
        self.assertEqual(shelf_line.qty, 2,
                         "Adjustable shelf qty must match panel_dict shelf_count")

    def test_toe_kick_never_emitted_as_line(self):
        """The single most important enforcement contract — toe_kick is
        integrated into the side panels, NEVER a separate cut. Any
        future change to shared.southbrook_dims that turns toe_kick
        into a tuple instead of metadata fails the generator hard
        (UserError on unexpected shape) — exactly what we want."""
        mo = self._new_mo()
        cutlist = self.Cutlist.create({"mo_id": mo.id})
        panel_dict = panel_cut_list(600, 720, 580, family="base", door_count=1)
        self.Cutlist.generate_lines_from_panel_dict(cutlist, panel_dict)

        for ln in cutlist.line_ids:
            self.assertNotEqual(
                ln.panel_name, "toe_kick",
                "toe_kick must NEVER be emitted as a cutlist line",
            )

    def test_dimensions_match_shared_panel_dict_exactly(self):
        """Every emitted line's (length, width, thickness) must equal the
        corresponding tuple from panel_cut_list. No rounding, no drift."""
        mo = self._new_mo()
        cutlist = self.Cutlist.create({"mo_id": mo.id})
        panel_dict = panel_cut_list(600, 720, 580, family="base", door_count=2)
        self.Cutlist.generate_lines_from_panel_dict(cutlist, panel_dict)

        by_name = {ln.panel_name: ln for ln in cutlist.line_ids}
        for key in ("side_L", "side_R", "top", "bottom", "back", "door"):
            expected = panel_dict[key]
            line = by_name[key]
            self.assertEqual(
                (line.length_mm, line.width_mm, line.thickness_mm),
                expected,
                f"{key} dimensions drifted",
            )

    def test_substrate_defaults_per_panel(self):
        mo = self._new_mo()
        cutlist = self.Cutlist.create({"mo_id": mo.id})
        panel_dict = panel_cut_list(600, 720, 580, family="base", door_count=1)
        self.Cutlist.generate_lines_from_panel_dict(cutlist, panel_dict)

        by_name = {ln.panel_name: ln for ln in cutlist.line_ids}
        self.assertEqual(by_name["back"].substrate, "hardboard_1_4",
                         "Back panel must default to 1/4\" hardboard")
        self.assertEqual(by_name["door"].substrate, "ply_3_4",
                         "Door must default to 3/4\" plywood")
        self.assertEqual(by_name["side_L"].substrate, "melamine_white_5_8")

    def test_door_count_zero_skips_door(self):
        """When door_count == 0, shared.southbrook_dims returns None for
        the door key; the generator must skip rather than crash."""
        mo = self._new_mo()
        cutlist = self.Cutlist.create({"mo_id": mo.id})
        panel_dict = panel_cut_list(600, 720, 580, family="base", door_count=0)
        self.Cutlist.generate_lines_from_panel_dict(cutlist, panel_dict)

        self.assertFalse(
            any(ln.panel_name == "door" for ln in cutlist.line_ids),
            "No door line should be emitted when door_count is 0",
        )

    def test_short_cabinet_only_one_shelf(self):
        """600x600x580 cabinet — shelf_count=1 per shared.southbrook_dims."""
        mo = self._new_mo()
        cutlist = self.Cutlist.create({"mo_id": mo.id})
        panel_dict = panel_cut_list(600, 600, 580, family="base", door_count=1)
        self.Cutlist.generate_lines_from_panel_dict(cutlist, panel_dict)

        shelf = cutlist.line_ids.filtered(
            lambda l: l.panel_name == "adjustable_shelf"
        )
        self.assertEqual(shelf.qty, 1)
