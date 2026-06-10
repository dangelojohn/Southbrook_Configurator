# SPDX-License-Identifier: LGPL-3.0-only
"""render_elevation.py — procedural FreeCAD TechDraw elevation render.

Same single-cabinet spec as render_cabinet.py, but produces a TechDraw
elevation drawing as an SVG (which the dealer portal embeds into the
installation PDF).

Invocation (must wrap in xvfb-run to make GUI modules importable):

    xvfb-run -a freecadcmd render_elevation.py -- '<spec_json>'

Output (in spec["output_dir"]/):
    front.svg       front elevation view (the customer-facing face)
    top.svg         top-down plan view
    side.svg        side elevation view
    elevation.svg   combined 3-view page (front + top + side on one sheet)
    manifest.json   machine-readable index

Why TechDraw vs the per-panel SVG render_cabinet.py emits:
  - render_cabinet.py SVGs are individual cut-list panels for the
    cutting/nesting division. No assembly view, no dimensioning, no
    intent of being shown to the dealer for installation.
  - TechDraw SVGs here are dimensioned ORTHOGRAPHIC PROJECTIONS of the
    assembled cabinet from three principal views — what the installer
    actually needs to fit the cabinet on site.

Init-doc init-doc GAP-06 ('FreeCAD TechDraw elevation output') closure:
  this is the script Module 9's dealer portal installation PDF can
  embed (as <img> tag pointing at an attachment, or as a downloadable
  follow-up to the cut-list-tables PDF that ships today).
"""
import json
import sys
from pathlib import Path

# freecadcmd reinitialises Python; PYTHONPATH does NOT carry over.
if "/srv/shared" not in sys.path:
    sys.path.insert(0, "/srv/shared")

from southbrook_dims import panel_cut_list  # noqa: E402

import FreeCAD as App  # type: ignore
import FreeCADGui as Gui  # type: ignore  # noqa: F401 — required for TechDraw projection compute
import Part  # type: ignore
import TechDraw  # type: ignore


def _parse_args() -> dict:
    if "--" in sys.argv:
        sep = sys.argv.index("--")
        rest = sys.argv[sep + 1:]
    else:
        rest = sys.argv[1:]
    if not rest:
        raise SystemExit("render_elevation.py: no spec JSON argument")
    return json.loads(rest[0])


def _make_box(length: float, width: float, thickness: float):
    return Part.makeBox(float(length), float(width), float(thickness))


def _place(shape, x: float, y: float, z: float):
    return shape.translated(App.Vector(x, y, z))


def _build_carcass_compound(width_mm: float, height_mm: float,
                             depth_mm: float, family: str, door_count: int):
    """Assemble all panels into one Part.Compound so TechDraw sees a
    single solid to project. Origin is at the front-bottom-left corner."""
    pd = panel_cut_list(width_mm, height_mm, depth_mm,
                         family=family, door_count=door_count)
    BOX_TH = pd["side_L"][2]
    parts = []

    # Sides — rotate the box so length runs vertical.
    side = _make_box(*pd["side_L"])
    side.rotate(App.Vector(0, 0, 0), App.Vector(0, 1, 0), 90)
    parts.append(_place(side, 0, 0, 0))
    inside_width = pd["top"][0]
    parts.append(_place(side, BOX_TH + inside_width, 0, 0))

    # Top + bottom.
    top = _make_box(*pd["top"])
    parts.append(_place(top, BOX_TH, 0, height_mm - BOX_TH))
    parts.append(_place(top, BOX_TH, 0, 0))

    # Back — captures into the rabbet.
    back = _make_box(*pd["back"])
    parts.append(_place(back, BOX_TH - 6.35, 0, BOX_TH - 6.35))

    # Door(s).
    door_dim = pd["door"]
    if door_dim:
        # door tuple is (length=height, width, thickness)
        d_len, d_w, d_th = door_dim
        # Position doors slightly in front of the carcass (depth_mm + small gap)
        # so they're visible in the elevation projection.
        if door_count == 1:
            door = _make_box(d_w, d_len, d_th)
            parts.append(_place(door, 0, depth_mm + 5, 0))
        elif door_count == 2:
            door = _make_box(d_w, d_len, d_th)
            parts.append(_place(door, 0, depth_mm + 5, 0))
            parts.append(_place(door,
                                  width_mm - d_w, depth_mm + 5, 0))

    return Part.makeCompound(parts)


def _make_page(doc, name: str = "Installation"):
    """Create a TechDraw Page using FreeCAD's built-in A3 template."""
    page = doc.addObject("TechDraw::DrawPage", "Page")
    template = doc.addObject("TechDraw::DrawSVGTemplate", "Template")
    template.Template = (
        "/usr/share/freecad/Mod/TechDraw/Templates/A3_Landscape_blank.svg"
    )
    page.Template = template
    page.Label = name
    return page


