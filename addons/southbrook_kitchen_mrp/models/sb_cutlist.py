# SPDX-License-Identifier: LGPL-3.0-only
"""sb.cutlist + sb.cutlist.line — the panel cut list for one MO.

Generation source of truth: shared.southbrook_dims.panel_cut_list — the
same module Odoo's G1 test imports and the FreeCAD bridge renders from.
Drift between cutlist geometry and rendered geometry is therefore
impossible by construction as long as G1 passes.

Toe-kick is integrated into the side panels and is NOT emitted as a
cutlist line. The shared.southbrook_dims.toe_kick() function returns a
metadata dict, never a panel tuple — and the generation code asserts
that contract by never iterating the toe_kick key.
"""
import json
import logging
from typing import Any, Dict, Optional

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


PANEL_NAMES = [
    ("side_L", "Side (Left)"),
    ("side_R", "Side (Right)"),
    ("top", "Top"),
    ("bottom", "Bottom"),
    ("back", "Back"),
    ("adjustable_shelf", "Adjustable Shelf"),
    ("door", "Door / Drawer Face"),
]

SUBSTRATE_CHOICES = [
    ("melamine_white_5_8", "5/8\" White Melamine"),
    ("melamine_oak_5_8", "5/8\" Oak Melamine"),
    ("mdf_5_8", "5/8\" MDF"),
    ("hardboard_1_4", "1/4\" Hardboard (Backs)"),
    ("ply_3_4", "3/4\" Plywood (Doors)"),
]

GRAIN_DIRECTIONS = [
    ("with_grain", "With Grain (Length)"),
    ("cross_grain", "Cross Grain (Width)"),
    ("no_grain", "No Grain"),
]

CUTLIST_STATES = [
    ("draft", "Draft"),
    ("exported", "Exported to Nesting"),
    ("nested", "Nested"),
    ("done", "Done"),
]


# Substrate defaults per panel type. Backs are hardboard; doors are plywood
# (or whatever the configurator-resolved door spec says — future wiring);
# everything else is 5/8" white melamine carcass standard.
DEFAULT_SUBSTRATE_BY_PANEL = {
    "side_L": "melamine_white_5_8",
    "side_R": "melamine_white_5_8",
    "top": "melamine_white_5_8",
    "bottom": "melamine_white_5_8",
    "back": "hardboard_1_4",
    "adjustable_shelf": "melamine_white_5_8",
    "door": "ply_3_4",
}


