# SPDX-License-Identifier: LGPL-3.0-only
"""Tests for southbrook_room_capture — AI-assisted room capture backend.

Covers:
  * southbrook.room.capture (AbstractModel) — mock estimate short-
    circuit, the real (non-mock) JSON-parsing/normalization path via a
    monkeypatched `_call_anthropic`, upload validation, malformed/failed
    AI-call recovery, low-confidence flagging, geometry-validator
    gating, no-ir.attachment privacy guarantee.
  * controllers/main.py — the single JSON-RPC route: authenticated
    access, ownership rejection, upload validation, no ir.attachment /
    no southbrook.room side effects, existing_room payload shape.

Follows the `stubbed_request` pattern established in
southbrook_estimating_website/tests/test_room_api.py: swap the
`request` LocalProxy in EVERY controller module whose code path is
exercised. `_southbrook_resolve_order`'s `request` binding lives in
southbrook_estimating_website.controllers.main (the mixin's home
module), not in this addon's own controller module, so both must be
swapped for the duration of each call.

All external AI calls are mocked:
  * Model-layer tests either rely on `use_mock=True` (the addon
    default — never touches the network) or monkeypatch
    `southbrook.room.capture._call_anthropic` to return a canned raw
    Anthropic response dict, exercising the real JSON-parsing +
    normalization path with zero network access.
  * Controller tests exercise the mock-estimate short-circuit only
    (use_mock stays at its default True) — the model-layer tests above
    already cover the real-path parsing in isolation.

Run with:
    odoo --no-http --test-enable -u southbrook_room_capture \\
        -d <db> --stop-after-init --test-tags=southbrook_room_capture
"""
import base64
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

from odoo.tests import TransactionCase, tagged

from odoo.addons.southbrook_room_capture.controllers import (
    main as ctrl_capture,
)
from odoo.addons.southbrook_estimating_website.controllers import (
    main as ctrl_main,
)


# A 1x1 white PNG (valid, tiny) used as the "photo" in every test.
_TINY_PNG_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUB"
    "ATQIH1oAAAAASUVORK5CYII="
)


@contextmanager
def stubbed_request(env, user=None):
    """Swap `request` in both controller modules for the duration of
    the with-block. Mirrors southbrook_estimating_website/tests/
    test_room_api.py's helper — `_southbrook_resolve_order`'s `request`
    binding lives in ctrl_main (the mixin's home module), not in our
    own controllers.main.
    """
    saved_capture = ctrl_capture.request
    saved_main = ctrl_main.request
    mock = MagicMock()
    mock.env = env if user is None else env(user=user.id)
    mock.session = {}
    mock.params = {}
    ctrl_capture.request = mock
    ctrl_main.request = mock
    try:
        yield mock
    finally:
        ctrl_capture.request = saved_capture
        ctrl_main.request = saved_main


def _one_image():
    """A single valid base64-string image entry."""
    return _TINY_PNG_B64


def _one_image_dict(mime="image/png"):
    return {"data": _TINY_PNG_B64, "mime": mime}


