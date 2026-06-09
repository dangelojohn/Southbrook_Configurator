# SPDX-License-Identifier: LGPL-3.0-only
"""southbrook.config.engine — the placement algorithm.

Implements the algorithm in docs/config_engine_spec.md §4. Idempotent +
deterministic per §9 — re-running on identical inputs yields a byte-
identical output (so ECO impact analysis is tractable).
"""
import json
import logging
from typing import Any, Dict, List, Optional, Tuple

from odoo import _, api, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


ENGINE_VERSION = "1.0"
SCHEMA_VERSION = "southbrook.config_engine.v1"

# Cabinet widths the engine may place. In a future iteration this comes
# from product.template.DimensionEnvelope.items; for Module 7 scope we
# hold the canonical set inline so the algorithm is self-contained.
AVAILABLE_BASE_WIDTHS_MM = [225, 300, 375, 450, 600, 750, 800, 900]

# Default per-kind clearance fallback when no sb.placement.rule matches.
# Aligns with the table in G4 §6.
DEFAULT_CLEARANCES = {
    "stove":      {"left_mm": 30, "right_mm": 30},
    "fridge":     {"left_mm": 25, "right_mm": 25},
    "dishwasher": {"left_mm": 0,  "right_mm": 0},
    "sink":       {"left_mm": 0,  "right_mm": 0},
    "microwave":  {"left_mm": 0,  "right_mm": 0},
    "oven_wall":  {"left_mm": 0,  "right_mm": 0},
    "hood":       {"left_mm": 0,  "right_mm": 0},
    "other":      {"left_mm": 0,  "right_mm": 0},
}


