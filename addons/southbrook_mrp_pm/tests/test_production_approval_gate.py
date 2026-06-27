# SPDX-License-Identifier: LGPL-3.0-only
"""W009 — Production-approval HARD GATE tests.

Five scenarios covering both the SO-confirm gate (primary) and the
manager-bypass affordance:

  1. test_so_blocked_without_approval
       Manufactured product + state=none → action_confirm raises.

  2. test_so_passes_with_approval
       Manufactured product + state=approved → action_confirm succeeds.

  3. test_so_bypass_with_manager_flag
       Manager sets force_production_release=True → confirms despite
       state=none.

  4. test_so_bypass_blocked_for_non_manager
       Non-manager user tries to set force_production_release → either
       the field write itself raises AccessError, OR the write happens
       in admin context and confirm still raises because the bypass
       only matters when set BY a manager. We assert the field is
       group-gated on the view at minimum, and the gate logic itself
       remains effective.

  5. test_existing_mos_unaffected
       A pre-existing MO continues through its lifecycle (cancel /
       state-write) untouched by the W009 gate, which fires only on
       NEW create().
"""
from odoo.exceptions import AccessError, UserError
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "w009")
class TestProductionApprovalGate(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.SaleOrder = cls.env["sale.order"]
        cls.Partner = cls.env["res.partner"]
        cls.Product = cls.env["product.product"]
        cls.Bom = cls.env["mrp.bom"]
        cls.Mrp = cls.env["mrp.production"]

        cls.partner = cls.Partner.create({
            "name": "W009 Test Partner",
        })

        # Manufactured product with a resolvable BoM — the gate's
        # trigger condition. Storable so MRP can produce it.
        cls.mfg_product = cls.Product.create({
            "name": "W009 Test Cabinet",
            "type": "consu",
            "is_storable": True,
        })
        cls.bom = cls.Bom.create({
            "product_tmpl_id": cls.mfg_product.product_tmpl_id.id,
            "product_qty": 1.0,
            "type": "normal",
        })

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _make_order(self):
        return self.SaleOrder.create({
            "partner_id": self.partner.id,
            "order_line": [(0, 0, {
                "product_id": self.mfg_product.id,
                "product_uom_qty": 1.0,
            })],
        })

    def _make_sales_manager(self, login="w009_mgr"):
        return self.env["res.users"].create({
            "name": "W009 Sales Manager",
            "login": login,
            "group_ids": [(4, self.env.ref(
                "sales_team.group_sale_manager").id)],
        })

    def _make_sales_user(self, login="w009_user"):
        return self.env["res.users"].create({
            "name": "W009 Sales User",
            "login": login,
            "group_ids": [(4, self.env.ref(
                "sales_team.group_sale_salesman").id)],
        })

    # ------------------------------------------------------------------
    # 1 — Block without approval
    # ------------------------------------------------------------------
    def test_so_blocked_without_approval(self):
        order = self._make_order()
        self.assertEqual(order.production_approval_state, "none")
        with self.assertRaises(UserError) as cm:
            order.action_confirm()
        # Error message must name the offending product so the user can
        # tell which line is blocked.
        self.assertIn(self.mfg_product.display_name, str(cm.exception))
        # Order must still be in draft — confirm rolled back.
        self.assertEqual(order.state, "draft")

    # ------------------------------------------------------------------
    # 2 — Pass with approval
    # ------------------------------------------------------------------
    def test_so_passes_with_approval(self):
        order = self._make_order()
        order.write({"production_approval_state": "approved"})
        # Should not raise.
        order.action_confirm()
        self.assertEqual(order.state, "sale")

    # ------------------------------------------------------------------
    # 3 — Manager bypass
    # ------------------------------------------------------------------
    def test_so_bypass_with_manager_flag(self):
        order = self._make_order()
        manager = self._make_sales_manager()
        # Manager flips the bypass.
        order.with_user(manager).write({
            "force_production_release": True,
        })
        # State still 'none', but bypass cleared the gate.
        self.assertEqual(order.production_approval_state, "none")
        self.assertTrue(order.force_production_release)
        order.action_confirm()
        self.assertEqual(order.state, "sale")
        # The bypass must have been logged into chatter for audit.
        messages = order.message_ids.mapped("body")
        self.assertTrue(any("bypassed" in (m or "").lower()
                            for m in messages),
                        "Bypass must leave an audit trail in chatter")

    # ------------------------------------------------------------------
    # 4 — Bypass is group-gated on the view + gate stays effective
    # ------------------------------------------------------------------
    def test_so_bypass_blocked_for_non_manager(self):
        # The bypass field is visible only to sales_team.group_sale_manager
        # per the view xpath. We assert that visibility wiring is in
        # place AND that without the bypass, a non-manager confirming
        # an unapproved order still hits the gate.
        view = self.env.ref(
            "southbrook_mrp_pm.view_order_form_production_approval")
        self.assertIn(
            "sales_team.group_sale_manager",
            view.arch,
            "Bypass page must be gated on sales_team.group_sale_manager",
        )
        # And the gate itself remains effective for a non-manager user
        # who hasn't been able to flip the bypass.
        non_manager = self._make_sales_user()
        order = self._make_order()
        with self.assertRaises(UserError):
            order.with_user(non_manager).action_confirm()

    # ------------------------------------------------------------------
    # 5 — Existing MOs unaffected
    # ------------------------------------------------------------------
    def test_existing_mos_unaffected(self):
        # Pre-existing MO with no source SO (component sub-assembly
        # shape) — must be writeable + cancellable without the gate
        # firing.
        component = self.Product.create({
            "name": "W009 Test Component",
            "type": "consu",
            "is_storable": True,
        })
        self.Bom.create({
            "product_tmpl_id": component.product_tmpl_id.id,
            "product_qty": 1.0,
            "type": "normal",
        })
        # Pre-existing MO from a non-customer route (no sale_line_id,
        # no SO-matching origin) — should create cleanly. Confirms the
        # R1 carve-out for procurement/stock-rule MOs.
        existing_mo = self.Mrp.create({
            "product_id": component.id,
            "product_qty": 1.0,
            "origin": "INTERNAL/STOCK-REPL",
        })
        self.assertTrue(existing_mo.exists())
        # And state mutations on the already-existing MO are not
        # blocked by the W009 hook (gate is only on create).
        existing_mo.action_cancel()
        self.assertEqual(existing_mo.state, "cancel")
