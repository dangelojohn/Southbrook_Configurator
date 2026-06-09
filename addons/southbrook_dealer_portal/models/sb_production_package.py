# SPDX-License-Identifier: LGPL-3.0-only
"""sb.production.package extension — KD flat-pack export.

KD = Knock-Down = shipped disassembled with pre-drilled hardware holes,
assembled on site. The Central Kitchens channel consumes the export
JSON; for Module 9 scope we ship the envelope structure + the action
that emits it. The consumer-side cabling lands when a real Central
Kitchens dealer is signed."""
import json
from typing import Dict, List

from odoo import _, fields, models
from odoo.exceptions import UserError


KD_ENVELOPE_SCHEMA = "southbrook.kd_flatpack.v1"


class SbProductionPackage(models.Model):
    _inherit = "sb.production.package"

    is_kd_variant = fields.Boolean(
        string="KD Flat-Pack Variant",
        help="When True this package ships as knock-down (assembled "
             "on site). KD export includes pre-drilled hole positions.",
    )

    def export_kd_envelope(self) -> dict:
        """Emit the JSON envelope a KD-channel dealer consumes.

        Per SYN-05: each panel carries its pre-drilled hole positions so
        the destination shop assembles without re-drilling. Hole positions
        are derived from each panel's edge_banding_config + standard
        cam-lock + dowel positions for the carcass.
        """
        self.ensure_one()
        if not self.cutlist_id:
            raise UserError(_(
                "Production package %s has no cutlist; cannot export KD."
            ) % self.name)

        panels: List[Dict] = []
        for line in self.cutlist_id.line_ids:
            panels.append({
                "panel_name": line.panel_name,
                "qty": line.qty,
                "length_mm": line.length_mm,
                "width_mm": line.width_mm,
                "thickness_mm": line.thickness_mm,
                "substrate": line.substrate,
                "grain_dir": line.grain_dir,
                "predrilled_holes": self._derive_predrilled_holes(line),
            })

        hardware: List[Dict] = []
        if self.hardware_package_id:
            for ln in self.hardware_package_id.line_ids:
                hardware.append({
                    "marathon_sku": ln.product_id.x_marathon_sku,
                    "category": ln.hardware_category,
                    "qty": ln.qty,
                    "pricing_pending": ln.pricing_pending,
                })

        return {
            "schema": KD_ENVELOPE_SCHEMA,
            "production_package_id": self.id,
            "production_package_name": self.name,
            "mo_id": self.mo_id.id if self.mo_id else None,
            "panels": panels,
            "hardware": hardware,
            "warnings": [],
        }

    def _derive_predrilled_holes(self, panel) -> List[Dict]:
        """Phase-1 hole-position derivation per SYN-05.

        Standard frameless euro construction:
          Side panels: hinge cup at top 95mm + bottom 95mm from each end
                       (for cabinets <=720mm), 32mm system-line dowels
                       on the inside face at 32mm grid.
          Top/Bottom:  cam-lock holes at each corner, 50mm in from edges.
          Back:        no holes (captures into rabbet).
          Shelf:       no holes (sits on shelf pins).
          Door:        hinge-cup holes at 95mm from top + bottom edges.

        Module-9 ships the constants + the panel-name dispatch. Per-
        cabinet refinement (overlay vs. inset, special hinge angles) is
        a Phase-2 refinement.
        """
        holes: List[Dict] = []
        name = panel.panel_name
        if name in ("side_L", "side_R"):
            holes.append({"kind": "hinge_cup", "x_mm": 35,
                          "y_mm": 95, "diameter_mm": 35})
            holes.append({"kind": "hinge_cup", "x_mm": 35,
                          "y_mm": panel.length_mm - 95, "diameter_mm": 35})
            # 32mm system line on inside face.
            y = 65
            while y < panel.length_mm - 65:
                holes.append({"kind": "system_line", "x_mm": 37,
                              "y_mm": y, "diameter_mm": 5})
                y += 32
        elif name in ("top", "bottom"):
            for corner_x in (50, panel.length_mm - 50):
                for corner_y in (50, panel.width_mm - 50):
                    holes.append({"kind": "cam_lock", "x_mm": corner_x,
                                  "y_mm": corner_y, "diameter_mm": 10})
        elif name == "door":
            holes.append({"kind": "hinge_cup", "x_mm": 22,
                          "y_mm": 95, "diameter_mm": 35})
            holes.append({"kind": "hinge_cup", "x_mm": 22,
                          "y_mm": panel.length_mm - 95, "diameter_mm": 35})
        return holes