@tagged("post_install", "-at_install", "southbrook", "southbrook_room_capture")
class TestRoomCaptureModel(TransactionCase):
    """Direct tests of the southbrook.room.capture AbstractModel."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Capture = cls.env["southbrook.room.capture"]

    def _set_real_backend(self):
        """Flip use_mock off + set a dummy key so analyze() takes the
        real-path branch — every test that does this ALSO monkeypatches
        `_call_anthropic`, so no network call is ever actually made."""
        ICP = self.env["ir.config_parameter"].sudo()
        ICP.set_param("southbrook_room_capture.use_mock", "False")
        ICP.set_param(
            "southbrook_room_capture.anthropic_api_key", "sk-test-dummy")

    # ------------------------------------------------------------------
    # Mock mode
    # ------------------------------------------------------------------
    def test_mock_estimate_returned(self):
        """use_mock defaults True — analyze() returns the mock estimate
        without any network access or configured API key."""
        result = self.Capture.analyze([_one_image_dict()])
        self.assertTrue(result["ok"], msg=result)
        self.assertIn("estimate", result)
        self.assertIsInstance(result["estimate"]["walls"], list)
        self.assertGreater(len(result["estimate"]["walls"]), 0)
        self.assertIn("low_confidence", result)

    # ------------------------------------------------------------------
    # Upload validation
    # ------------------------------------------------------------------
    def test_upload_validation_wrong_mime_rejected(self):
        result = self.Capture.analyze([_one_image_dict(mime="image/gif")])
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "invalid")

    def test_upload_validation_oversize_rejected(self):
        oversize = b"\x00" * (self.Capture._MAX_IMAGE_BYTES + 1)
        result = self.Capture.analyze(
            [{"data": oversize, "mime": "image/png"}])
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "invalid")

    def test_upload_validation_too_many_rejected(self):
        result = self.Capture.analyze([_one_image_dict()] * 6)
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "invalid")

    def test_upload_validation_empty_list_rejected(self):
        result = self.Capture.analyze([])
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "invalid")

    # ------------------------------------------------------------------
    # Real-path (non-mock) recovery — forced via a mocked transport
    # ------------------------------------------------------------------
    def test_malformed_ai_response_recovered(self):
        """A mocked transport returning non-JSON text must degrade to
        {"ok": False}, never raise."""
        self._set_real_backend()
        with patch.object(
            type(self.Capture), "_call_anthropic",
            return_value={
                "content": [{"type": "text", "text": "not json at all"}],
                "stop_reason": "end_turn",
            },
        ):
            result = self.Capture.analyze([_one_image_dict()])
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "malformed_response")

    def test_failed_ai_call_graceful(self):
        """`_call_anthropic` raising (network error / non-200) must
        degrade to a graceful error, never propagate."""
        self._set_real_backend()
        with patch.object(
            type(self.Capture), "_call_anthropic",
            side_effect=RuntimeError("Anthropic HTTP 503"),
        ):
            result = self.Capture.analyze([_one_image_dict()])
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "upstream_error")

    def test_refusal_stop_reason_graceful(self):
        self._set_real_backend()
        with patch.object(
            type(self.Capture), "_call_anthropic",
            return_value={"content": [], "stop_reason": "refusal"},
        ):
            result = self.Capture.analyze([_one_image_dict()])
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "refused")

    def test_daily_cap_kill_switch_blocks_real_call(self):
        """max_daily_calls=0 is a hard kill-switch — analyze() returns
        rate_limited WITHOUT ever reaching _call_anthropic."""
        self._set_real_backend()
        self.env["ir.config_parameter"].sudo().set_param(
            "southbrook_room_capture.max_daily_calls", "0")
        with patch.object(
            type(self.Capture), "_call_anthropic",
            side_effect=AssertionError("_call_anthropic must not be called"),
        ):
            result = self.Capture.analyze([_one_image_dict()])
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "rate_limited")

    def test_daily_cap_reached_blocks_further_real_calls(self):
        """Once today's counter hits the cap, subsequent real calls are
        rejected with rate_limited; calls within the cap still succeed."""
        self._set_real_backend()
        self.env["ir.config_parameter"].sudo().set_param(
            "southbrook_room_capture.max_daily_calls", "1")
        canned = {
            "content": [{"type": "text", "text": (
                '{"layout_shape": "straight", "walls": '
                '[{"name": "A", "length_mm": 3000, "confidence": 0.8}], '
                '"confidence": 0.8}')}],
            "stop_reason": "end_turn",
        }
        with patch.object(
            type(self.Capture), "_call_anthropic", return_value=canned,
        ):
            first = self.Capture.analyze([_one_image_dict()])
            second = self.Capture.analyze([_one_image_dict()])
        self.assertTrue(first["ok"], msg=first)
        self.assertFalse(second["ok"])
        self.assertEqual(second["error"], "rate_limited")

    def test_daily_cap_does_not_apply_to_mock(self):
        """The mock backend is free — the global cap only gates the paid
        real call, so mock analyze() never consumes quota."""
        self.env["ir.config_parameter"].sudo().set_param(
            "southbrook_room_capture.max_daily_calls", "0")
        result = self.Capture.analyze([_one_image_dict()])
        self.assertTrue(result["ok"], msg=result)

    def test_real_path_json_parsing_via_mocked_transport(self):
        """Exercise the real (non-mock) JSON-parsing + normalization
        path with a canned, well-formed raw Anthropic response —
        proving the parser (not just the mock short-circuit) works."""
        self._set_real_backend()
        canned_json = (
            '{"layout_shape": "l_shape", "ceiling_height_mm": 2440, '
            '"walls": [{"name": "Wall A", "length_mm": 3000, '
            '"confidence": 0.7}, {"name": "Wall B", "length_mm": 2400, '
            '"confidence": 0.65}], '
            '"constraints": [{"constraint_type": "window", '
            '"wall_index": 0, "distance_from_left_mm": 500, '
            '"width_mm": 900, "height_mm": 1200, '
            '"height_from_floor_mm": 900, "confidence": 0.8}], '
            '"assumptions": ["assumed standard ceiling height"], '
            '"warnings": [], "confidence": 0.7}'
        )
        with patch.object(
            type(self.Capture), "_call_anthropic",
            return_value={
                "content": [{"type": "text", "text": canned_json}],
                "stop_reason": "end_turn",
            },
        ):
            result = self.Capture.analyze([_one_image_dict()])
        self.assertTrue(result["ok"], msg=result)
        self.assertEqual(result["estimate"]["layout_shape"], "l_shape")
        self.assertEqual(len(result["estimate"]["walls"]), 2)
        self.assertEqual(len(result["estimate"]["constraints"]), 1)
        self.assertFalse(result["low_confidence"])

    def test_low_confidence_flagged(self):
        self._set_real_backend()
        low_conf_json = (
            '{"layout_shape": null, "ceiling_height_mm": null, '
            '"walls": [{"name": "Wall A", "length_mm": 2000, '
            '"confidence": 0.1}], "constraints": [], '
            '"assumptions": [], "warnings": ["very blurry photo"], '
            '"confidence": 0.15}'
        )
        with patch.object(
            type(self.Capture), "_call_anthropic",
            return_value={
                "content": [{"type": "text", "text": low_conf_json}],
                "stop_reason": "end_turn",
            },
        ):
            result = self.Capture.analyze([_one_image_dict()])
        self.assertTrue(result["ok"], msg=result)
        self.assertTrue(result["low_confidence"])

    def test_no_usable_walls_flags_low_confidence_even_if_score_high(self):
        """low_confidence must trigger on empty walls too, not only on
        the numeric confidence score."""
        self._set_real_backend()
        no_walls_json = (
            '{"layout_shape": null, "ceiling_height_mm": null, '
            '"walls": [], "constraints": [], "assumptions": [], '
            '"warnings": ["nothing usable in frame"], "confidence": 0.9}'
        )
        with patch.object(
            type(self.Capture), "_call_anthropic",
            return_value={
                "content": [{"type": "text", "text": no_walls_json}],
                "stop_reason": "end_turn",
            },
        ):
            result = self.Capture.analyze([_one_image_dict()])
        self.assertTrue(result["ok"], msg=result)
        self.assertTrue(result["low_confidence"])

    def test_analyze_normalization_missing_fields_no_crash(self):
        """Malformed/missing fields in an otherwise-valid JSON object
        must be coerced/skipped, never raise."""
        self._set_real_backend()
        garbage_but_valid_json = (
            '{"walls": "not-a-list", "confidence": "nope"}'
        )
        with patch.object(
            type(self.Capture), "_call_anthropic",
            return_value={
                "content": [{"type": "text", "text": garbage_but_valid_json}],
                "stop_reason": "end_turn",
            },
        ):
            result = self.Capture.analyze([_one_image_dict()])
        self.assertTrue(result["ok"], msg=result)
        self.assertEqual(result["estimate"]["walls"], [])
        self.assertEqual(result["estimate"]["confidence"], 0.0)
        self.assertTrue(result["low_confidence"])

    def test_max_tokens_stop_reason_recovered(self):
        """A possibly-truncated response (stop_reason=max_tokens) that
        still parsed cleanly should be used, with a warning appended,
        not treated as a hard failure."""
        self._set_real_backend()
        truncated_json = (
            '{"layout_shape": "straight", "ceiling_height_mm": 2400, '
            '"walls": [{"name": "Wall A", "length_mm": 3000, '
            '"confidence": 0.5}], "constraints": [], '
            '"assumptions": [], "warnings": [], "confidence": 0.5}'
        )
        with patch.object(
            type(self.Capture), "_call_anthropic",
            return_value={
                "content": [{"type": "text", "text": truncated_json}],
                "stop_reason": "max_tokens",
            },
        ):
            result = self.Capture.analyze([_one_image_dict()])
        self.assertTrue(result["ok"], msg=result)
        self.assertTrue(
            any("truncat" in w.lower() for w in result["estimate"]["warnings"])
        )

    # ------------------------------------------------------------------
    # Privacy
    # ------------------------------------------------------------------
    def test_no_ir_attachment_created(self):
        before = self.env["ir.attachment"].search_count([])
        self.Capture.analyze([_one_image_dict()])
        after = self.env["ir.attachment"].search_count([])
        self.assertEqual(before, after)

    # ------------------------------------------------------------------
    # Geometry gating — AI output is NOT exempt from the existing
    # validator.
    # ------------------------------------------------------------------
    def test_geometry_gated_by_validate_geometry(self):
        """The mock estimate's walls/constraints, fed through
        southbrook.room.validate_geometry (the SAME validator the
        wizard/controllers use before persistence), must return a
        list (empty for the deliberately-valid mock estimate), proving
        AI output is gated by the existing validator, not bypassed."""
        result = self.Capture.analyze([_one_image_dict()])
        estimate = result["estimate"]
        walls_payload = [{"length_mm": w["length_mm"]} for w in estimate["walls"]]
        constraints_payload = [
            {
                "wall_index": c["wall_index"],
                "distance_from_left_mm": c["distance_from_left_mm"],
                "width_mm": c["width_mm"],
            }
            for c in estimate["constraints"]
        ]
        errors = self.env["southbrook.room"].validate_geometry(
            walls_payload, constraints_payload, estimate["ceiling_height_mm"])
        self.assertIsInstance(errors, list)
        self.assertEqual(errors, [])  # the mock estimate is deliberately valid

        # A deliberately out-of-bounds constraint must produce errors.
        bad_constraints = [
            {"wall_index": 0, "distance_from_left_mm": 999999, "width_mm": 100},
        ]
        bad_errors = self.env["southbrook.room"].validate_geometry(
            walls_payload, bad_constraints, estimate["ceiling_height_mm"])
        self.assertIsInstance(bad_errors, list)
        self.assertTrue(bad_errors)

    # ------------------------------------------------------------------
    # existing_room payload shape
    # ------------------------------------------------------------------
    def test_existing_room_payload_shape(self):
        result = self.Capture.analyze([_one_image_dict()])
        existing_room = self.Capture._estimate_to_existing_room(
            result["estimate"])
        for key in (
            "name", "room_type", "layout_shape", "ceiling_height_mm",
            "unit_preference", "walls", "assumptions", "warnings",
            "confidence",
        ):
            self.assertIn(key, existing_room)
        self.assertIsInstance(existing_room["walls"], list)
        self.assertGreater(len(existing_room["walls"]), 0)
        for wall in existing_room["walls"]:
            for key in (
                "name", "length_mm", "wall_order", "confidence",
                "constraints",
            ):
                self.assertIn(key, wall)
            self.assertIsInstance(wall["constraints"], list)
            for constraint in wall["constraints"]:
                for key in (
                    "constraint_type", "distance_from_left_mm", "width_mm",
                    "height_mm", "height_from_floor_mm", "notes",
                    "confidence",
                ):
                    self.assertIn(key, constraint)


@tagged("post_install", "-at_install", "southbrook", "southbrook_room_capture")
class TestRoomCaptureController(TransactionCase):
    """Tests of the JSON-RPC controller layer."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create({
            "name": "Test Customer Room Capture",
            "email": "test_room_capture@southbrook.test",
        })
        cls.order = cls.env["sale.order"].create({
            "partner_id": cls.partner.id,
        })

        cls.other_partner = cls.env["res.partner"].create({
            "name": "Stranger Room Capture",
            "email": "stranger_room_capture@southbrook.test",
        })

        # Portal user (res.users.share=True) NOT related to cls.partner
        # in any way — used for the ownership-rejection test. Odoo 19
        # renamed res.users.groups_id -> group_ids.
        portal_group = cls.env.ref("base.group_portal")
        cls.portal_user = cls.env["res.users"].create({
            "name": "Portal Stranger Room Capture",
            "login": "portal_stranger_room_capture@southbrook.test",
            "partner_id": cls.other_partner.id,
            "group_ids": [(6, 0, [portal_group.id])],
        })

        cls.controller = ctrl_capture.SouthbrookRoomCaptureApi()

    def test_authenticated_access_returns_mock_estimate(self):
        """Default env user in TransactionCase is an internal (non-
        share) user, so ownership resolves regardless of partner."""
        with stubbed_request(self.env):
            result = self.controller.southbrook_api_room_analyze_photos(
                self.order.id, images=[_one_image()],
            )
        self.assertTrue(result.get("ok"), msg=result)
        self.assertIn("estimate", result)
        self.assertIn("existing_room", result)
        self.assertIn("low_confidence", result)

    def test_ownership_rejection_for_non_owning_portal_user(self):
        with stubbed_request(self.env, user=self.portal_user):
            result = self.controller.southbrook_api_room_analyze_photos(
                self.order.id, images=[_one_image()],
            )
        self.assertEqual(result.get("error"), "forbidden")

    def test_wrong_mime_rejected(self):
        with stubbed_request(self.env):
            result = self.controller.southbrook_api_room_analyze_photos(
                self.order.id,
                images=[{"data": _one_image(), "mime": "application/pdf"}],
            )
        self.assertEqual(result.get("error"), "invalid")

    def test_oversize_rejected(self):
        oversize_b64 = base64.b64encode(
            b"\x00" * (8 * 1024 * 1024 + 1)).decode()
        with stubbed_request(self.env):
            result = self.controller.southbrook_api_room_analyze_photos(
                self.order.id,
                images=[{"data": oversize_b64, "mime": "image/png"}],
            )
        self.assertEqual(result.get("error"), "invalid")

    def test_too_many_images_rejected(self):
        with stubbed_request(self.env):
            result = self.controller.southbrook_api_room_analyze_photos(
                self.order.id, images=[_one_image()] * 6,
            )
        self.assertEqual(result.get("error"), "invalid")

    def test_empty_list_rejected(self):
        with stubbed_request(self.env):
            result = self.controller.southbrook_api_room_analyze_photos(
                self.order.id, images=[],
            )
        self.assertEqual(result.get("error"), "invalid")

    def test_no_ir_attachment_created_end_to_end(self):
        before = self.env["ir.attachment"].search_count([])
        with stubbed_request(self.env):
            self.controller.southbrook_api_room_analyze_photos(
                self.order.id, images=[_one_image()],
            )
        after = self.env["ir.attachment"].search_count([])
        self.assertEqual(before, after)

    def test_no_southbrook_room_records_created(self):
        """The controller must never create southbrook.room / wall /
        constraint records — only the wizard, after human review,
        does that."""
        before = self.env["southbrook.room"].search_count([])
        with stubbed_request(self.env):
            self.controller.southbrook_api_room_analyze_photos(
                self.order.id, images=[_one_image()],
            )
        after = self.env["southbrook.room"].search_count([])
        self.assertEqual(before, after)
