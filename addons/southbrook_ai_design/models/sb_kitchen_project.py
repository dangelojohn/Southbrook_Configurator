# SPDX-License-Identifier: LGPL-3.0-only
"""sb.kitchen.project extension — analyze_photo() + consume_gemini_analysis()."""
import json
import logging

from odoo import _, api, models
from odoo.exceptions import UserError


_logger = logging.getLogger(__name__)


class SbKitchenProject(models.Model):
    _inherit = "sb.kitchen.project"

    # ------------------------------------------------------------------
    # Workspace action — analyze a photo via Gemini
    # ------------------------------------------------------------------
    def analyze_photo(self, attachment_id: int,
                      prompt_template_code: str = "default_v1"):
        """Read the ir.attachment payload, run it through Gemini (or
        mock), and land the analysis on this project. Idempotent by
        (project_id, image_hash) — calling twice with the same image
        returns the existing analysis record unchanged.
        """
        self.ensure_one()
        attachment = self.env["ir.attachment"].browse(attachment_id).exists()
        if not attachment:
            raise UserError(_("Attachment %s not found.") % attachment_id)

        image_bytes = attachment.raw or attachment.datas
        if isinstance(image_bytes, bytes) and not attachment.raw:
            # legacy `datas` field is base64
            import base64
            try:
                image_bytes = base64.b64decode(image_bytes)
            except Exception:
                pass
        if not image_bytes:
            raise UserError(_("Attachment %s has no payload.") % attachment_id)

        client = self.env["southbrook.gemini.client"]
        payload = client.analyze(image_bytes, prompt_template_code)
        return self.consume_gemini_analysis(payload)

    # ------------------------------------------------------------------
    # Lander — idempotent by image_hash
    # ------------------------------------------------------------------
    def consume_gemini_analysis(self, payload: dict):
        """Materialise a Gemini payload into sb.kitchen.ai.analysis +
        sb.kitchen.appliance records on this project. Idempotent: a
        second call with the same image_hash returns the existing
        analysis record without creating duplicates."""
        self.ensure_one()
        if not isinstance(payload, dict):
            raise UserError(_("Gemini payload must be a JSON object."))

        image_hash = payload.get("image_hash") or ""
        if not image_hash:
            raise UserError(_(
                "Gemini payload is missing image_hash — refusing to land."
            ))

        Analysis = self.env["sb.kitchen.ai.analysis"]
        Appliance = self.env["sb.kitchen.appliance"]

        # Idempotency dedup. We store the hash in raw_response_json as a
        # JSON-encoded blob; search by substring keeps the contract
        # surface minimal without an extra indexed column for now.
        existing = Analysis.search([
            ("project_id", "=", self.id),
            ("raw_response_json", "ilike", image_hash),
        ], limit=1)
        if existing:
            _logger.info("consume_gemini_analysis: deduped (image_hash=%s)",
                         image_hash)
            return existing

        room = payload.get("room") or {}
        analysis = Analysis.create({
            "project_id": self.id,
            "raw_response_json": json.dumps(payload),
            "sink_detected": bool(room.get("sink_detected")),
            "window_count": int(room.get("window_count") or 0),
            "room_door_count": int(room.get("room_door_count") or 0),
            "floor_area_m2_approx": room.get("floor_area_m2_approx") or 0.0,
            "ceiling_height_mm_approx":
                room.get("ceiling_height_mm_approx") or 0.0,
            "detected_appliances_json": json.dumps(payload.get("appliances") or []),
            "detected_dimensions_json": json.dumps(
                payload.get("dimensions_confidence") or {}
            ),
            "confirmed_by_human": False,
        })

        for idx, app in enumerate(payload.get("appliances") or [], start=10):
            Appliance.create({
                "project_id": self.id,
                "sequence": idx,
                "name": app.get("label") or app.get("kind") or "Appliance",
                "appliance_type": app.get("kind") or "other",
                "width_mm": app.get("width_mm_approx") or 0.0,
                "height_mm": app.get("height_mm_approx") or 0.0,
                "depth_mm": app.get("depth_mm_approx") or 0.0,
                "requires_clearance_mm":
                    int(app.get("requires_clearance_mm") or 0),
                "position_x": float(app.get("position_pct_along_wall") or 0.0),
                "position_y": 0.0,
                "confirmed_by_human": False,
            })

        # Link the analysis to the project.
        self.write({"ai_analysis_id": analysis.id})
        return analysis
