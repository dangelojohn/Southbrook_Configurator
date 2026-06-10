# SPDX-License-Identifier: LGPL-3.0-only
"""sb.production.package extension — KD flat-pack export.

KD = Knock-Down = shipped disassembled with pre-drilled hardware holes,
assembled on site. The Central Kitchens channel consumes the export
JSON; for Module 9 scope we ship the envelope structure + the action
that emits it. The consumer-side cabling lands when a real Central
Kitchens dealer is signed."""
import base64
import io
import json
import logging
import os
from typing import Dict, List, Optional, Tuple

import requests

from odoo import _, fields, models
from odoo.exceptions import UserError


KD_ENVELOPE_SCHEMA = "southbrook.kd_flatpack.v1"
ELEVATION_SCHEMA = "southbrook.elevation.v1"

_logger = logging.getLogger(__name__)


class SbProductionPackage(models.Model):
    _inherit = "sb.production.package"

    is_kd_variant = fields.Boolean(
        string="KD Flat-Pack Variant",
        help="When True this package ships as knock-down (assembled "
             "on site). KD export includes pre-drilled hole positions.",
    )

    # ------------------------------------------------------------------
    # Helpers — cabinet box dimensions from cutlist
    # ------------------------------------------------------------------
    def _derive_box_dimensions(self) -> Optional[Tuple[float, float, float]]:
        """Recover (width, height, depth) in mm from the cutlist panels.

        Used by the installation-PDF elevation render to know the carcass
        size to pass to the bridge. The cutlist is authoritative because
        it carries the as-cut panel dimensions; rebuilding height/width/
        depth is straight inverse of southbrook_dims.panel_cut_list:

          side_L: (height, depth, thickness)
          top:    (width - 2*thickness, depth - rabbet, thickness)
          back:   (width - 2*thickness + offsets, height - 2*thickness, thk)

        Returns None when the cutlist is missing or the required panels
        aren't present (e.g. a hardware-only package).
        """
        if not self.cutlist_id:
            return None
        by_name = {
            ln.panel_name: ln for ln in self.cutlist_id.line_ids
        }
        side = by_name.get("side_L") or by_name.get("side_R")
        top = by_name.get("top") or by_name.get("bottom")
        if not (side and top):
            return None
        thickness = side.thickness_mm or 18.0
        height = side.length_mm
        depth = side.width_mm
        width = top.length_mm + 2 * thickness
        return (width, height, depth)

    def _fetch_elevation_svgs(
        self, dimensions: Tuple[float, float, float],
    ) -> Optional[Dict[str, bytes]]:
        """Call the freecad-bridge /render_elevation endpoint.

        Returns a dict {label: svg_bytes} on success, or None when the
        bridge is unreachable or returns an error (the installation PDF
        gracefully degrades to text-only if the elevation isn't available).
        Env vars FREECAD_BRIDGE_URL + FREECAD_BRIDGE_SECRET come from
        services/odoo container env (docker-compose.yml).
        """
        bridge_url = os.environ.get(
            "FREECAD_BRIDGE_URL", "http://freecad-bridge:8000",
        )
        bridge_secret = os.environ.get("FREECAD_BRIDGE_SECRET")
        if not bridge_secret:
            _logger.info("elevation: bridge secret unset, skipping")
            return None
        width, height, depth = dimensions
        door_count = 2 if width >= 600 else 1
        family = "wall" if "wall" in (self.name or "").lower() else "base"
        payload = {
            "production_id": self.id,
            "dimensions": {
                "width_mm": width, "height_mm": height, "depth_mm": depth,
            },
            "family": family,
            "door_count": door_count,
        }
        try:
            resp = requests.post(
                f"{bridge_url}/render_elevation",
                json=payload,
                headers={"X-Bridge-Secret": bridge_secret},
                timeout=45,
            )
        except requests.RequestException as exc:
            _logger.warning("elevation: bridge unreachable: %s", exc)
            return None
        if resp.status_code != 200:
            _logger.warning("elevation: bridge returned %s: %s",
                            resp.status_code, resp.text[:200])
            return None
        body = resp.json()
        svgs_b64 = body.get("svgs_b64") or {}
        return {
            label: base64.b64decode(b64)
            for label, b64 in svgs_b64.items()
        }

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

    # ------------------------------------------------------------------
    # Installation-drawing PDF (GAP-06 — Module 9 init-doc DoD)
    # ------------------------------------------------------------------
    def export_installation_pdf(self) -> bytes:
        """Multi-page installation reference PDF for a dealer.

        Page 1 — Cover: package + MO + cutlist/hardware summary.
        Page 2 — Panel cut list table.
        Page 3 — Hardware schedule.
        Page 4+ — KD pre-drilled holes (only when is_kd_variant=True).

        Init-doc Module 9 calls for 'FreeCAD TechDraw elevation output'
        (GAP-06). TechDraw needs the GUI module that freecadcmd does
        NOT load (see services/freecad_bridge/Dockerfile comments).
        Module-9 ships a reportlab-driven installation reference here —
        enough paper for the dealer to install on-site; the TechDraw
        elevation render lands when a GUI-FreeCAD path is wired.
        """
        self.ensure_one()

        def _selection_label(recordset, fname, value):
            """Return the human label for a selection-field value.

            Handles both static-list and callable selections — Odoo
            related-Selection fields, since the 2026-06-10 hardware-
            catalog refactor, expose .selection as a function rather
            than the static list. dict(...).get(value) would crash
            with 'function object is not iterable'.

            Falls back to the raw value when label can't be resolved
            (covers extension-flagged values that aren't in the active
            selection list anymore).
            """
            if not value:
                return "-"
            field = recordset._fields[fname]
            try:
                opts = field._description_selection(recordset.env)
            except Exception:  # noqa: BLE001
                opts = field.selection
            try:
                return dict(opts).get(value, value)
            except TypeError:
                # opts is still a callable for some reason — last
                # resort, return the raw value.
                return value

        try:
            from reportlab.lib.pagesizes import letter
            from reportlab.lib.styles import getSampleStyleSheet
            from reportlab.lib.units import mm
            from reportlab.lib import colors
            from reportlab.platypus import (
                SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
                PageBreak,
            )
        except ImportError as exc:
            raise UserError(_(
                "ReportLab is not installed in this Odoo container; "
                "the installation-PDF endpoint requires it."
            )) from exc

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer, pagesize=letter,
            leftMargin=15 * mm, rightMargin=15 * mm,
            topMargin=15 * mm, bottomMargin=15 * mm,
            title=f"Installation Reference {self.name}",
        )
        styles = getSampleStyleSheet()
        story = []

        # ---- Cover ----
        story.append(Paragraph("<b>Installation Reference</b>", styles["Title"]))
        story.append(Paragraph(f"Package: {self.name}", styles["Heading2"]))
        if self.mo_id:
            story.append(Paragraph(
                f"Manufacturing Order: {self.mo_id.name}", styles["Normal"]))
        if self.cutlist_id:
            story.append(Paragraph(
                f"Cut list: {self.cutlist_id.name} "
                f"({len(self.cutlist_id.line_ids)} panel rows)",
                styles["Normal"]))
        if self.hardware_package_id:
            story.append(Paragraph(
                f"Hardware package: {self.hardware_package_id.name} "
                f"({len(self.hardware_package_id.line_ids)} SKU rows; "
                f"pricing_pending={self.hardware_package_id.has_pricing_pending})",
                styles["Normal"]))
        if self.is_kd_variant:
            story.append(Paragraph(
                "<b>Variant: KD flat-pack</b> — shipped knocked-down with "
                "pre-drilled hardware holes; assembled on site.",
                styles["Normal"]))
        story.append(Spacer(1, 6 * mm))
        story.append(Paragraph(
            "Cut-list dimensions are authoritative; consult the spec "
            "sheet alongside this reference for cosmetic specs.",
            styles["Italic"]))

        # ---- TechDraw elevation views (page 2 — front/top/side) ----
        # Calls the freecad-bridge /render_elevation endpoint which runs
        # FreeCAD + TechDraw under xvfb and returns three orthographic
        # projections as inline base64-encoded SVGs. The PDF gracefully
        # degrades to text-only if the bridge is unreachable.
        box_dims = self._derive_box_dimensions()
        if box_dims:
            elevation_svgs = self._fetch_elevation_svgs(box_dims)
            if elevation_svgs:
                try:
                    from svglib.svglib import svg2rlg
                    from reportlab.graphics import renderPDF
                    from reportlab.platypus.flowables import Flowable

                    class _SvgFlowable(Flowable):
                        """Wrap a svglib Drawing as a platypus Flowable."""
                        def __init__(self, drawing, max_w_mm, max_h_mm):
                            super().__init__()
                            self.drawing = drawing
                            scale = min(
                                (max_w_mm * mm) / drawing.width,
                                (max_h_mm * mm) / drawing.height,
                            )
                            drawing.width *= scale
                            drawing.height *= scale
                            drawing.scale(scale, scale)
                            self.width = drawing.width
                            self.height = drawing.height
                        def draw(self):
                            renderPDF.draw(self.drawing, self.canv, 0, 0)

                    story.append(PageBreak())
                    story.append(Paragraph(
                        "Elevation Views", styles["Heading1"]))
                    story.append(Paragraph(
                        f"Carcass {int(box_dims[0])} × {int(box_dims[1])} × "
                        f"{int(box_dims[2])} mm — third-angle projection.",
                        styles["Italic"]))
                    story.append(Spacer(1, 4 * mm))
                    for label in ("frontview", "topview", "sideview"):
                        svg_bytes = elevation_svgs.get(label)
                        if not svg_bytes:
                            continue
                        try:
                            drawing = svg2rlg(io.BytesIO(svg_bytes))
                            if drawing is None:
                                continue
                            story.append(Paragraph(
                                label.replace("view", "").title(),
                                styles["Heading3"]))
                            story.append(_SvgFlowable(drawing, 160, 80))
                            story.append(Spacer(1, 4 * mm))
                        except Exception as exc:  # noqa: BLE001
                            _logger.warning(
                                "elevation %s SVG embed failed: %s",
                                label, exc)
                except ImportError as exc:
                    _logger.warning(
                        "elevation: svglib import failed (%s); skipping",
                        exc)

        # ---- Cut list table ----
        story.append(PageBreak())
        story.append(Paragraph("Panel Cut List", styles["Heading1"]))
        cut_rows = [["Panel", "Qty", "Length mm", "Width mm",
                     "Thickness mm", "Substrate", "Grain"]]
        for ln in (self.cutlist_id.line_ids if self.cutlist_id else []):
            cut_rows.append([
                dict(ln._fields["panel_name"].selection).get(
                    ln.panel_name, ln.panel_name),
                str(ln.qty),
                f"{ln.length_mm:.1f}",
                f"{ln.width_mm:.1f}",
                f"{ln.thickness_mm:.2f}",
                dict(ln._fields["substrate"].selection).get(
                    ln.substrate, ln.substrate or "-"),
                dict(ln._fields["grain_dir"].selection).get(
                    ln.grain_dir, ln.grain_dir or "-"),
            ])
        cut_table = Table(cut_rows, repeatRows=1)
        cut_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1c2d49")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("ALIGN", (1, 1), (4, -1), "RIGHT"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1),
             [colors.white, colors.HexColor("#f5f1e8")]),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
        ]))
        story.append(cut_table)

        # ---- Hardware schedule ----
        story.append(PageBreak())
        story.append(Paragraph("Hardware Schedule", styles["Heading1"]))
        hw_rows = [["SKU", "Category", "Brand", "Qty", "Pricing"]]
        if self.hardware_package_id:
            for ln in self.hardware_package_id.line_ids:
                p = ln.product_id
                hw_rows.append([
                    p.x_marathon_sku or p.default_code or p.name,
                    _selection_label(p, "x_hardware_category",
                                     p.x_hardware_category),
                    p.x_hardware_brand_id.name or "-",
                    str(ln.qty),
                    "PENDING" if ln.pricing_pending else "OK",
                ])
        hw_table = Table(hw_rows, repeatRows=1)
        hw_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1c2d49")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("ALIGN", (3, 1), (3, -1), "RIGHT"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1),
             [colors.white, colors.HexColor("#f5f1e8")]),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
        ]))
        story.append(hw_table)

        # ---- KD pre-drilled holes (only for KD variants) ----
        if self.is_kd_variant and self.cutlist_id:
            story.append(PageBreak())
            story.append(Paragraph("KD Pre-Drilled Holes", styles["Heading1"]))
            for ln in self.cutlist_id.line_ids:
                holes = self._derive_predrilled_holes(ln)
                if not holes:
                    continue
                story.append(Paragraph(
                    dict(ln._fields["panel_name"].selection).get(
                        ln.panel_name, ln.panel_name),
                    styles["Heading3"],
                ))
                hole_rows = [["Kind", "X mm", "Y mm", "Diameter mm"]]
                for h in holes:
                    hole_rows.append([
                        h["kind"], f"{h['x_mm']:.1f}",
                        f"{h['y_mm']:.1f}", f"{h['diameter_mm']:.1f}",
                    ])
                tbl = Table(hole_rows, repeatRows=1)
                tbl.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1c2d49")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                ]))
                story.append(tbl)
                story.append(Spacer(1, 3 * mm))

        doc.build(story)
        return buffer.getvalue()

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
