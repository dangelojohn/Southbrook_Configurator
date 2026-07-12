# SPDX-License-Identifier: LGPL-3.0-only
"""W012 — tests for the engineering deviation approval flow."""
from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestDeviationWaiver(TransactionCase):
    """Covers the W012 spec acceptance points:
      1. waiver create() links to mi.check + auto-numbered
      2. engineering approval requires mrp.group_mrp_manager
      3. SoD: approver != mi.check creator
      4. mi.check.state transitions on waiver approval/rejection
      5. chatter posts on state change
      6. mrp.production smart button returns the filtered waivers
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Users = cls.env["res.users"].with_context(no_reset_password=True)

        cls.qc_user = Users.create({
            "name": "Test QC Inspector",
            "login": "test_qc_w012",
            "group_ids": [
                (6, 0, [cls.env.ref("mrp.group_mrp_user").id]),
            ],
        })
        cls.eng_user = Users.create({
            "name": "Test Engineering Lead",
            "login": "test_eng_w012",
            "group_ids": [
                (6, 0, [cls.env.ref("mrp.group_mrp_manager").id]),
            ],
        })
        cls.other_eng_user = Users.create({
            "name": "Test Second Engineer",
            "login": "test_eng2_w012",
            "group_ids": [
                (6, 0, [cls.env.ref("mrp.group_mrp_manager").id]),
            ],
        })
        cls.random_user = Users.create({
            "name": "Test Non-Eng User",
            "login": "test_rand_w012",
            "group_ids": [
                (6, 0, [cls.env.ref("mrp.group_mrp_user").id]),
            ],
        })

    def _make_production(self):
        product_vals = {"name": "W012 Test Cabinet"}
        if "detailed_type" in self.env["product.product"]._fields:
            product_vals["detailed_type"] = "consu"
        elif "type" in self.env["product.product"]._fields:
            product_vals["type"] = "consu"
        product = self.env["product.product"].create(product_vals)
        bom = self.env["mrp.bom"].create({
            "product_tmpl_id": product.product_tmpl_id.id,
            "product_qty": 1.0,
            "product_uom_id": product.uom_id.id,
            "type": "normal",
        })
        production = self.env["mrp.production"].create({
            "product_id": product.id,
            "product_uom_id": product.uom_id.id,
            "product_qty": 1.0,
            "bom_id": bom.id,
        })
        return production

    def _make_check(self, production, user=None):
        env = self.env(user=user) if user else self.env
        return env["southbrook.mi.check"].create({
            "name": "W012 Defect",
            "severity": "warning",
            "category": "production",
            "message": "Door alignment off by 1.5 mm — cosmetic.",
            "recommendation": "Customer to confirm acceptance.",
            "production_id": production.id,
        })

    def _draft_waiver(self, check, customer_acked=True, user=None):
        env = self.env(user=user) if user else self.env
        return env["southbrook.deviation.waiver"].create({
            "mi_check_id": check.id,
            "defect_summary": "Door alignment cosmetic offset, customer aware.",
            "customer_acknowledged": customer_acked,
            "customer_acknowledgment_method":
                "email" if customer_acked else False,
            "customer_acknowledgment_ref":
                "RE: Cabinet B-3 approval 2026-06-27"
                if customer_acked else False,
        })

    # ------------------------------------------------------------------
    # 1. waiver create links + sequence
    # ------------------------------------------------------------------
    def test_waiver_create_links_to_mi_check(self):
        production = self._make_production()
        check = self._make_check(production)
        waiver = self._draft_waiver(check)
        self.assertEqual(waiver.mi_check_id, check)
        self.assertEqual(waiver.production_id, production)
        # Auto-sequenced (WV-YYYY-NNNN format expected).
        self.assertNotEqual(waiver.name, "New")
        self.assertTrue(waiver.name.startswith("WV-"),
                        f"Expected WV- prefix, got {waiver.name!r}")
        # create() posts a chatter note.
        self.assertTrue(waiver.message_ids,
                        "Expected chatter note on waiver create")

    # ------------------------------------------------------------------
    # 2. eng approval requires the eng group
    # ------------------------------------------------------------------
    def test_eng_approval_requires_eng_group(self):
        production = self._make_production()
        check = self._make_check(production, user=self.qc_user)
        waiver = self._draft_waiver(check)
        waiver.action_submit_for_eng_review()
        self.assertEqual(waiver.state, "eng_review")
        # Non-eng user cannot approve.
        with self.assertRaises(AccessError):
            waiver.with_user(self.random_user).action_approve()
        # Eng user (NOT the check creator) can approve.
        waiver.with_user(self.eng_user).action_approve()
        self.assertEqual(waiver.state, "approved")
        self.assertEqual(waiver.engineering_approver_id, self.eng_user)
        self.assertTrue(waiver.engineering_approved_at)

    # ------------------------------------------------------------------
    # 3. SoD — approver must differ from check creator
    # ------------------------------------------------------------------
    def test_sod_approver_not_check_creator(self):
        production = self._make_production()
        # QC user who is ALSO an eng (group_mrp_manager) — common in
        # small shops. The SoD rule must still bite because they're the
        # ones who created the check.
        Users = self.env["res.users"].with_context(no_reset_password=True)
        dual_role = Users.create({
            "name": "Test Dual-Role Engineer",
            "login": "test_dual_w012",
            "group_ids": [(6, 0, [
                self.env.ref("mrp.group_mrp_user").id,
                self.env.ref("mrp.group_mrp_manager").id,
            ])],
        })
        check = self._make_check(production, user=dual_role)
        # SoD compares the WAIVER REQUESTER (create_uid), so the dual-role user
        # must be the one who raised the waiver — then they can't self-approve.
        waiver = self._draft_waiver(check, user=dual_role)
        waiver.action_submit_for_eng_review()
        # Same user cannot self-approve even though they're in the eng
        # group — SoD must block.
        with self.assertRaises(AccessError):
            waiver.with_user(dual_role).action_approve()
        # A different eng user CAN approve.
        waiver.with_user(self.eng_user).action_approve()
        self.assertEqual(waiver.state, "approved")

    # ------------------------------------------------------------------
    # 4. mi.check.state transitions tracked on waiver lifecycle
    # ------------------------------------------------------------------
    def test_mi_check_state_transitions_on_waiver_approval(self):
        production = self._make_production()
        check = self._make_check(production, user=self.qc_user)
        self.assertEqual(check.state, "draft")
        waiver = self._draft_waiver(check)
        # link the waiver to the check (the wizard does this; we do it
        # directly here to keep the test focused on the model).
        check.deviation_waiver_id = waiver
        waiver.action_submit_for_eng_review()
        check.invalidate_recordset(fnames=["state"])
        self.assertEqual(check.state, "pending_deviation_approval")
        waiver.with_user(self.eng_user).action_approve()
        check.invalidate_recordset(fnames=["state"])
        self.assertEqual(check.state, "ship_with_deviation")

    def test_mi_check_state_resets_on_waiver_rejection(self):
        production = self._make_production()
        check = self._make_check(production, user=self.qc_user)
        waiver = self._draft_waiver(check, customer_acked=False)
        check.deviation_waiver_id = waiver
        waiver.action_submit_for_eng_review()
        waiver.with_user(self.eng_user).action_reject()
        check.invalidate_recordset(fnames=["state"])
        self.assertEqual(check.state, "draft")
        self.assertEqual(waiver.state, "rejected")

    # ------------------------------------------------------------------
    # 5. chatter posts on state change
    # ------------------------------------------------------------------
    def test_chatter_post_on_state_change(self):
        production = self._make_production()
        check = self._make_check(production, user=self.qc_user)
        waiver = self._draft_waiver(check)
        msg_count_before_submit = len(waiver.message_ids)
        waiver.action_submit_for_eng_review()
        self.assertGreater(len(waiver.message_ids), msg_count_before_submit)
        msg_count_before_approve = len(waiver.message_ids)
        waiver.with_user(self.eng_user).action_approve()
        self.assertGreater(len(waiver.message_ids), msg_count_before_approve)
        # The most recent message should mention APPROVED.
        latest = waiver.message_ids[0]
        self.assertIn("APPROVED", latest.body or "")

    # ------------------------------------------------------------------
    # 6. smart button on mrp.production returns the filtered waivers
    # ------------------------------------------------------------------
    def test_smart_button_on_mo_returns_filtered_waivers(self):
        production = self._make_production()
        production2 = self._make_production()
        check1 = self._make_check(production, user=self.qc_user)
        check2 = self._make_check(production2, user=self.qc_user)
        waiver1 = self._draft_waiver(check1)
        check1.deviation_waiver_id = waiver1
        _waiver2 = self._draft_waiver(check2)  # bound to MO2
        production.invalidate_recordset(fnames=["deviation_waiver_count"])
        production2.invalidate_recordset(fnames=["deviation_waiver_count"])
        # Counts are MO-scoped.
        self.assertEqual(production.deviation_waiver_count, 1)
        self.assertEqual(production2.deviation_waiver_count, 1)
        action = production.action_open_deviation_waivers()
        self.assertEqual(action["res_model"], "southbrook.deviation.waiver")
        domain = action["domain"]
        self.assertIn(("production_id", "=", production.id), domain)

    # ------------------------------------------------------------------
    # Bonus — approval blocks if customer ack not captured
    # ------------------------------------------------------------------
    def test_approval_blocks_without_customer_ack(self):
        production = self._make_production()
        check = self._make_check(production, user=self.qc_user)
        waiver = self._draft_waiver(check, customer_acked=False)
        waiver.action_submit_for_eng_review()
        with self.assertRaises(UserError):
            waiver.with_user(self.eng_user).action_approve()
        # Tick the box — now it should succeed.
        waiver.write({
            "customer_acknowledged": True,
            "customer_acknowledgment_method": "email",
            "customer_acknowledgment_ref": "RE: Approval",
        })
        waiver.with_user(self.eng_user).action_approve()
        self.assertEqual(waiver.state, "approved")
