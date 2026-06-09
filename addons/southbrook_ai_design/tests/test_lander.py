# SPDX-License-Identifier: LGPL-3.0-only
"""Module 6 — sb.kitchen.project.consume_gemini_analysis() tests.

Covers the G3 §5 persistence contract: payload fields land on
sb.kitchen.ai.analysis + sb.kitchen.appliance records; every newly-
created record has confirmed_by_human=False; idempotency by image_hash
holds; analyze_photo() end-to-end DoD walk-through."""
import base64

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "ai_design", "lander")
class TestLander(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Project = cls.env["sb.kitchen.project"]
        cls.Partner = cls.env["res.partner"]
        cls.partner = cls.Partner.create({
            "name": "Test Customer for AI", "is_company": False,
        })

    def _new_project(self):
        return self.Project.create({
            "name": "AI test project",
            "partner_id": self.partner.id,
            "theme": "signature",
        })

    def _baseline_payload(self, image_hash="sha256:abc"):
        return {
            "schema": "southbrook.gemini.room_analysis.v1",
            "model": "mock", "ts": "2026-06-09T18:00:00Z",
            "image_hash": image_hash,
            "room": {
                "sink_detected": True, "window_count": 1, "room_door_count": 1,
                "floor_area_m2_approx": 18.5,
                "ceiling_height_mm_approx": 2400,
                "wall_segments": [
                    {"id": "wall_north", "length_mm_approx": 4200,
                     "has_windows": [True], "has_doors": [False]},
                ],
            },
            "appliances": [
                {"kind": "stove", "label": "Test stove",
                 "wall_segment_id": "wall_north",
                 "position_pct_along_wall": 0.5,
                 "width_mm_approx": 762, "height_mm_approx": 914,
                 "depth_mm_approx": 610, "requires_clearance_mm": 30,
                 "confidence": 0.86},
            ],
            "dimensions_confidence": {}, "model_warnings": [],
        }

    # ------------------------------------------------------------------
    # Lander correctness
    # ------------------------------------------------------------------
    def test_creates_analysis_and_appliances(self):
        project = self._new_project()
        analysis = project.consume_gemini_analysis(self._baseline_payload())

        self.assertTrue(analysis.exists())
        self.assertEqual(analysis.project_id, project)
        self.assertTrue(analysis.sink_detected)
        self.assertEqual(analysis.window_count, 1)
        self.assertEqual(analysis.ceiling_height_mm_approx, 2400.0)

        # Project links to the analysis.
        self.assertEqual(project.ai_analysis_id, analysis)

        # One appliance landed.
        self.assertEqual(len(project.appliance_ids), 1)
        stove = project.appliance_ids
        self.assertEqual(stove.appliance_type, "stove")
        self.assertEqual(stove.width_mm, 762.0)

    def test_all_new_records_unconfirmed(self):
        """G3 §5 — every newly-created record lands with
        confirmed_by_human=False. The GAP-02 gate stays closed."""
        project = self._new_project()
        analysis = project.consume_gemini_analysis(self._baseline_payload())
        self.assertFalse(analysis.confirmed_by_human)
        for app in project.appliance_ids:
            self.assertFalse(app.confirmed_by_human)

    def test_idempotent_by_image_hash(self):
        """Calling twice with the same image_hash returns the same
        analysis record + does not duplicate appliances."""
        project = self._new_project()
        first = project.consume_gemini_analysis(
            self._baseline_payload("sha256:zzz"))
        second = project.consume_gemini_analysis(
            self._baseline_payload("sha256:zzz"))
        self.assertEqual(first.id, second.id)
        self.assertEqual(len(project.appliance_ids), 1,
                         "Duplicate analysis must NOT create duplicate appliances")

    def test_different_image_hash_lands_separately(self):
        project = self._new_project()
        first = project.consume_gemini_analysis(
            self._baseline_payload("sha256:aaa"))
        second = project.consume_gemini_analysis(
            self._baseline_payload("sha256:bbb"))
        self.assertNotEqual(first.id, second.id)
        # Two separate analyses, each created its own appliance.
        self.assertEqual(len(project.appliance_ids), 2)

    def test_missing_image_hash_rejected(self):
        project = self._new_project()
        payload = self._baseline_payload(image_hash="")
        with self.assertRaises(UserError):
            project.consume_gemini_analysis(payload)

    def test_non_dict_payload_rejected(self):
        project = self._new_project()
        with self.assertRaises(UserError):
            project.consume_gemini_analysis("not a dict")

    # ------------------------------------------------------------------
    # End-to-end DoD — analyze_photo() with the mock backend
    # ------------------------------------------------------------------
    def test_dod_analyze_photo_end_to_end(self):
        """DoD: a photo produces a validated, schema-conformant analysis
        record with unconfirmed dimensions flagged."""
        project = self._new_project()
        # Synthesise a tiny PNG-like blob; mock backend ignores contents.
        attachment = self.env["ir.attachment"].create({
            "name": "fake_kitchen.jpg",
            "res_model": "sb.kitchen.project",
            "res_id": project.id,
            "raw": b"\xff\xd8\xff\xe0fake-jpeg",  # JPEG magic + filler
        })

        analysis = project.analyze_photo(attachment.id)

        self.assertTrue(analysis.exists())
        self.assertFalse(analysis.confirmed_by_human,
                         "DoD: dimensions must be flagged unconfirmed")
        # Mock returns 2 appliances (stove + sink).
        self.assertEqual(len(project.appliance_ids), 2)
        for app in project.appliance_ids:
            self.assertFalse(app.confirmed_by_human)

        # GAP-02 gate: project NOT yet ready for config engine.
        self.assertFalse(project.is_ready_for_config_engine())

        # Confirming the analysis + every appliance flips the gate.
        analysis.action_confirm()
        project.appliance_ids.write({"confirmed_by_human": True})
        self.assertTrue(project.is_ready_for_config_engine())
