# SPDX-License-Identifier: LGPL-3.0-only
"""Module 6 — schema validator tests against G3 §4.1."""
from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "ai_design", "validator")
class TestValidator(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Client = cls.env["southbrook.gemini.client"]

    def _baseline(self):
        return {
            "schema": "southbrook.gemini.room_analysis.v1",
            "model": "test", "ts": "2026-06-09T18:00:00Z",
            "image_hash": "sha256:abc",
            "room": {
                "sink_detected": False, "window_count": 0, "room_door_count": 0,
                "floor_area_m2_approx": 10.0, "ceiling_height_mm_approx": 2400,
                "wall_segments": [{"id": "wall_north", "length_mm_approx": 3000,
                                   "has_windows": [], "has_doors": []}],
            },
            "appliances": [], "dimensions_confidence": {}, "model_warnings": [],
        }

    def test_accepts_valid_payload(self):
        payload = self._baseline()
        out = self.Client._validate(payload)
        self.assertEqual(out["schema"], "southbrook.gemini.room_analysis.v1")
        self.assertEqual(out["model_warnings"], [])

    def test_rejects_wrong_schema(self):
        payload = self._baseline()
        payload["schema"] = "not.our.schema"
        with self.assertRaises(UserError):
            self.Client._validate(payload)

    def test_rejects_non_dict(self):
        with self.assertRaises(UserError):
            self.Client._validate("a string, not a dict")

    def test_rejects_orphan_wall_segment_id(self):
        payload = self._baseline()
        payload["appliances"] = [{
            "kind": "stove", "label": "Phantom stove",
            "wall_segment_id": "wall_does_not_exist",
            "width_mm_approx": 762, "height_mm_approx": 914,
            "depth_mm_approx": 610, "confidence": 0.8,
        }]
        with self.assertRaises(UserError):
            self.Client._validate(payload)

    def test_coerces_unknown_appliance_kind_to_other(self):
        payload = self._baseline()
        payload["appliances"] = [{
            "kind": "espresso_machine", "label": "Wonky",
            "wall_segment_id": "wall_north",
            "width_mm_approx": 300, "height_mm_approx": 400,
            "depth_mm_approx": 300, "confidence": 0.7,
        }]
        out = self.Client._validate(payload)
        self.assertEqual(out["appliances"][0]["kind"], "other")
        self.assertTrue(any("espresso_machine" in w for w in out["model_warnings"]))

    def test_nulls_out_of_range_ceiling(self):
        payload = self._baseline()
        payload["room"]["ceiling_height_mm_approx"] = 9999
        out = self.Client._validate(payload)
        self.assertIsNone(out["room"]["ceiling_height_mm_approx"])
        self.assertTrue(any("ceiling" in w for w in out["model_warnings"]))

    def test_nulls_out_of_range_wall(self):
        payload = self._baseline()
        payload["room"]["wall_segments"][0]["length_mm_approx"] = 999999
        out = self.Client._validate(payload)
        self.assertIsNone(out["room"]["wall_segments"][0]["length_mm_approx"])
        self.assertTrue(any("wall" in w for w in out["model_warnings"]))

    def test_nulls_out_of_range_appliance_dim(self):
        payload = self._baseline()
        payload["appliances"] = [{
            "kind": "stove", "label": "Giant",
            "wall_segment_id": "wall_north",
            "width_mm_approx": 99999, "height_mm_approx": 914,
            "depth_mm_approx": 610, "confidence": 0.8,
        }]
        out = self.Client._validate(payload)
        self.assertIsNone(out["appliances"][0]["width_mm_approx"])

    def test_clamps_confidence_out_of_range(self):
        payload = self._baseline()
        payload["appliances"] = [{
            "kind": "stove", "label": "Inflated confidence",
            "wall_segment_id": "wall_north",
            "width_mm_approx": 762, "height_mm_approx": 914,
            "depth_mm_approx": 610, "confidence": 1.5,
        }]
        out = self.Client._validate(payload)
        self.assertEqual(out["appliances"][0]["confidence"], 1.0)

    def test_clamps_dimensions_confidence(self):
        payload = self._baseline()
        payload["dimensions_confidence"] = {"wall_lengths": 1.7}
        out = self.Client._validate(payload)
        self.assertEqual(out["dimensions_confidence"]["wall_lengths"], 1.0)

    def test_mock_response_passes_validator(self):
        out = self.Client.analyze(b"some-fake-image-bytes")
        self.assertEqual(out["schema"], "southbrook.gemini.room_analysis.v1")
        # image_hash gets stamped by analyze() so the lander can dedupe.
        self.assertTrue(out["image_hash"].startswith("sha256:"))
