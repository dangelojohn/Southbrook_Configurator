# SPDX-License-Identifier: LGPL-3.0-only
"""P1 — auto-emit cutlist + production package on action_confirm.

Two flag positions:
  - OFF (default): action_confirm behavior is byte-identical to the
    pre-P1 baseline (no production package, no cutlist).
  - ON: a configured kitchen line emits exactly one sb.production.package
    with a non-empty cutlist; the MI Missing-cutlist blocker would
    therefore have nothing to fire on (asserted indirectly here; the
    direct MI assertion lives in test_p3 once P3 lands).
"""
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "premium_orchestration",
        "p1", "auto_emit_cutlist")
class TestP1AutoEmitCutlist(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create({
            "name": "P1 Auto-Emit Test Customer",
        })
        cls.project = cls.env["project.project"].create({
            "name": "P1 Kitchen Jobs",
        })
        cls.env["ir.config_parameter"].sudo().set_param(
            "southbrook_premium.default_kitchen_project_id",
            str(cls.project.id),
        )
        cls.kitchen_product = cls.env["product.product"].create({
            "name": "Base Cabinet, 3-Drawer, Shaker Maple, 24W",
            "type": "consu",
            "is_storable": True,
        })

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _set_flag(self, value):
        self.env["ir.config_parameter"].sudo().set_param(
            "southbrook_premium_orchestration.auto_emit_cutlist", value,
        )

    def _make_confirmed_order(self):
        so = self.env["sale.order"].create({
            "partner_id": self.partner.id,
            "order_line": [(0, 0, {
                "product_id": self.kitchen_product.id,
                "product_uom_qty": 1.0,
            })],
        })
        line = so.order_line[0]
        # Manual MO link so build_from_order_line resolves cleanly without
        # a full BoM setup (BoM-bound MOs are a different code path tested
        # in test_full_flow.py).
        self.env["mrp.production"].create({
            "product_id": self.kitchen_product.id,
            "product_qty": 1.0,
            "sale_line_id": line.id,
            "origin": so.name,
        })
        so.action_confirm()
        return so, line

    # ------------------------------------------------------------------
    # Flag OFF (default) — behavior is byte-identical to baseline
    # ------------------------------------------------------------------
    def test_flag_off_emits_no_package(self):
        # Explicitly set the flag off to neutralise any prior test that
        # might have toggled it on for the same DB session.
        self._set_flag("False")
        so, line = self._make_confirmed_order()
        pkg_count = self.env["sb.production.package"].search_count(
            [("sale_order_line_id", "=", line.id)])
        self.assertEqual(
            pkg_count, 0,
            "with the flag OFF the auto-emit must be byte-identical "
            "to the pre-P1 baseline (no package emitted)")
        # Spine creation still happens — that's the legacy path.
        self.assertTrue(so.x_premium_orchestration_managed,
                        "spine creation is unrelated to P1; still on")

    # ------------------------------------------------------------------
    # Flag ON — package emitted, idempotent on re-confirm
    # ------------------------------------------------------------------
    def test_flag_on_emits_one_package(self):
        self._set_flag("True")
        so, line = self._make_confirmed_order()
        pkgs = self.env["sb.production.package"].search(
            [("sale_order_line_id", "=", line.id)])
        self.assertEqual(
            len(pkgs), 1,
            "with the flag ON, one production package per confirmed "
            "configured line")
        self.assertTrue(pkgs.cutlist_id, "package carries a cutlist")
        self.assertGreaterEqual(
            pkgs.cutlist_id.line_count, 7,
            "cutlist is non-empty and enumerates side_L/R, top, bottom, "
            "back, shelf, door (drawer banks skip door; 3-drawer base "
            "still emits 6+ panels)")

    def test_flag_on_re_confirm_is_idempotent(self):
        self._set_flag("True")
        so, line = self._make_confirmed_order()
        # Drop the order back to draft and re-confirm to simulate the
        # legacy "unlock + confirm" pattern.
        so._action_cancel()
        so.action_draft()
        # The MO survives via cascade rules in fresh CE; if it's gone
        # in a future Odoo, the spine backlink will rewire on re-confirm.
        # In either case the production package's back-reference is the
        # idempotency key — assert no duplicate even if the MO changes.
        existing_before = self.env["sb.production.package"].search_count(
            [("sale_order_line_id", "=", line.id)])
        so.action_confirm()
        existing_after = self.env["sb.production.package"].search_count(
            [("sale_order_line_id", "=", line.id)])
        self.assertEqual(
            existing_before, existing_after,
            "re-confirm must not create a duplicate production package")
