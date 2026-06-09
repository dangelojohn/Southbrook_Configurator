# SPDX-License-Identifier: LGPL-3.0-only
"""sb.production.package extension — KD flat-pack export.

KD = Knock-Down = shipped disassembled with pre-drilled hardware holes,
assembled on site. The Central Kitchens channel consumes the export
JSON; for Module 9 scope we ship the envelope structure + the action
that emits it. The consumer-side cabling lands when a real Central
Kitchens dealer is signed."""
import io
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
                    dict(p._fields["x_hardware_category"].selection).get(
                        p.x_hardware_category, p.x_hardware_category or "-"),
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