class SouthbrookConfigEngine(models.AbstractModel):
    """Cabinet placement engine — env['southbrook.config.engine']."""
    _name = "southbrook.config.engine"
    _description = "Southbrook Configuration Engine"

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------
    @api.model
    def place_for_project(self, project, design_option=None) -> dict:
        """Produce a placement plan for a project (and optionally the
        specific design option). Returns the G4 §2 envelope dict.

        Raises UserError when project is not ready (GAP-02 gate)."""
        if not project.is_ready_for_config_engine():
            raise UserError(_(
                "Project %s is not ready for the configuration engine. "
                "AI analysis and every appliance must be human-confirmed "
                "first (GAP-02 gate)."
            ) % project.code)

        rules = self._load_rules()
        room = self._read_room(project)
        appliances = self._read_appliances(project)

        runs: List[dict] = []
        warnings: List[str] = []
        errors: List[str] = []

        # One run per wall segment that carries appliances or capacity.
        for segment in room["wall_segments"]:
            try:
                run = self._place_run(
                    segment=segment,
                    appliances=[a for a in appliances if a["wall_segment_id"] == segment["id"]],
                    theme=project.theme or "signature",
                    rules=rules,
                    warnings=warnings,
                )
                runs.append(run)
            except UserError as exc:
                errors.append(f"{segment['id']}: {exc.args[0]}")

        envelope = {
            "schema": SCHEMA_VERSION,
            "engine_version": ENGINE_VERSION,
            "project_id": project.id,
            "design_option_id": design_option.id if design_option else None,
            "theme": project.theme,
            "runs": runs,
            "warnings": warnings,
            "errors": errors,
        }
        if design_option:
            design_option.placement_data_json = json.dumps(envelope)
        return envelope

    # ------------------------------------------------------------------
    # Input readers
    # ------------------------------------------------------------------
    @api.model
    def _read_room(self, project) -> dict:
        analysis = project.ai_analysis_id
        if not analysis or not analysis.raw_response_json:
            raise UserError(_(
                "Project has no raw AI analysis payload to read room "
                "geometry from."
            ))
        try:
            raw = json.loads(analysis.raw_response_json)
        except json.JSONDecodeError as exc:
            raise UserError(_("AI analysis JSON is malformed: %s") % exc)
        return raw.get("room") or {"wall_segments": []}

    @api.model
    def _read_appliances(self, project) -> List[dict]:
        """Sorted, normalised appliance list. Sort order is deterministic
        per G4 §9 (position_x, position_y, id)."""
        appliances = []
        analysis = project.ai_analysis_id
        wall_lookup = {}
        if analysis and analysis.raw_response_json:
            try:
                raw = json.loads(analysis.raw_response_json)
                for app in raw.get("appliances") or []:
                    wall_lookup[app.get("label")] = app.get("wall_segment_id")
            except json.JSONDecodeError:
                pass

        for app in project.appliance_ids.sorted(
            lambda a: (a.position_x, a.position_y, a.id),
        ):
            appliances.append({
                "id": app.id,
                "kind": app.appliance_type or "other",
                "label": app.name,
                "wall_segment_id": wall_lookup.get(app.name),
                "position_pct": app.position_x,
                "width_mm": app.width_mm,
                "requires_clearance_mm": app.requires_clearance_mm,
            })
        return appliances

    @api.model
    def _load_rules(self) -> Dict[str, List[dict]]:
        """Load active placement rules into a kind-indexed dict."""
        Rule = self.env["sb.placement.rule"]
        records = Rule.search([("active", "=", True)],
                              order="kind, priority, id")
        out: Dict[str, List[dict]] = {}
        for r in records:
            out.setdefault(r.kind, []).append({
                "id": r.id,
                "name": r.name,
                "theme": r.theme,
                "appliance_kind": r.appliance_kind,
                "priority": r.priority,
                "payload": r.to_dict(),
            })
        return out

    # ------------------------------------------------------------------
    # Per-segment placement
    # ------------------------------------------------------------------
    @api.model
    def _place_run(self, segment, appliances, theme, rules, warnings):
        """Place one wall segment. Returns a run dict per G4 §2."""
        wall_length = float(segment.get("length_mm_approx") or 0)
        if wall_length <= 0:
            raise UserError(_("Wall segment has no length to place into."))

        # Sort appliances by position along this wall.
        sorted_apps = sorted(appliances, key=lambda a: a["position_pct"])

        # Compute the appliance slots (start_x, end_x) along the wall.
        slots: List[dict] = []
        for app in sorted_apps:
            center_x = app["position_pct"] * wall_length
            half = app["width_mm"] / 2.0
            clearance = self._resolve_clearance(app, theme, rules)
            slot_left = center_x - half - clearance["left_mm"]
            slot_right = center_x + half + clearance["right_mm"]
            slots.append({
                "appliance": app,
                "slot_left": slot_left,
                "slot_right": slot_right,
                "clearance_left": clearance["left_mm"],
                "clearance_right": clearance["right_mm"],
            })

        # Pack cabinets into the gaps between slots.
        cabinets: List[dict] = []
        cursor = 0.0
        seq = 1
        preferred_widths = self._resolve_width_preference(theme, rules)

        for slot in slots:
            gap_len = slot["slot_left"] - cursor
            if gap_len < 0:
                raise UserError(_(
                    "Appliance %s at %.0fmm overlaps prior cabinet/appliance "
                    "(gap_len=%.1f). Clearance violation."
                ) % (slot["appliance"]["label"], slot["slot_left"], gap_len))
            packed = self._pack_stretch(gap_len, preferred_widths)
            for cab in packed:
                cab["seq"] = seq
                seq += 1
                cab["x_offset_mm"] = cursor
                cursor += cab["width_mm"]
                cabinets.append(cab)
            # Place the appliance slot itself (no cabinet here).
            cursor = slot["slot_right"]

        # Final stretch after the last appliance to the end of the wall.
        gap_len = wall_length - cursor
        if gap_len < 0:
            raise UserError(_(
                "Last appliance slot extends past wall end by %.1fmm — "
                "wall too short for appliance set."
            ) % (-gap_len))
        packed = self._pack_stretch(gap_len, preferred_widths)
        for cab in packed:
            cab["seq"] = seq
            seq += 1
            cab["x_offset_mm"] = cursor
            cursor += cab["width_mm"]
            cabinets.append(cab)

        # Reconcile width-fit. Cursor must be within ±1mm of wall_length.
        leftover = wall_length - cursor
        if abs(leftover) > 1.0:
            # Add a filler at the right end per Rule F1.
            cabinets.append({
                "seq": seq,
                "type": "filler",
                "width_mm": round(leftover, 1),
                "x_offset_mm": cursor,
            })
            warnings.append(
                f"{segment['id']}: {leftover:.1f}mm leftover absorbed as filler at right end"
            )

        appliance_slots = [
            {
                "appliance_id": s["appliance"]["id"],
                "kind": s["appliance"]["kind"],
                "x_offset_mm": s["slot_left"] + s["clearance_left"],
                "width_mm": s["appliance"]["width_mm"],
                "clearance_mm": s["clearance_left"] + s["clearance_right"],
            }
            for s in slots
        ]

        return {
            "id": f"run_{segment['id']}",
            "wall_segment_id": segment["id"],
            "anchor_x_mm": 0, "anchor_y_mm": 0, "direction": "east",
            "length_mm": wall_length,
            "cabinets": cabinets,
            "appliance_slots": appliance_slots,
        }

    # ------------------------------------------------------------------
    # Per-stretch packing — greedy-then-balance per G4 §4
    # ------------------------------------------------------------------
    @api.model
    def _pack_stretch(self, length_mm, preferred_widths) -> List[dict]:
        """Pack a stretch of given length using preferred widths.

        Greedy: pick the largest preferred width that fits, recurse.
        If the recursion would leave an unpaired narrow gap, back up
        one step and try the next-preferred width."""
        if length_mm <= 0:
            return []
        if length_mm < min(preferred_widths or [225]) - 1:
            # Cannot fit any cabinet; return empty (the caller emits a
            # filler from the leftover).
            return []

        widths_desc = sorted(preferred_widths, reverse=True)
        # Forward greedy.
        plan = self._greedy_pack(length_mm, widths_desc)
        if plan is not None:
            return plan
        # Fall back to single largest-that-fits + filler at the end.
        for w in widths_desc:
            if w <= length_mm:
                return [{"width_mm": float(w), "door_count": 2 if w >= 600 else 1,
                          "drawer_count": 0, "soft_close": True}]
        return []

    def _greedy_pack(self, length_mm: float,
                     widths_desc: List[int]) -> Optional[List[dict]]:
        """Recursive greedy fit with single-level backtracking."""
        if abs(length_mm) <= 1.0:
            return []
        for w in widths_desc:
            if w > length_mm + 1:
                continue
            sub = self._greedy_pack(length_mm - w, widths_desc)
            if sub is not None:
                cab = {"width_mm": float(w),
                       "door_count": 2 if w >= 600 else 1,
                       "drawer_count": 0, "soft_close": True}
                return [cab] + sub
        return None  # No partition fits

    # ------------------------------------------------------------------
    # Rule resolution
    # ------------------------------------------------------------------
    @api.model
    def _resolve_clearance(self, app, theme, rules) -> dict:
        """Pick the clearance rule for this appliance + theme.

        Priority: app.requires_clearance_mm override > theme-specific rule
        > default-for-kind > DEFAULT_CLEARANCES."""
        override = app.get("requires_clearance_mm") or 0
        if override:
            return {"left_mm": override, "right_mm": override}

        for r in rules.get("clearance") or []:
            if r["appliance_kind"] != app["kind"]:
                continue
            if r["theme"] and r["theme"] != theme:
                continue
            return r["payload"]

        return DEFAULT_CLEARANCES.get(app["kind"], {"left_mm": 0, "right_mm": 0})

    @api.model
    def _resolve_width_preference(self, theme, rules) -> List[int]:
        """Pick the preferred-widths list for this theme."""
        for r in rules.get("width_pref") or []:
            if r["theme"] == theme:
                widths = r["payload"].get("preferred_widths_mm")
                if widths:
                    return widths
        return AVAILABLE_BASE_WIDTHS_MM
