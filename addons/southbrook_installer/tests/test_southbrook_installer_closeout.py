# SPDX-License-Identifier: LGPL-3.0-only
"""Phase 1.3 acceptance tests for tool loan + closeout.

Covers:
  test_10_tool_return_damaged_creates_maintenance_request
  test_11_tool_return_good_does_not_create_maintenance_request
  test_12_closeout_submit_collects_all_failures
  test_13_closeout_submit_creates_return_picking
  test_14_closeout_complete_flips_job_closeout_done
  test_15_closeout_tool_lines_auto_populate_from_loans
  test_16_lost_tool_requires_notes
"""
from datetime import datetime, timedelta

from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook_installer", "closeout")
class TestToolLoanAndCloseout(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Job = cls.env["southbrook.installer.job"]
        cls.Loan = cls.env["southbrook.installer.tool.loan"]
        cls.Closeout = cls.env["southbrook.installer.closeout"]
        cls.MaterialLine = cls.env[
            "southbrook.installer.closeout.material.line"]
        cls.ToolLine = cls.env["southbrook.installer.closeout.tool.line"]
        cls.Equipment = cls.env["maintenance.equipment"]
        cls.MaintReq = cls.env["maintenance.request"]
        cls.Att = cls.env["ir.attachment"]

        cls.partner = cls.env["res.partner"].create({
            "name": "Test Builder — 1.3",
        })
        cls.project = cls.env["project.project"].create({
            "name": "Phase 1.3 Test Project",
        })
        cls.installer = cls.env["hr.employee"].create({
            "name": "Test Lead — 1.3",
        })

        cls.product_a = cls.env["product.product"].create({
            "name": "Test Cab B30 (1.3)",
            "type": "consu",
        })

        # Two pieces of equipment to use as tools
        cls.tool_drill = cls.Equipment.create({
            "name": "Test Drill — DeWalt 20V",
        })
        cls.tool_laser = cls.Equipment.create({
            "name": "Test Laser Level — Bosch GLL",
        })

    def _make_job(self, **overrides):
        vals = {
            "project_id": self.project.id,
            "unit_number": "T-13",
            "site_address": "13 Closeout Lane",
            "builder_contact_id": self.partner.id,
            "lead_installer_id": self.installer.id,
            "scheduled_date": datetime.now() + timedelta(days=1),
        }
        vals.update(overrides)
        return self.Job.create(vals)

    def _photo(self, name="p.jpg"):
        return self.Att.create({
            "name": name, "datas": "Zm9v", "mimetype": "image/jpeg",
        })

    def _attach_minimum_phase_photos(self, job):
        """Closeout requires at least one phase photo on the job.
        Helper to satisfy that gate."""
        photo = self._photo("job_phase.jpg")
        job.write({"phase_photo_ids": [(4, photo.id)]})

    # ==================================================================
    # test_10 — damaged tool return creates maintenance.request
    # ==================================================================
    def test_10_tool_return_damaged_creates_maintenance_request(self):
        job = self._make_job()
        loan = self.Loan.create({
            "job_id": job.id,
            "equipment_id": self.tool_drill.id,
            "tool_type": "power_tool",
            "signed_out_by_id": self.installer.id,
        })
        # Return damaged — requires return_notes per constraint
        loan.write({
            "return_condition": "damaged",
            "return_notes": "Chuck stripped, won't grip bit.",
        })
        loan.action_return_tool()

        self.assertTrue(loan.returned, "Loan should be returned.")
        self.assertEqual(loan.return_condition, "damaged")
        self.assertTrue(
            loan.maintenance_request_id,
            "Damaged condition should auto-create maintenance.request.",
        )
        req = loan.maintenance_request_id
        self.assertEqual(req.equipment_id, self.tool_drill)
        self.assertEqual(req.maintenance_type, "corrective")
        self.assertIn(loan.name, req.description)

    def test_11_tool_return_good_does_not_create_maintenance_request(self):
        job = self._make_job()
        loan = self.Loan.create({
            "job_id": job.id,
            "equipment_id": self.tool_laser.id,
            "tool_type": "measuring",
        })
        loan.write({"return_condition": "good"})
        loan.action_return_tool()

        self.assertTrue(loan.returned)
        self.assertFalse(
            loan.maintenance_request_id,
            "Good condition should NOT spawn a maintenance request.",
        )

    # ==================================================================
    # test_12 — closeout submit collects ALL failures
    # ==================================================================
    def test_12_closeout_submit_collects_all_failures(self):
        job = self._make_job()
        # No phase photos, no cleanup ticked, no installer confirm.
        # Plus one un-returned tool loan AND one open blocking flag
        # with no replacement ETA.
        loan = self.Loan.create({
            "job_id": job.id,
            "equipment_id": self.tool_drill.id,
        })
        flag = self.env["southbrook.damage.flag"].create({
            "job_id": job.id,
            "product_id": self.product_a.id,
            "issue_type": "damaged_transit",
            "urgency": "blocking",
            "qty_affected": 1.0,
            "description": "Cracked.",
        })

        closeout = self.Closeout.create({"job_id": job.id})
        closeout.action_open()
        self.assertEqual(closeout.state, "in_progress")
        self.assertEqual(
            len(closeout.tool_return_ids), 1,
            "Tool return line should auto-populate from the loan.",
        )

        with self.assertRaises(UserError) as cm:
            closeout.action_submit_closeout()
        msg = cm.exception.args[0]
        # All 5 categories of failure should surface in ONE error:
        self.assertIn("Packaging not removed", msg)
        self.assertIn("Builder has not confirmed cleanup", msg)
        self.assertIn("Tools not confirmed returned", msg)
        # Note: the flag's auto-PO may or may not have succeeded
        # depending on whether the test products have vendors. Either
        # way, the flag is still open → should surface unless it has
        # ETA. Set no ETA above, so it should fail.
        self.assertIn("Damage flags open without ETA", msg)
        self.assertIn("Lead installer has not confirmed", msg)
        self.assertIn("No phase photos", msg)

    # ==================================================================
    # test_13 — closeout submit creates return picking
    # ==================================================================
    def test_13_closeout_submit_creates_return_picking(self):
        job = self._make_job()
        self._attach_minimum_phase_photos(job)
        closeout = self.Closeout.create({"job_id": job.id})
        closeout.action_open()
        # Tick all gates
        closeout.write({
            "packaging_removed": True,
            "offcuts_collected": True,
            "cabinets_wiped": True,
            "sawdust_cleared": True,
            "adhesive_removed": True,
            "floor_protection_removed": True,
            "tape_removed": True,
            "builder_approves_cleanup": True,
            "installer_confirmed": True,
        })
        # Add a material return line
        self.MaterialLine.create({
            "closeout_id": closeout.id,
            "product_id": self.product_a.id,
            "qty_returning": 1.0,
            "uom_id": self.product_a.uom_id.id,
            "reason": "unused",
            "condition": "new",
        })

        closeout.action_submit_closeout()
        self.assertEqual(closeout.state, "complete")
        self.assertTrue(
            closeout.return_picking_id,
            "Return picking should be created from material lines.",
        )
        self.assertEqual(closeout.return_picking_id.partner_id, self.partner)
        self.assertEqual(
            len(closeout.return_picking_id.move_ids), 1,
            "One stock.move per material return line.",
        )

    # ==================================================================
    # test_14 — closeout 'complete' flips job.closeout_done
    # ==================================================================
    def test_14_closeout_complete_flips_job_closeout_done(self):
        job = self._make_job()
        self._attach_minimum_phase_photos(job)
        self.assertFalse(job.closeout_done)
        closeout = self.Closeout.create({"job_id": job.id})
        closeout.action_open()
        closeout.write({
            "packaging_removed": True,
            "offcuts_collected": True,
            "cabinets_wiped": True,
            "sawdust_cleared": True,
            "adhesive_removed": True,
            "floor_protection_removed": True,
            "tape_removed": True,
            "builder_approves_cleanup": True,
            "installer_confirmed": True,
        })
        closeout.action_submit_closeout()

        job.invalidate_recordset()
        self.assertTrue(
            job.closeout_done,
            "Closeout in 'complete' state must flip "
            "job.closeout_done True.",
        )
        self.assertEqual(job.closeout_id, closeout)

    # ==================================================================
    # test_15 — opening closeout auto-populates tool_return_ids
    # ==================================================================
    def test_15_closeout_tool_lines_auto_populate_from_loans(self):
        job = self._make_job()
        loan_a = self.Loan.create({
            "job_id": job.id, "equipment_id": self.tool_drill.id,
        })
        loan_b = self.Loan.create({
            "job_id": job.id, "equipment_id": self.tool_laser.id,
        })

        closeout = self.Closeout.create({"job_id": job.id})
        closeout.action_open()
        loans_in_closeout = closeout.tool_return_ids.mapped("tool_loan_id")
        self.assertEqual(loans_in_closeout, loan_a | loan_b,
                         "All active loans must spawn a tool line.")

        # Re-running action_open is idempotent
        closeout.action_open()
        self.assertEqual(
            len(closeout.tool_return_ids), 2,
            "Re-opening should not duplicate tool lines.",
        )

    # ==================================================================
    # test_16 — 'lost' tool requires a return note (constraint)
    # ==================================================================
    def test_16_lost_tool_requires_notes(self):
        job = self._make_job()
        loan = self.Loan.create({
            "job_id": job.id, "equipment_id": self.tool_drill.id,
        })
        # Try to report lost without notes
        with self.assertRaises(ValidationError) as cm:
            loan.action_report_lost(notes="")
        self.assertIn("Return Notes", cm.exception.args[0])

        # With notes it works
        loan.action_report_lost(notes="Left at jobsite, can't recover.")
        self.assertEqual(loan.return_condition, "lost")
        self.assertTrue(loan.returned)
