# SPDX-License-Identifier: LGPL-3.0-only
"""Phase 2.3 acceptance tests:

  test_17_punchlist_open_spawns_items_from_templates
  test_18_signoff_validates_signature_and_name_required
  test_19_fail_item_spawns_damage_flag_on_signoff
  test_20_signoff_creates_draft_invoice
  test_21_job_sign_off_received_computes_from_punchlist
  test_22_punchlist_item_evidence_constraints
"""
from datetime import datetime, timedelta

from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook_installer", "punchlist")
class TestPunchlistAndSignoff(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Job = cls.env["southbrook.installer.job"]
        cls.Punchlist = cls.env["southbrook.installer.punchlist"]
        cls.Template = cls.env["southbrook.installer.punchlist.template"]
        cls.Manifest = cls.env["southbrook.delivery.manifest"]
        cls.Line = cls.env["southbrook.delivery.manifest.line"]
        cls.Att = cls.env["ir.attachment"]

        # Builder / project / installer
        cls.partner = cls.env["res.partner"].create({
            "name": "Test Builder LTD",
            "is_company": True,
        })
        cls.contact = cls.env["res.partner"].create({
            "name": "Test Builder Site Super",
            "parent_id": cls.partner.id,
        })
        cls.project = cls.env["project.project"].create({
            "name": "Phase 2.3 Test Project",
        })
        cls.installer = cls.env["hr.employee"].create({
            "name": "Test Lead — 2.3",
        })
        cls.product = cls.env["product.product"].create({
            "name": "Test B30 (2.3)",
            "type": "consu",
        })

    def _make_job(self, **overrides):
        vals = {
            "project_id": self.project.id,
            "unit_number": "T-23",
            "site_address": "23 Punch Lane",
            "builder_contact_id": self.contact.id,
            "lead_installer_id": self.installer.id,
            "scheduled_date": datetime.now() + timedelta(days=1),
        }
        vals.update(overrides)
        return self.Job.create(vals)

    def _photo(self, name="p.jpg"):
        return self.Att.create({
            "name": name, "datas": "Zm9v", "mimetype": "image/jpeg",
        })

    def _attach_signature_blob(self, punchlist):
        """Minimal signature placeholder — Binary field accepts any
        base64 string for test purposes."""
        punchlist.write({
            "signature_data": "aGVsbG8=",  # base64 "hello"
            "signed_by_name": "Test Builder Super",
            "signed_by_role": "Builder Site Supervisor",
        })

    def _attach_minimum_manifest(self, job):
        """Sign-off auto-creates damage flags for FAIL items and needs
        a product context; manifest gives us one when item has no
        product_id of its own."""
        manifest = self.Manifest.create({
            "job_id": job.id, "state": "confirmed",
        })
        self.Line.create({
            "manifest_id": manifest.id,
            "product_id": self.product.id,
            "qty_expected": 1.0,
            "status": "ok",
        })
        return manifest

    # ==================================================================
    # test_17 — opening spawns items per template
    # ==================================================================
    def test_17_punchlist_open_spawns_items_from_templates(self):
        job = self._make_job()
        punchlist = self.Punchlist.create({"job_id": job.id})
        self.assertEqual(punchlist.state, "draft")
        self.assertFalse(punchlist.item_ids)

        punchlist.action_open()
        self.assertEqual(punchlist.state, "in_progress")
        active_template_count = self.Template.search_count(
            [("active", "=", True)]
        )
        self.assertEqual(
            len(punchlist.item_ids), active_template_count,
            "One punchlist item per active template.",
        )
        self.assertGreaterEqual(active_template_count, 20,
                                "Phase 2.3 seeds at least 20 items.")

        # Idempotent
        punchlist.action_open()
        self.assertEqual(len(punchlist.item_ids), active_template_count)

    # ==================================================================
    # test_18 — sign-off requires signature + name + no pending items
    # ==================================================================
    def test_18_signoff_validates_signature_and_name_required(self):
        job = self._make_job()
        self._attach_minimum_manifest(job)
        punchlist = self.Punchlist.create({"job_id": job.id})
        punchlist.action_open()

        # All items still pending → blocks
        with self.assertRaises(UserError) as cm:
            punchlist.action_submit_signoff()
        self.assertIn("pending", cm.exception.args[0].lower())

        # Mark all pass
        for item in punchlist.item_ids:
            item.write({"result": "pass"})
        # Still missing signature
        with self.assertRaises(UserError) as cm:
            punchlist.action_submit_signoff()
        self.assertIn("signature", cm.exception.args[0].lower())

        # Add signature but no name
        punchlist.write({"signature_data": "aGVsbG8="})
        with self.assertRaises(UserError) as cm:
            punchlist.action_submit_signoff()
        self.assertIn("printed name", cm.exception.args[0].lower())

        # All good now
        punchlist.write({"signed_by_name": "Test Super"})
        punchlist.action_submit_signoff()
        self.assertEqual(punchlist.state, "complete")
        self.assertTrue(punchlist.signed_at)

    # ==================================================================
    # test_19 — FAIL items spawn damage flags
    # ==================================================================
    def test_19_fail_item_spawns_damage_flag_on_signoff(self):
        job = self._make_job()
        self._attach_minimum_manifest(job)
        punchlist = self.Punchlist.create({"job_id": job.id})
        punchlist.action_open()

        # Pick one item to FAIL and the rest PASS
        items = punchlist.item_ids.sorted("id")
        photo = self._photo("fail.jpg")
        items[0].write({
            "result": "fail",
            "notes": "Hinge alignment way off — door rubs.",
            "photo_ids": [(4, photo.id)],
        })
        for it in items[1:]:
            it.write({"result": "pass"})

        self._attach_signature_blob(punchlist)
        punchlist.action_submit_signoff()

        # Damage flag spawned + linked
        self.assertTrue(items[0].deficiency_flag_id,
                        "FAIL item must get a linked deficiency flag.")
        flag = items[0].deficiency_flag_id
        self.assertEqual(flag.issue_type, "site_damage")
        self.assertEqual(flag.urgency, "non_blocking")
        self.assertEqual(flag.job_id, job)
        self.assertEqual(flag.product_id, self.product,
                         "Should use manifest line product as fallback.")

    # ==================================================================
    # test_20 — sign-off creates draft invoice
    # ==================================================================
    def test_20_signoff_creates_draft_invoice(self):
        job = self._make_job()
        self._attach_minimum_manifest(job)
        punchlist = self.Punchlist.create({"job_id": job.id})
        punchlist.action_open()
        for item in punchlist.item_ids:
            item.write({"result": "pass"})
        self._attach_signature_blob(punchlist)
        punchlist.action_submit_signoff()

        self.assertTrue(
            punchlist.invoice_id,
            "Draft invoice should be auto-created on PASS sign-off.",
        )
        inv = punchlist.invoice_id
        self.assertEqual(inv.move_type, "out_invoice")
        self.assertEqual(inv.state, "draft")
        # builder_contact_id has parent_id = self.partner; invoice goes
        # to the company, not the individual contact.
        self.assertEqual(inv.partner_id, self.partner)
        self.assertIn(job.name, inv.invoice_origin)

    # ==================================================================
    # test_21 — job.sign_off_received computes from punchlist
    # ==================================================================
    def test_21_job_sign_off_received_computes_from_punchlist(self):
        job = self._make_job()
        self._attach_minimum_manifest(job)
        self.assertFalse(
            job.sign_off_received,
            "Fresh job should not be signed off.",
        )

        punchlist = self.Punchlist.create({"job_id": job.id})
        punchlist.action_open()
        for item in punchlist.item_ids:
            item.write({"result": "pass"})
        self._attach_signature_blob(punchlist)
        punchlist.action_submit_signoff()

        job.invalidate_recordset()
        self.assertTrue(
            job.sign_off_received,
            "Completed signed punchlist must flip "
            "job.sign_off_received True via the computed field.",
        )
        self.assertEqual(job.punchlist_id, punchlist)

    # ==================================================================
    # test_22 — item-level evidence constraints
    #
    # The constraint fires for the first failing condition; for FAIL
    # items that means photo first (when required_on_fail=True),
    # then notes if photo is satisfied. Test each path distinctly.
    # ==================================================================
    def test_22_punchlist_item_evidence_constraints(self):
        job = self._make_job()
        punchlist = self.Punchlist.create({"job_id": job.id})
        punchlist.action_open()
        items = punchlist.item_ids.sorted("id")

        # Minor without notes raises ValidationError → "notes"
        with self.assertRaises(ValidationError) as cm:
            items[0].write({"result": "minor", "notes": ""})
        self.assertIn("notes", cm.exception.args[0].lower())

        # Fail with NO photo (constraint: photo check fires first)
        with self.assertRaises(ValidationError) as cm:
            items[0].write({
                "result": "fail",
                "notes": "Cosmetic nick",
                "photo_ids": [],
            })
        self.assertIn("photo", cm.exception.args[0].lower())

        # Fail WITH photo but NO notes → next constraint catches: "notes"
        photo = self._photo("p.jpg")
        with self.assertRaises(ValidationError) as cm:
            items[0].write({
                "result": "fail",
                "photo_ids": [(4, photo.id)],
                "notes": "",
            })
        self.assertIn("notes", cm.exception.args[0].lower())

        # All evidence present → OK
        items[0].write({
            "result": "fail",
            "notes": "Cosmetic nick",
            "photo_ids": [(4, photo.id)],
        })
        self.assertEqual(items[0].result, "fail")

        # Minor WITH notes → OK on a different item
        items[1].write({
            "result": "minor",
            "notes": "Slight finish variation, acceptable.",
        })
        self.assertEqual(items[1].result, "minor")