class SbCutlist(models.Model):
    _name = "sb.cutlist"
    _description = "Southbrook Cabinet Cut List"
    _order = "id desc"

    name = fields.Char(required=True, default=lambda self: _("New"))
    mo_id = fields.Many2one(
        comodel_name="mrp.production",
        string="Manufacturing Order",
        ondelete="cascade",
        index=True,
    )
    state = fields.Selection(
        CUTLIST_STATES,
        default="draft",
        tracking=True,
        required=True,
    )
    line_ids = fields.One2many(
        comodel_name="sb.cutlist.line",
        inverse_name="cutlist_id",
        string="Cut List Lines",
    )
    line_count = fields.Integer(compute="_compute_line_count", store=True)

    # Nesting round-trip stash. Stored as JSON so the cutting/nesting
    # division can carry sheet-yield + waste metrics back without us
    # needing a model schema for every nesting tool variant.
    nesting_result_json = fields.Text(string="Nesting Result (JSON)")

    @api.depends("line_ids")
    def _compute_line_count(self):
        for r in self:
            r.line_count = len(r.line_ids)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", _("New")) == _("New"):
                vals["name"] = self.env["ir.sequence"].next_by_code(
                    "sb.cutlist"
                ) or _("New")
        return super().create(vals_list)

    # ------------------------------------------------------------------
    # Generation from panel_cut_list (shared.southbrook_dims)
    # ------------------------------------------------------------------
    @api.model
    def generate_lines_from_panel_dict(
        self,
        cutlist,
        panel_dict: Dict[str, Any],
    ):
        """Create sb.cutlist.line records from a shared.southbrook_dims
        panel_cut_list() output dict.

        toe_kick is INTENTIONALLY SKIPPED — its value in the panel dict
        is a metadata descriptor (dict), not a (length, width, thickness)
        tuple, and emitting it as a cutlist line would create a phantom
        panel that the shop floor would then try to cut. That contract is
        enforced here AND in the corresponding G1 test.
        """
        Line = self.env["sb.cutlist.line"]
        keys_to_emit = ("side_L", "side_R", "top", "bottom", "back",
                        "adjustable_shelf", "door")
        shelf_count = int(panel_dict.get("shelf_count") or 0)

        for key in keys_to_emit:
            value = panel_dict.get(key)
            if value is None:
                continue
            if not isinstance(value, tuple) or len(value) != 3:
                # Defensive: shared.southbrook_dims schema is locked, but
                # a regression elsewhere would surface here cleanly.
                raise UserError(_(
                    "Panel '%(panel)s' has unexpected shape %(value)s — "
                    "expected (length_mm, width_mm, thickness_mm)."
                ) % {"panel": key, "value": value})

            length_mm, width_mm, thickness_mm = value
            qty = 1
            if key == "adjustable_shelf" and shelf_count > 0:
                qty = shelf_count

            Line.create({
                "cutlist_id": cutlist.id,
                "panel_name": key,
                "qty": qty,
                "length_mm": length_mm,
                "width_mm": width_mm,
                "thickness_mm": thickness_mm,
                "substrate": DEFAULT_SUBSTRATE_BY_PANEL.get(
                    key, "melamine_white_5_8"
                ),
                "grain_dir": "with_grain" if key in (
                    "side_L", "side_R", "door"
                ) else "no_grain",
                "edge_banding_config": json.dumps(
                    self._default_edge_banding(key)
                ),
            })

    def _default_edge_banding(self, panel_name: str) -> Dict[str, bool]:
        """Phase-1 edge-banding default per panel. Per-edge precision
        lands when the Accucutt-style nest spec is finalised (Module 4
        is the structural seam, not the substantive precision)."""
        if panel_name in ("top", "bottom"):
            return {"front": True, "back": False, "left": False, "right": False}
        if panel_name in ("side_L", "side_R"):
            return {"front": True, "back": False, "left": False, "right": False}
        if panel_name == "door":
            return {"front": True, "back": True, "left": True, "right": True}
        return {"front": False, "back": False, "left": False, "right": False}

    # ------------------------------------------------------------------
    # Nesting interface (round-trip stub)
    # ------------------------------------------------------------------
    def to_nesting_envelope(self) -> dict:
        """Return a deterministic JSON envelope the cutting/nesting
        division can consume. Versioned so future schema changes don't
        silently break consumers."""
        self.ensure_one()
        return {
            "schema": "southbrook.nesting.v1",
            "cutlist_id": self.id,
            "cutlist_name": self.name,
            "mo_id": self.mo_id.id if self.mo_id else None,
            "panels": [
                {
                    "panel_name": ln.panel_name,
                    "qty": ln.qty,
                    "length_mm": ln.length_mm,
                    "width_mm": ln.width_mm,
                    "thickness_mm": ln.thickness_mm,
                    "substrate": ln.substrate,
                    "grain_dir": ln.grain_dir,
                    "edge_banding": json.loads(ln.edge_banding_config or "{}"),
                }
                for ln in self.line_ids
            ],
        }

    def from_nesting_result(self, payload: dict) -> None:
        """Accept a nesting result and advance state to nested.

        Expected payload shape:
          {
            "schema": "southbrook.nesting.v1",
            "sheets_used": int,
            "yield_pct": float,
            "waste_pct": float,
            ...
          }
        Full schema validation is intentionally out of Module 4 scope —
        the interface is what matters; the cutting/nesting division
        producer is a different deliverable.
        """
        self.ensure_one()
        if not isinstance(payload, dict):
            raise UserError(_("Nesting result must be a JSON object."))
        if payload.get("schema") != "southbrook.nesting.v1":
            raise UserError(_(
                "Nesting result schema mismatch: expected "
                "southbrook.nesting.v1, got %s"
            ) % payload.get("schema"))
        self.write({
            "nesting_result_json": json.dumps(payload),
            "state": "nested",
        })


class SbCutlistLine(models.Model):
    _name = "sb.cutlist.line"
    _description = "Southbrook Cabinet Cut List Line"
    _order = "cutlist_id, sequence, id"

    cutlist_id = fields.Many2one(
        comodel_name="sb.cutlist",
        ondelete="cascade",
        required=True,
        index=True,
    )
    sequence = fields.Integer(default=10)
    panel_name = fields.Selection(PANEL_NAMES, required=True)
    qty = fields.Integer(default=1, required=True)
    length_mm = fields.Float(string="Length (mm)", digits=(8, 3))
    width_mm = fields.Float(string="Width (mm)", digits=(8, 3))
    thickness_mm = fields.Float(string="Thickness (mm)", digits=(8, 3))
    substrate = fields.Selection(
        SUBSTRATE_CHOICES, default="melamine_white_5_8",
    )
    grain_dir = fields.Selection(GRAIN_DIRECTIONS, default="no_grain")
    edge_banding_config = fields.Text(
        string="Edge Banding Config (JSON)",
        help="Per-edge banding flags as JSON: "
             "{'front': bool, 'back': bool, 'left': bool, 'right': bool}",
    )