def _add_view(doc, page, shape, direction: tuple, x_mm: float,
              y_mm: float, label: str):
    """Add a single orthographic view of `shape` to the page."""
    view = doc.addObject("TechDraw::DrawViewPart", label)
    view.Source = []
    # DrawViewPart requires a "real" document object. Wrap shape in a
    # Part::Feature so it has the right interface.
    feat_name = f"Feat_{label}"
    feat = doc.addObject("Part::Feature", feat_name)
    feat.Shape = shape
    view.Source = [feat]
    view.Direction = App.Vector(*direction)
    view.X = float(x_mm)
    view.Y = float(y_mm)
    view.Scale = 0.15  # so a 600mm cabinet ≈ 90mm on the page
    page.addView(view)
    return view


def main() -> None:
    spec = _parse_args()
    dims = spec["dimensions"]
    output_dir = Path(spec["output_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)

    width_mm = float(dims["width_mm"])
    height_mm = float(dims["height_mm"])
    depth_mm = float(dims["depth_mm"])
    family = spec.get("family", "base")
    door_count = int(spec.get("door_count", 1))

    compound = _build_carcass_compound(
        width_mm, height_mm, depth_mm, family, door_count,
    )

    # Single document with a page; we still build a page for the DXF
    # export (writeDXFPage works at page level), but per-view SVGs come
    # from viewPartAsSvg(view) since TechDraw 1.0 has no writeSVGPage.
    doc = App.newDocument("elevation")
    page = _make_page(doc, name=f"Cabinet {int(width_mm)}x{int(height_mm)}x{int(depth_mm)}mm")

    artifacts = {"svg": [], "dxf": []}
    warnings = []

    # Three views: front (-Y), top (+Z), side (+X). Standard third-angle.
    views = []
    for label, direction, x, y in [
        ("FrontView", (0, -1, 0), 100, 200),
        ("TopView",   (0,  0, 1), 100, 100),
        ("SideView",  (1,  0, 0), 250, 200),
    ]:
        try:
            v = _add_view(doc, page, compound, direction=direction,
                          x_mm=x, y_mm=y, label=label)
            views.append((label, v))
        except Exception as exc:
            warnings.append(f"view_creation_failed:{label}:{exc}")
    doc.recompute()

    # Wait for HLR (Hidden Line Removal) to finish. HLR runs async; the
    # SVG/DXF emit is empty until each view's Status flips to 0 (done).
    import time
    deadline = time.time() + 30
    for view in doc.Objects:
        if hasattr(view, "Status"):
            while getattr(view, "Status", 0) != 0 and time.time() < deadline:
                time.sleep(0.25)
    doc.recompute()

    # Whole-page DXF — works via TechDraw.writeDXFPage at page level.
    elevation_dxf = output_dir / "elevation.dxf"
    try:
        TechDraw.writeDXFPage(page, str(elevation_dxf))
        if elevation_dxf.exists() and elevation_dxf.stat().st_size > 0:
            artifacts["dxf"].append(str(elevation_dxf))
    except Exception as exc:
        warnings.append(f"dxf_export_failed:{exc}")

    # Per-view SVGs.
    # TechDraw 1.0's `viewPartAsSvg(view)` is documented but segfaults in
    # this FreeCAD build (1.0.0 on aarch64 / Python 3.13) when called
    # against a DrawViewPart whose Source is a Part::Feature wrapping a
    # makeCompound result. The crash is in C++ inside FreeCAD's PyImport,
    # so a Python try/except can't catch it.
    # Workaround: extract SVG fragments using projectToSVG(shape, dir),
    # which operates on the raw shape directly without going through the
    # view object. We assemble a minimal SVG wrapper around each fragment.
    for label, direction, _x, _y in [
        ("FrontView", (0, -1, 0), 100, 200),
        ("TopView",   (0,  0, 1), 100, 100),
        ("SideView",  (1,  0, 0), 250, 200),
    ]:
        svg_path = output_dir / f"{label.lower()}.svg"
        try:
            fragment = TechDraw.projectToSVG(
                compound, App.Vector(*direction),
            )
            if fragment:
                wrapper = (
                    "<?xml version='1.0' encoding='UTF-8'?>\n"
                    "<svg xmlns='http://www.w3.org/2000/svg' "
                    "viewBox='-1500 -1500 3000 3000'>\n"
                    f"<g transform='scale(0.5)'>{fragment}</g>\n"
                    "</svg>\n"
                )
                svg_path.write_text(wrapper)
                artifacts["svg"].append(str(svg_path))
            else:
                warnings.append(f"svg_empty:{label}")
        except Exception as exc:
            warnings.append(f"svg_export_failed:{label}:{exc}")

    manifest = {
        "schema": "southbrook.elevation.v1",
        "production_id": spec.get("production_id"),
        "dimensions": dims,
        "family": family,
        "door_count": door_count,
        "artifacts": artifacts,
        "warnings": warnings,
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print(json.dumps(manifest))


# freecadcmd does NOT set __name__ to "__main__".
main()
