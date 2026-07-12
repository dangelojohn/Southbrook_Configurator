# SPDX-License-Identifier: LGPL-3.0-only
"""Persistence-level invariants for design.action_auto_arrange().

Auto-arrange is a pure transformation of the customer's CANONICAL selection
into a derived arranged layout. These tests pin the lifecycle guarantees the
geometry tests can't see: idempotence, no canonical loss, no derived
accumulation, atomic rollback, and a mirror that reflects only visible lines.
"""
from unittest.mock import patch

from odoo.tests.common import TransactionCase
from odoo.addons.southbrook_estimating.models import kitchen_layout_engine as E


class TestAutoArrangeService(TransactionCase):

    def setUp(self):
        super().setUp()
        Template = self.env["product.template"]
        for code, name, price in [("SB-CORNER", "Corner Base", 625.0),
                                  ("SB-WALL-CORNER", "Corner Wall", 295.0)]:
            if not Template.search([("default_code", "=", code)], limit=1):
                Template.create({"name": name, "default_code": code,
                                 "list_price": price})
        self.base_prod = self.env["product.product"].create(
            {"name": "Test Base 24", "default_code": "ZZ-TEST-B24",
             "list_price": 200.0})
        self.partner = self.env["res.partner"].create({"name": "AA Test"})

    def _make_design(self, n, width_in=24.0, room_w=140.0, room_d=200.0):
        design = self.env["southbrook.kitchen.design"].create({
            "name": "AA test", "partner_id": self.partner.id,
            "room_width_in": room_w, "room_depth_in": room_d,
            "room_height_in": 96.0, "state": "draft"})
        Line = self.env["southbrook.kitchen.design.line"]
        for i in range(n):
            Line.create({
                "design_id": design.id, "product_id": self.base_prod.id,
                "quantity": 1, "price_unit": 200.0, "cabinet_type": "base",
                "width_in": width_in, "height_in": 34.5, "depth_in": 24.0,
                "sequence": i * 10, "origin": "configurator",
                "layout_key": "aa-%d" % i})
        return design

    def _active_snapshot(self, design):
        return sorted(
            (l.layout_key, l.product_id.default_code, round(l.x_position_in, 2),
             round(l.z_position_in, 2), l.rotation_deg, l.wall, l.layout_role)
            for l in design.cabinet_line_ids)

    def _all_lines(self, design):
        return design.with_context(active_test=False).cabinet_line_ids

    def test_first_run_produces_L(self):
        d = self._make_design(10)
        res = d.action_auto_arrange()
        self.assertEqual(res["inserted"], 1)
        self.assertEqual(res["removed"], 2)
        corners = d.cabinet_line_ids.filtered(lambda l: l.layout_role == "derived")
        self.assertEqual(len(corners), 1)
        self.assertEqual(corners.product_id.product_tmpl_id.default_code,
                         "SB-CORNER")

    def test_idempotent_active_lines(self):
        d = self._make_design(10)
        d.action_auto_arrange()
        snap = self._active_snapshot(d)
        for _ in range(4):                 # run 4 more times → identical
            d.action_auto_arrange()
            self.assertEqual(self._active_snapshot(d), snap)

    def test_active_count_stable_after_second_run(self):
        d = self._make_design(10)
        d.action_auto_arrange()
        n1 = len(d.cabinet_line_ids)
        d.action_auto_arrange()
        self.assertEqual(len(d.cabinet_line_ids), n1)   # 8 canonical + 1 corner

    def test_no_canonical_line_is_ever_lost(self):
        d = self._make_design(10)
        canon = lambda: len(self._all_lines(d).filtered(
            lambda l: l.layout_role == "canonical"))
        self.assertEqual(canon(), 10)
        for _ in range(3):
            d.action_auto_arrange()
            self.assertEqual(canon(), 10)   # superseded, never deleted

    def test_derived_artifacts_never_accumulate(self):
        d = self._make_design(10)
        for _ in range(5):
            d.action_auto_arrange()
            derived = self._all_lines(d).filtered(
                lambda l: l.layout_role == "derived")
            self.assertEqual(len(derived), 1)   # exactly one, every run

    def test_mirror_reflects_only_visible_lines(self):
        d = self._make_design(10)
        d.action_auto_arrange()
        d.action_auto_arrange()             # twice — catch mirror duplication
        self.assertTrue(d.sale_order_id)
        so_lines = d.sale_order_id.order_line
        # exactly one corner SO line (no duplication across runs)
        corner_so = so_lines.filtered(
            lambda l: l.product_id.product_tmpl_id.default_code == "SB-CORNER")
        self.assertEqual(len(corner_so), 1)
        # SO line count == visible (active) configurator design lines
        visible = d.cabinet_line_ids.filtered(lambda l: l.origin == "configurator")
        self.assertEqual(len(so_lines), len(visible))

    def test_rollback_on_injected_failure_restores_state(self):
        d = self._make_design(10)
        d.action_auto_arrange()             # arrange once
        before = self._active_snapshot(d)
        Recon = type(self.env["southbrook.design.reconcile"])
        with patch.object(Recon, "_reconcile_one",
                          side_effect=ValueError("boom")):
            with self.assertRaises(ValueError):
                d.action_auto_arrange()
        # savepoint rolled the whole re-arrange back → unchanged
        self.assertEqual(self._active_snapshot(d), before)

    def test_capacity_exceeded_raises_and_rolls_back(self):
        d = self._make_design(25, room_w=96.0, room_d=96.0)
        before = self._active_snapshot(d)
        with self.assertRaises(E.LayoutCapacityExceeded):
            d.action_auto_arrange()
        self.assertEqual(self._active_snapshot(d), before)
