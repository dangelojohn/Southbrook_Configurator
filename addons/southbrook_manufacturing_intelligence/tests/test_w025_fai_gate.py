# SPDX-License-Identifier: LGPL-3.0-only
"""W025 — tests for the First Article Inspection (FAI) gate.

Covers the W025 spec acceptance points:
  1. New BOMs flagged fai_required by create() heuristics (PG release
     id or southbrook_version > 1).
  2. First MO against a fai_required BOM is blocked at action_assign.
  3. Subsequent MOs on the same BOM after FAI pass are NOT blocked.
  4. FAI pass requires a different user than the BOM creator (SoD).
  5. FAI check is auto-created on MO create.
  6. FAI failed keeps the MO blocked until rework or waiver.
  7. action_fai_pass and action_fai_fail are idempotent.
"""
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestW025FaiGate(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Users = cls.env["res.users"].with_context(no_reset_password=True)
        cls.bom_creator = Users.create({
            "name": "Test BOM Engineer",
            "login": "test_bom_eng_w025",
            "group_ids": [(6, 0, [
                cls.env.ref("mrp.group_mrp_user").id,
                cls.env.ref("mrp.group_mrp_manager").id,
            ])],
        })
        cls.fai_inspector = Users.create({
            "name": "Test FAI Inspector",
            "login": "test_fai_qc_w025",
            "group_ids": [(6, 0, [
                cls.env.ref("mrp.group_mrp_user").id,
                cls.env.ref("mrp.group_mrp_manager").id,
            ])],
        })

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _make_product(self, name="W025 Cabinet"):
        vals = {"name": name}
        if "detailed_type" in self.env["product.product"]._fields:
            vals["detailed_type"] = "consu"
        elif "type" in self.env["product.product"]._fields:
            vals["type"] = "consu"
        return self.env["product.product"].create(vals)

    def _make_bom(self, product, fai_required=None, user=None,
                  southbrook_version=1):
        env = self.env(user=user) if user else self.env
        vals = {
            "product_tmpl_id": product.product_tmpl_id.id,
            "product_qty": 1.0,
            "product_uom_id": product.uom_id.id,
            "type": "normal",
        }
        # `fai_required` defaults to the None sentinel, NOT False, and is
        # omitted from vals when unset. mrp_bom.create() skips its
        # auto-stamp heuristics whenever "fai_required" is present in vals
        # ("don't clobber an explicit caller intent"), so passing False
        # unconditionally made the auto-stamp path untestable — the
        # southbrook_version > 1 case silently asserted against a flag the
        # override had deliberately declined to set. Callers that mean to
        # pin the flag still pass True/False explicitly.
        if fai_required is not None:
            vals["fai_required"] = fai_required
        # Only set southbrook_version when the field is on the model
        # (it is — PLM is a transitive dep — but be defensive in case
        # of future module-shape changes).
        if "southbrook_version" in env["mrp.bom"]._fields:
            vals["southbrook_version"] = southbrook_version
        return env["mrp.bom"].create(vals)

    def _make_mo(self, product, bom, skip_fai=False):
        ctx = {"_w025_skip_fai_default": True} if skip_fai else {}
        return self.env["mrp.production"].with_context(**ctx).create({
            "product_id": product.id,
            "product_uom_id": product.uom_id.id,
            "product_qty": 1.0,
            "bom_id": bom.id,
        })

    # ------------------------------------------------------------------
    # 1. Create-time heuristics — southbrook_version > 1 → fai_required
    # ------------------------------------------------------------------
    def test_new_bom_via_eco_reversion_has_fai_required(self):
        """A BOM created with southbrook_version > 1 (the PLM ECO
        re-version path) is auto-stamped fai_required=True."""
        product = self._make_product("W025 ECO-versioned")
        bom = self._make_bom(product, southbrook_version=2)
        self.assertTrue(
            bom.fai_required,
            "BOM with southbrook_version=2 should be fai_required",
        )

    def test_hand_authored_bom_not_fai_required(self):
        """A vanilla BOM with no PG release id and version=1 is NOT
        fai_required (admins hand-creating BOMs aren't the target)."""
        product = self._make_product("W025 Hand-authored")
        bom = self._make_bom(product)
        self.assertFalse(
            bom.fai_required,
            "Hand-authored BOM should not be fai_required by default",
        )

    def test_context_skip_bypasses_auto_fai(self):
        """The `_w025_skip_fai_default` context flag bypasses both the
        BOM auto-flag AND the MO auto-check-create — for test/migration
        fixtures."""
        product = self._make_product("W025 Skip-ctx")
        bom = self.env["mrp.bom"].with_context(
            _w025_skip_fai_default=True
        ).create({
            "product_tmpl_id": product.product_tmpl_id.id,
            "product_qty": 1.0,
            "product_uom_id": product.uom_id.id,
            "type": "normal",
            "southbrook_version": 5,
        })
        self.assertFalse(bom.fai_required)

    # ------------------------------------------------------------------
    # 2. action_assign gate
    # ------------------------------------------------------------------
    def test_first_mo_blocked_without_fai_pass(self):
        """An MO whose BOM is fai_required + no FAI pass yet cannot be
        released via action_assign."""
        product = self._make_product("W025 Gated")
        bom = self._make_bom(product, fai_required=True)
        mo = self._make_mo(product, bom)
        # bypass_availability_gate=True keeps southbrook_premium_orchestration's
        # action_confirm from calling action_assign itself — we want
        # to call action_assign explicitly below so we can assert the
        # FAI gate behaviour in isolation.
        mo.with_context(bypass_availability_gate=True).action_confirm()
        # fai_status should be in_progress (auto-check at warning sev).
        self.assertIn(mo.fai_status, ("pending", "in_progress"))
        with self.assertRaises(UserError):
            mo.action_assign()

    # ------------------------------------------------------------------
    # 3. After FAI pass, subsequent MO is not blocked
    # ------------------------------------------------------------------
    def test_subsequent_mo_after_fai_pass_not_blocked(self):
        product = self._make_product("W025 SequencedPass")
        bom = self._make_bom(product, fai_required=True,
                              user=self.bom_creator)
        mo1 = self._make_mo(product, bom)
        mo1.action_confirm()
        # Pass the FAI on mo1 (with a different user — SoD).
        fai_check = mo1.fai_check_id
        self.assertTrue(fai_check, "FAI check should be auto-created on mo1")
        fai_check.with_user(self.fai_inspector).action_fai_pass()
        bom.invalidate_recordset(fnames=["fai_required"])
        self.assertFalse(
            bom.fai_required,
            "BOM.fai_required should flip to False after passing FAI",
        )
        # Now a SECOND MO on the same BOM:
        mo2 = self._make_mo(product, bom)
        self.assertEqual(
            mo2.fai_status, "not_required",
            "Second MO on a passed BOM should be fai_status=not_required",
        )
        # action_assign should not raise (it may still fail for other
        # reasons in this minimal test setup — we only care that the
        # FAI gate UserError is NOT raised).
        try:
            mo2.action_confirm()
            mo2.action_assign()
        except UserError as exc:
            # Anything OTHER than the FAI gate text is fine.
            self.assertNotIn(
                "First Article Inspection", str(exc),
                f"Did not expect FAI gate on second MO: {exc}",
            )

    # ------------------------------------------------------------------
    # 4. SoD — FAI inspector must differ from BOM creator
    # ------------------------------------------------------------------
    def test_fai_pass_requires_different_user_than_bom_creator(self):
        product = self._make_product("W025 SoD")
        bom = self._make_bom(product, fai_required=True,
                              user=self.bom_creator)
        mo = self._make_mo(product, bom)
        # bypass_availability_gate=True keeps southbrook_premium_orchestration's
        # action_confirm from calling action_assign itself — we want
        # to call action_assign explicitly below so we can assert the
        # FAI gate behaviour in isolation.
        mo.with_context(bypass_availability_gate=True).action_confirm()
        fai_check = mo.fai_check_id
        # Same user (bom_creator) trying to self-approve must raise.
        with self.assertRaises(UserError):
            fai_check.with_user(self.bom_creator).action_fai_pass()
        # Different user — passes.
        fai_check.with_user(self.fai_inspector).action_fai_pass()
        bom.invalidate_recordset(fnames=["fai_required"])
        self.assertFalse(bom.fai_required)

    # ------------------------------------------------------------------
    # 5. Auto-create FAI check on MO create
    # ------------------------------------------------------------------
    def test_fai_check_auto_created_on_mo_create(self):
        product = self._make_product("W025 AutoCheck")
        bom = self._make_bom(product, fai_required=True)
        mo = self._make_mo(product, bom)
        fai = mo.x_mi_check_ids.filtered(lambda c: c.category == "fai")
        self.assertEqual(
            len(fai), 1,
            "Exactly one FAI check should be auto-created on MO create",
        )
        self.assertEqual(fai.production_id, mo)
        self.assertEqual(fai.severity, "warning")

    def test_no_fai_check_when_bom_not_required(self):
        product = self._make_product("W025 NoGate")
        bom = self._make_bom(product, fai_required=False)
        mo = self._make_mo(product, bom)
        fai = mo.x_mi_check_ids.filtered(lambda c: c.category == "fai")
        self.assertFalse(
            fai, "No FAI check expected when BOM.fai_required=False",
        )
        self.assertEqual(mo.fai_status, "not_required")

    # ------------------------------------------------------------------
    # 6. Failed FAI blocks until rework or waiver
    # ------------------------------------------------------------------
    def test_fai_failed_blocks_until_rework_or_waiver(self):
        product = self._make_product("W025 Failed")
        bom = self._make_bom(product, fai_required=True,
                              user=self.bom_creator)
        mo = self._make_mo(product, bom)
        # bypass_availability_gate=True keeps southbrook_premium_orchestration's
        # action_confirm from calling action_assign itself — we want
        # to call action_assign explicitly below so we can assert the
        # FAI gate behaviour in isolation.
        mo.with_context(bypass_availability_gate=True).action_confirm()
        fai_check = mo.fai_check_id
        fai_check.with_user(self.fai_inspector).action_fai_fail()
        # Severity bumped to blocker; fai_status should be 'failed'.
        fai_check.invalidate_recordset(fnames=["severity"])
        self.assertEqual(fai_check.severity, "blocker")
        mo.invalidate_recordset(fnames=["fai_status"])
        self.assertEqual(mo.fai_status, "failed")
        # action_assign still blocked.
        with self.assertRaises(UserError):
            mo.action_assign()
        # BOM flag is NOT cleared.
        self.assertTrue(bom.fai_required)

    # ------------------------------------------------------------------
    # 7. Idempotency
    # ------------------------------------------------------------------
    def test_action_fai_pass_idempotent(self):
        product = self._make_product("W025 Idempotent")
        bom = self._make_bom(product, fai_required=True,
                              user=self.bom_creator)
        mo = self._make_mo(product, bom)
        # bypass_availability_gate=True keeps southbrook_premium_orchestration's
        # action_confirm from calling action_assign itself — we want
        # to call action_assign explicitly below so we can assert the
        # FAI gate behaviour in isolation.
        mo.with_context(bypass_availability_gate=True).action_confirm()
        fai_check = mo.fai_check_id
        fai_check.with_user(self.fai_inspector).action_fai_pass()
        # Re-fire — should NOT raise and should not change BOM state.
        bom.invalidate_recordset(fnames=["fai_required", "fai_passed_at"])
        passed_at_before = bom.fai_passed_at
        result = fai_check.with_user(self.fai_inspector).action_fai_pass()
        self.assertTrue(result)
        bom.invalidate_recordset(fnames=["fai_passed_at"])
        self.assertEqual(bom.fai_passed_at, passed_at_before,
                         "Second action_fai_pass should be a no-op")

    def test_action_fai_fail_idempotent(self):
        product = self._make_product("W025 FailIdem")
        bom = self._make_bom(product, fai_required=True,
                              user=self.bom_creator)
        mo = self._make_mo(product, bom)
        # bypass_availability_gate=True keeps southbrook_premium_orchestration's
        # action_confirm from calling action_assign itself — we want
        # to call action_assign explicitly below so we can assert the
        # FAI gate behaviour in isolation.
        mo.with_context(bypass_availability_gate=True).action_confirm()
        fai_check = mo.fai_check_id
        fai_check.with_user(self.fai_inspector).action_fai_fail()
        # Re-fire — should be safe.
        result = fai_check.with_user(self.fai_inspector).action_fai_fail()
        self.assertTrue(result)

    # ------------------------------------------------------------------
    # 8. Wrong-category guard — pass/fail only valid on category='fai'
    # ------------------------------------------------------------------
    def test_fai_pass_rejects_non_fai_category(self):
        product = self._make_product("W025 WrongCat")
        bom = self._make_bom(product, fai_required=False)
        mo = self._make_mo(product, bom)
        non_fai = self.env["southbrook.mi.check"].create({
            "name": "Random NCR",
            "severity": "warning",
            "category": "production",
            "message": "Not a FAI",
            "production_id": mo.id,
        })
        with self.assertRaises(UserError):
            non_fai.with_user(self.fai_inspector).action_fai_pass()

    # ------------------------------------------------------------------
    # 9. fai_status compute: passed-vs-not_required disambiguation
    # ------------------------------------------------------------------
    def test_fai_status_passed_on_signing_mo(self):
        """The MO that signed off the FAI should show fai_status='passed',
        not 'not_required', so the audit trail is preserved."""
        product = self._make_product("W025 PassedTrail")
        bom = self._make_bom(product, fai_required=True,
                              user=self.bom_creator)
        mo = self._make_mo(product, bom)
        # bypass_availability_gate=True keeps southbrook_premium_orchestration's
        # action_confirm from calling action_assign itself — we want
        # to call action_assign explicitly below so we can assert the
        # FAI gate behaviour in isolation.
        mo.with_context(bypass_availability_gate=True).action_confirm()
        fai_check = mo.fai_check_id
        fai_check.with_user(self.fai_inspector).action_fai_pass()
        mo.invalidate_recordset(fnames=["fai_status"])
        self.assertEqual(mo.fai_status, "passed")
