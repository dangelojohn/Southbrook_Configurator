# SPDX-License-Identifier: LGPL-3.0-only
"""Lifecycle tests for southbrook.installer.job.

Covers the v1 spec Phase 1.1 acceptance criteria:
- test_01: create job, verify auto-sequence + auto-spawned phase logs
- test_02: stage-gate enforcement — all failures surface in one pass
"""
from datetime import datetime, timedelta

from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook_installer", "job")
class TestInstallerJobLifecycle(TransactionCase):
    """Full lifecycle through the 8-stage workflow."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Job = cls.env["southbrook.installer.job"]
        cls.Stage = cls.env["southbrook.installer.stage"]
        cls.Phase = cls.env["southbrook.installer.phase"]
        cls.Log = cls.env["southbrook.installer.stage.log"]

        # Build a minimal viable project + lead installer + builder partner.
        cls.partner = cls.env["res.partner"].create({
            "name": "Test Builder Supervisor",
            "phone": "555-0100",
        })
        cls.project = cls.env["project.project"].create({
            "name": "Test Builder Project — Phase 1 Test",
        })
        cls.installer = cls.env["hr.employee"].create({
            "name": "Test Lead Installer",
        })

    def _make_job(self, **overrides):
        vals = {
            "project_id": self.project.id,
            "unit_number": "T-101",
            "site_address": "1 Test Lane, Toronto",
            "builder_contact_id": self.partner.id,
            "lead_installer_id": self.installer.id,
            "scheduled_date": datetime.now() + timedelta(days=1),
        }
        vals.update(overrides)
        return self.Job.create(vals)

    # ==================================================================
    # test_01 — create + auto-population
    # ==================================================================
    def test_01_create_job_and_verify_fields(self):
        """Creating a job allocates a sequence, picks the first stage,
        and spawns one phase log per active phase."""
        job = self._make_job()

        # Sequence allocation
        self.assertTrue(
            job.name.startswith("INST-"),
            f"Expected INST- prefix, got {job.name!r}",
        )
        self.assertNotEqual(job.name, "New", "Sequence was not allocated.")

        # Starts at lowest-sequence stage (SCHEDULED)
        self.assertEqual(job.stage_id.code, "SCHEDULED")
        self.assertFalse(
            job.stage_is_terminal,
            "SCHEDULED should not be terminal.",
        )

        # One phase log per ACTIVE phase
        active_phase_count = self.Phase.search_count([("active", "=", True)])
        self.assertEqual(
            len(job.stage_log_ids),
            active_phase_count,
            "Phase logs should be spawned 1:1 with active phases.",
        )
        self.assertEqual(active_phase_count, 11, "Phase 1.1 seeds 11 phases.")

        # All logs start pending
        self.assertTrue(
            all(log.state == "pending" for log in job.stage_log_ids),
            "All freshly-spawned logs should be 'pending'.",
        )

        # Completion is zero
        self.assertEqual(job.completion_pct, 0.0)

        # Spawn is idempotent — calling again creates no duplicates
        before = len(job.stage_log_ids)
        job._spawn_phase_logs()
        self.assertEqual(
            len(job.stage_log_ids),
            before,
            "_spawn_phase_logs should be idempotent.",
        )

    # ==================================================================
    # test_02 — stage gate enforcement (the big one)
    # ==================================================================
    def test_02_advance_stage_gate_enforcement(self):
        """Walk the workflow stage by stage, proving each gate's
        failure surfaces in one ``UserError`` and the gate's pass
        condition allows the advance."""
        job = self._make_job()

        # ── Stage 1: SCHEDULED (no exit gates) → PRE_SITE_CONFIRM ──
        self.assertEqual(job.stage_id.code, "SCHEDULED")
        job.action_advance_stage()
        self.assertEqual(job.stage_id.code, "PRE_SITE_CONFIRM")

        # ── Stage 2: PRE_SITE_CONFIRM (gate: delivery_confirmed) ──
        # Should fail with delivery not confirmed.
        with self.assertRaises(UserError) as cm:
            job.action_advance_stage()
        self.assertIn("Delivery manifest", cm.exception.args[0])
        self.assertEqual(
            job.stage_id.code, "PRE_SITE_CONFIRM",
            "Stage must not change when gate fails.",
        )

        # Flip delivery and advance.
        job.delivery_confirmed = True
        job.action_advance_stage()
        self.assertEqual(job.stage_id.code, "DELIVERY_RECEIVED")

        # ── Stage 3: DELIVERY_RECEIVED (no gates) → INSTALLATION_IN_PROGRESS ──
        job.action_advance_stage()
        self.assertEqual(job.stage_id.code, "INSTALLATION_IN_PROGRESS")

        # ── Stage 4: INSTALLATION_IN_PROGRESS (gate: all phases done) ──
        with self.assertRaises(UserError) as cm:
            job.action_advance_stage()
        self.assertIn("phases not done", cm.exception.args[0].lower())

        # Mark all phase logs done. We must inject photos for the
        # photo-gated phases first — otherwise action_mark_done raises.
        # M2M tuple (4, X) is idempotent (dedupes on the rel table) so
        # we must create DISTINCT ir.attachment rows per photo slot.
        Att = self.env["ir.attachment"]
        for log in job.stage_log_ids:
            if log.phase_id.require_photo and log.photo_count < log.min_photos_required:
                need = log.min_photos_required - log.photo_count
                new_atts = Att.create([{
                    "name": f"phase-{log.phase_id.code}-photo-{i}.jpg",
                    "datas": "Zm9v",  # base64 "foo"
                    "mimetype": "image/jpeg",
                } for i in range(need)])
                log.photo_ids = [(4, a.id) for a in new_atts]
            log.action_mark_done()

        self.assertEqual(job.completion_pct, 100.0)
        job.action_advance_stage()
        self.assertEqual(job.stage_id.code, "FINAL_SIGN_OFF")

        # ── Stage 5: FINAL_SIGN_OFF (gate: sign_off_received) ──
        with self.assertRaises(UserError) as cm:
            job.action_advance_stage()
        self.assertIn("sign-off", cm.exception.args[0].lower())
        job.action_record_signoff()
        job.action_advance_stage()
        self.assertEqual(job.stage_id.code, "CLOSED_OUT")

        # ── Stage 6: CLOSED_OUT (gate: closeout_done) ──
        with self.assertRaises(UserError) as cm:
            job.action_advance_stage()
        self.assertIn("close-out", cm.exception.args[0].lower())
        job.action_mark_closeout_done()
        job.action_advance_stage()
        self.assertEqual(job.stage_id.code, "COMPLETE")

        # ── Stage 7: COMPLETE (no gates) → INVOICED (terminal) ──
        job.action_advance_stage()
        self.assertEqual(job.stage_id.code, "INVOICED")
        self.assertTrue(job.stage_is_terminal)

        # ── Stage 8: INVOICED is terminal — cannot advance further ──
        with self.assertRaises(UserError) as cm:
            job.action_advance_stage()
        self.assertIn("final stage", cm.exception.args[0].lower())

    # ==================================================================
    # Additional coverage — gate aggregation
    # ==================================================================
    def test_03_gate_failures_aggregate(self):
        """When multiple exit gates fail on the same stage, ALL appear
        in the one error message — the installer never has to submit
        twice to discover two problems."""
        job = self._make_job()
        # Manually park the job at INSTALLATION_IN_PROGRESS by writing
        # the stage directly (skipping gate validation).
        stage_iip = self.Stage.search([("code", "=", "INSTALLATION_IN_PROGRESS")])
        job.stage_id = stage_iip
        # Inject a compound failure: both all-phases-done AND we'll
        # mutate the stage temporarily to require sign-off too.
        original = stage_iip.gate_require_sign_off
        try:
            stage_iip.gate_require_sign_off = True
            with self.assertRaises(UserError) as cm:
                job.action_advance_stage()
            msg = cm.exception.args[0]
            self.assertIn("phases not done", msg.lower())
            self.assertIn("sign-off", msg.lower())
        finally:
            stage_iip.gate_require_sign_off = original

    # ==================================================================
    # Phase log photo gate
    # ==================================================================
    def test_04_phase_log_photo_gate(self):
        """A phase that requires photos cannot be marked done until
        ``min_photos`` are attached. The phase that does NOT require
        photos (Lighting) is freely completable with zero attachments."""
        job = self._make_job()

        # Site assessment requires 2 photos.
        site_log = job.stage_log_ids.filtered(
            lambda l: l.phase_id.code == "PHASE_01"
        )
        self.assertTrue(site_log)
        with self.assertRaises(ValidationError) as cm:
            site_log.action_mark_done()
        self.assertIn("photo", cm.exception.args[0].lower())

        # Lighting (PHASE_09) does NOT require photos.
        lighting_log = job.stage_log_ids.filtered(
            lambda l: l.phase_id.code == "PHASE_09"
        )
        self.assertTrue(lighting_log)
        self.assertTrue(
            lighting_log.photo_gate_passed,
            "Phases with require_photo=False should pass the gate "
            "with zero attachments.",
        )
        lighting_log.action_mark_done()
        self.assertEqual(lighting_log.state, "done")

    # ==================================================================
    # Computed completion percentage
    # ==================================================================
    def test_05_completion_pct_ignores_skipped(self):
        """Skipped phases drop out of both numerator and denominator
        of the completion calculation."""
        job = self._make_job()
        # Skip lighting + one other (don't need photos to skip).
        job.stage_log_ids.filtered(
            lambda l: l.phase_id.code in ("PHASE_09",)
        ).action_mark_skipped()

        # Mark one phase as done (use one that doesn't require photos —
        # PHASE_06 is filler strips, photo not required by default? Let's
        # check: PHASE_06 require_photo=True (default), min_photos=1.
        # Easier: use the lighting we just skipped. Already skipped.
        # Instead, set photo + mark PHASE_06 done.
        attachment = self.env["ir.attachment"].create({
            "name": "p.jpg", "datas": "Zm9v", "mimetype": "image/jpeg",
        })
        filler_log = job.stage_log_ids.filtered(
            lambda l: l.phase_id.code == "PHASE_06"
        )
        filler_log.photo_ids = [(4, attachment.id)]
        filler_log.action_mark_done()

        # 11 total phases, 1 skipped → denominator 10, numerator 1 → 10%
        self.assertEqual(job.completion_pct, 10.0)
