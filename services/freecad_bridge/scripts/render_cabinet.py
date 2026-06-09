# SPDX-License-Identifier: LGPL-3.0-only
"""render_cabinet.py — procedural FreeCAD render for one cabinet.

Invoked by the bridge worker as:

    freecadcmd render_cabinet.py -- '<spec_json>'

The spec_json is the same dict the bridge's /render endpoint accepts:

    {
      "production_id": <int>,
      "dimensions":    {"width_mm": <f>, "height_mm": <f>, "depth_mm": <f>},
      "family":        "base" | "wall" | "tall" | "sink" | "vanity",
      "door_count":    <int>,
      "output_dir":    "<absolute path>"
    }

Panel geometry comes from shared.southbrook_dims (mounted at /srv/shared,
on PYTHONPATH per docker-compose). Same source the G1 gate asserts —
rendered geometry is therefore guaranteed identical to BoM-computed
geometry as long as G1 stays green.

Outputs to <output_dir>/:
    side_L.dxf  side_R.dxf  top.dxf  bottom.dxf  back.dxf
    adjustable_shelf.dxf  door.dxf      (whichever are produced)
    assembly.step                       (full carcass STEP AP214)
    manifest.json                       (machine-readable index)

The script writes manifest.json AND prints it to stdout so the caller
can read it either way.

DXF is R12 per init-doc Module 2 contract.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# freecadcmd reinitialises its own Python environment and does NOT
# inherit the host process's PYTHONPATH. Add /srv/shared explicitly
# so we can import the canonical shared.southbrook_dims that the G1
# gate asserts against.
if "/srv/shared" not in sys.path:
    sys.path.insert(0, "/srv/shared")

from southbrook_dims import panel_cut_list  # noqa: E402

import FreeCAD as App  # type: ignore
import Part            # type: ignore
import Import          # type: ignore


def _parse_args() -> dict:
    """Read the JSON spec after the `--` separator that freecadcmd uses."""
    if "--" in sys.argv:
        sep = sys.argv.index("--")
        rest = sys.argv[sep + 1:]
    else:
        rest = sys.argv[1:]
    if not rest:
        raise SystemExit("render_cabinet.py: no spec JSON argument")
    return json.loads(rest[0])


def _make_panel_box(length_mm: float, width_mm: float, thickness_mm: float) -> Part.Shape:
    """Build a rectangular panel. Length runs along X, width along Y,
    thickness along Z (so X×Y is the face that gets edge-banded)."""
    return Part.makeBox(float(length_mm), float(width_mm), float(thickness_mm))


def _place(panel: Part.Shape, x: float, y: float, z: float) -> Part.Shape:
    """Translate the panel to (x, y, z) without rotating it. The carcass
    builder positions each panel in cabinet-internal coordinates."""
    return panel.translated(App.Vector(x, y, z))


def _build_carcass(panel_dict: dict, family: str) -> dict:
    """Return {panel_name: Part.Shape} for every panel actually present
    in the carcass. Coordinates are in mm; origin at the front-bottom-
    left corner of the cabinet looking at the front face."""
    out: dict = {}

    # Side panels — full height + depth, thickness along the left/right
    # exterior. side_L sits at x=0; side_R sits at x=(W - BOX_TH).
    side_dim = panel_dict.get("side_L")
    if side_dim:
        side = _make_panel_box(side_dim[0], side_dim[1], side_dim[2])
        # Rotate so length runs vertical: swap X/Z.
        side = side.copy()
        side.rotate(App.Vector(0, 0, 0), App.Vector(0, 1, 0), 90)
        # side_L at x=0, side_R at x = W - thickness
        # We don't strictly know W here; recompute from the dim tuple:
        # the side's length_mm is height_mm, and the wall_thickness is the
        # side's thickness_mm (= BOX_TH).
        out["side_L"] = _place(side, 0, 0, 0)
        # The right side mirrors at x_right; we compute x_right from the
        # known inside_width + 2*BOX_TH. We get inside_width from the
        # top panel below.
        out["_side_R_template"] = side  # placed later when we know W

    top_dim = panel_dict.get("top")
    if top_dim:
        # length = inside_width; width = depth; thickness = BOX_TH
        top = _make_panel_box(top_dim[0], top_dim[1], top_dim[2])
        # Position: above the cabinet sides, between them.
        # x = BOX_TH (right after the left side)
        # y = 0  (flush with the front)
        # z = (height_mm - BOX_TH) — top of cabinet
        out["top"] = top  # placement deferred to assembly stage
        out["_top_dim"] = top_dim

    bottom_dim = panel_dict.get("bottom")
    if bottom_dim:
        bottom = _make_panel_box(bottom_dim[0], bottom_dim[1], bottom_dim[2])
        out["bottom"] = bottom
        out["_bottom_dim"] = bottom_dim

    back_dim = panel_dict.get("back")
    if back_dim:
        back = _make_panel_box(back_dim[0], back_dim[1], back_dim[2])
        out["back"] = back

    shelf_dim = panel_dict.get("adjustable_shelf")
    shelf_count = int(panel_dict.get("shelf_count") or 0)
    if shelf_dim and shelf_count > 0:
        shelf = _make_panel_box(shelf_dim[0], shelf_dim[1], shelf_dim[2])
        out["adjustable_shelf"] = shelf

    door_dim = panel_dict.get("door")
    if door_dim:
        door = _make_panel_box(door_dim[0], door_dim[1], door_dim[2])
        out["door"] = door

    # Now position side_R using the known top length.
    if out.get("_side_R_template") is not None:
        top_dim = out.get("_top_dim")
        if top_dim:
            inside_width = top_dim[0]
            BOX_TH = (panel_dict.get("side_L") or [0, 0, 0])[2]
            x_right = BOX_TH + inside_width
            out["side_R"] = _place(out.pop("_side_R_template"), x_right, 0, 0)
            out.pop("_top_dim", None)
        else:
            out.pop("_side_R_template", None)

    return out


def _export_dxf(panel_name: str, length_mm: float, width_mm: float, path: Path) -> None:
    """Export a single panel as DXF R12 using ezdxf.

    The cutting/nesting division wants a flat 2D outline of the panel
    face (length × width) — that's what they nest into stock sheets.
    The thickness dimension is irrelevant for nesting; it appears in
    the shop-floor drawing.

    Using ezdxf — pure Python, no GUI dep — instead of FreeCAD's Draft
    workbench (which needs the Gui module that freecadcmd does not
    load). We emit a single LWPOLYLINE rectangle on layer
    PANEL_OUTLINE, plus the panel name as a TEXT annotation in the
    lower-left corner."""
    try:
        import ezdxf  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "ezdxf is not installed in the bridge container; "
            "add to requirements.txt and rebuild."
        ) from exc

    # DXF R12 per init-doc Module 2 — predates LWPOLYLINE (R2000),
    # so we emit 4 LINE entities for the panel rectangle.
    doc = ezdxf.new("R12", setup=True)
    doc.layers.add(name="PANEL_OUTLINE", color=1)  # red
    doc.layers.add(name="PANEL_LABEL", color=7)    # white/black on white

    msp = doc.modelspace()
    corners = [
        ((0, 0), (length_mm, 0)),
        ((length_mm, 0), (length_mm, width_mm)),
        ((length_mm, width_mm), (0, width_mm)),
        ((0, width_mm), (0, 0)),
    ]
    for start, end in corners:
        msp.add_line(start, end, dxfattribs={"layer": "PANEL_OUTLINE"})
    msp.add_text(
        f"{panel_name} {length_mm:.1f} x {width_mm:.1f} mm",
        dxfattribs={"layer": "PANEL_LABEL", "height": max(20.0, width_mm / 20)},
    ).set_placement((5, -25))
    doc.saveas(str(path))


def _export_svg(panel_name: str, length_mm: float, width_mm: float,
                thickness_mm: float, path: Path) -> None:
    """Export a single panel as an SVG shop drawing.

    Stock SVG strings — no dependency needed. Per-panel SVG includes:
      - the rectangular outline scaled to mm with a margin
      - dimension callouts on length + width
      - panel-name + thickness label
    """
    margin = 30
    # Scale so the longer dimension is 800 px (keeps the SVG readable).
    scale = 800.0 / max(length_mm, width_mm)
    width_px = length_mm * scale + margin * 2
    height_px = width_mm * scale + margin * 2

    rect_x = margin
    rect_y = margin
    rect_w = length_mm * scale
    rect_h = width_mm * scale
    label_y = rect_y + rect_h + 18
    title_y = 18

    svg = f"""<?xml version="1.0" encoding="utf-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="{width_px:.0f}" height="{height_px:.0f}"
     viewBox="0 0 {width_px:.0f} {height_px:.0f}">
  <style>
    .panel {{ fill: #f5f1e8; stroke: #333; stroke-width: 1.5; }}
    .label {{ font: 12px sans-serif; fill: #333; }}
    .title {{ font: 14px sans-serif; font-weight: 600; fill: #1c2d49; }}
    .dim   {{ font: 10px sans-serif; fill: #666; }}
  </style>
  <text class="title" x="{margin}" y="{title_y}">{panel_name} — {thickness_mm:.2f} mm thick</text>
  <rect class="panel" x="{rect_x}" y="{rect_y}" width="{rect_w:.1f}" height="{rect_h:.1f}"/>
  <text class="dim" x="{rect_x + rect_w/2:.1f}" y="{label_y}" text-anchor="middle">
    length: {length_mm:.1f} mm
  </text>
  <text class="dim" x="{rect_x - 6:.1f}" y="{rect_y + rect_h/2:.1f}"
        text-anchor="end" dominant-baseline="middle">
    width: {width_mm:.1f} mm
  </text>
</svg>
"""
    path.write_text(svg)


def _export_step(shapes: list, path: Path) -> None:
    """Export the carcass as STEP AP214 (the standard CAD assembly format)."""
    doc = App.newDocument("step_export")
    objects = []
    for name, shape in shapes:
        obj = doc.addObject("Part::Feature", name)
        obj.Shape = shape
        objects.append(obj)
    doc.recompute()
    Import.export(objects, str(path))
    App.closeDocument(doc.Name)


def main() -> None:
    spec = _parse_args()
    dims = spec["dimensions"]
    output_dir = Path(spec["output_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)

    panel_dict = panel_cut_list(
        width_mm=float(dims["width_mm"]),
        height_mm=float(dims["height_mm"]),
        depth_mm=float(dims["depth_mm"]),
        family=spec.get("family", "base"),
        door_count=int(spec.get("door_count", 1)),
    )

    carcass = _build_carcass(panel_dict, spec.get("family", "base"))

    artifacts = {"dxf": [], "svg": [], "step": []}
    warnings = []

    # Per-panel DXF + SVG. We pull the panel's length × width directly
    # from panel_dict (the same source the BoM math + G1 use) rather
    # than reverse-engineering it from the Part.Shape bounding box.
    PANEL_KEYS = ("side_L", "side_R", "top", "bottom", "back",
                  "adjustable_shelf", "door")
    for name in PANEL_KEYS:
        if carcass.get(name) is None or name.startswith("_"):
            continue
        dim = panel_dict.get(name)
        if dim is None or not isinstance(dim, tuple) or len(dim) != 3:
            continue
        length_mm, width_mm, thickness_mm = dim

        dxf_path = output_dir / f"{name}.dxf"
        try:
            _export_dxf(name, length_mm, width_mm, dxf_path)
            artifacts["dxf"].append(str(dxf_path))
        except Exception as exc:
            sys.stderr.write(f"DXF export raised for {name}: {exc}\n")
            warnings.append(f"dxf_failed:{name}:{exc}")

        svg_path = output_dir / f"{name}.svg"
        try:
            _export_svg(name, length_mm, width_mm, thickness_mm, svg_path)
            artifacts["svg"].append(str(svg_path))
        except Exception as exc:
            sys.stderr.write(f"SVG export raised for {name}: {exc}\n")
            warnings.append(f"svg_failed:{name}:{exc}")

    # Whole-carcass STEP.
    step_shapes = [(k, v) for k, v in carcass.items()
                   if not k.startswith("_") and v is not None]
    if step_shapes:
        step_path = output_dir / "assembly.step"
        try:
            _export_step(step_shapes, step_path)
            artifacts["step"].append(str(step_path))
        except Exception as exc:
            sys.stderr.write(f"STEP export failed: {exc}\n")

    manifest = {
        "schema": "southbrook.render.v1",
        "production_id": spec.get("production_id"),
        "dimensions": dims,
        "family": spec.get("family"),
        "door_count": spec.get("door_count"),
        "panel_count": len(step_shapes),
        "artifacts": artifacts,
        "warnings": warnings,
    }
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2))
    # Also print to stdout so subprocess callers can capture it.
    print(json.dumps(manifest))


# freecadcmd does NOT set __name__ to "__main__", so we call main()
# unconditionally. The script is single-purpose: every invocation
# renders one cabinet.
main()
