# SPDX-License-Identifier: LGPL-3.0-only
"""Nesting interface round-trip — sb.cutlist exports a JSON envelope and
accepts back a result that flips state to 'nested'. The interface
contract is what Module 4 ships; the cutting/nesting division producer
is a separate deliverable."""
import json

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged

from southbrook_dims import panel_cut_list


@tagged("post_install", "-at_install", "southbrook", "kitchen_mrp", "nesting")
class TestNestingIO(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Cutlist = cls.env["sb.cutlist"]
        cls.Product = cls.env["product.product"]

    def _new_cutlist(self):
        product = self.Product.create({
            "name": "Cutlist for nest", "type": "consu", "is_storable": True,
        })
        self.env["mrp.bom"].create({
            "product_tmpl_id": product.product_tmpl_id.id, "product_qty": 1.0,
        })
        mo = self.env["mrp.production"].create({
            "product_id": product.id, "product_qty": 1.0,
        })
        cutlist = self.Cutlist.create({"mo_id": mo.id})
        panel_dict = panel_cut_list(600, 720, 580, family="base", door_count=2)
        self.Cutlist.generate_lines_from_panel_dict(cutlist, panel_dict)
        return cutlist

    def test_envelope_is_deterministic_and_versioned(self):
        cutlist = self._new_cutlist()
        envelope = cutlist.to_nesting_envelope()
        self.assertEqual(envelope["schema"], "southbrook.nesting.v1")
        self.assertEqual(envelope["cutlist_id"], cutlist.id)
        # Same line count, same dims.
        self.assertEqual(len(envelope["panels"]), len(cutlist.line_ids))
        for panel in envelope["panels"]:
            self.assertIn("panel_name", panel)
            self.assertIn("length_mm", panel)
            self.assertIn("width_mm", panel)
            self.assertIn("thickness_mm", panel)
            self.assertIn("edge_banding", panel)
            self.assertIsInstance(panel["edge_banding"], dict)

    def test_envelope_is_json_round_trippable(self):
        cutlist = self._new_cutlist()
        envelope = cutlist.to_nesting_envelope()
        # If json.dumps + json.loads survives, the envelope is wire-safe.
        wire = json.dumps(envelope)
        recovered = json.loads(wire)
        self.assertEqual(recovered["cutlist_id"], cutlist.id)

    def test_result_flips_state_to_nested(self):
        cutlist = self._new_cutlist()
        result = {
            "schema": "southbrook.nesting.v1",
            "cutlist_id": cutlist.id,
            "sheets_used": 2,
            "yield_pct": 0.91,
            "waste_pct": 0.09,
        }
        cutlist.from_nesting_result(result)
        self.assertEqual(cutlist.state, "nested")
        self.assertEqual(json.loads(cutlist.nesting_result_json)["sheets_used"], 2)

    def test_wrong_schema_rejects(self):
        cutlist = self._new_cutlist()
        with self.assertRaises(UserError):
            cutlist.from_nesting_result({"schema": "not.our.schema"})

    def test_non_dict_payload_rejects(self):
        cutlist = self._new_cutlist()
        with self.assertRaises(UserError):
            cutlist.from_nesting_result("a string, not a dict")
