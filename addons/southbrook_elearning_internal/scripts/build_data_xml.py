#!/usr/bin/env python3
"""Generate Odoo data XML records for the internal e-learning series.

Reads docs/elearning/*.md (with YAML frontmatter), converts each lesson's
markdown body to HTML, and emits one ``data/elearning_courses.xml`` plus
per-course ``data/elearning_slides_NN.xml`` files containing slide.channel
+ slide.slide records ready for Odoo's website_slides module to load on
addon install / upgrade.

Run from the addon root:
    python3 scripts/build_data_xml.py

Re-run any time the markdown sources change; the script is deterministic
and the output XML is sorted by chapter so a diff is meaningful.

Why this is a build-time script (not a runtime hook):
  * Data XML is the simplest Odoo path — no Python hook, no module
    upgrade gymnastics; ``odoo -u`` reloads the records.
  * Pre-generated HTML keeps install-time fast (no markdown library
    inside the Odoo image).
  * The XML diff in git tells you exactly what changed lesson-by-lesson.
"""

from __future__ import annotations

import html
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import markdown  # type: ignore[import]
import yaml  # type: ignore[import]

ADDON_ROOT = Path(__file__).resolve().parent.parent
ELEARNING_SOURCE = ADDON_ROOT.parent.parent / "docs" / "elearning"
DATA_DIR = ADDON_ROOT / "data"

# Course metadata — order matters; this is the order they appear on
# /odoo/e-learning. Each entry: (course_no, xml_id, name, description,
# tag_color_int).  Tag colors use Odoo's 1-11 palette.
COURSE_META: List[Tuple[int, str, str, str, int]] = [
    (
        1,
        "course_workcenter_operators",
        "Workcenter Operators",
        "Daily flow for the people who run the shop — edge banding, CNC, "
        "assembly, sanding, finishing. Anchored on real workcenters: "
        "SB-EDGE, SB-CNC-BORE, SB-ASSY, SAND, PAINT, CURE.",
        3,
    ),
    (
        2,
        "course_production_planning",
        "Production Planning",
        "For the human sequencing the day's work against workcenters, "
        "running the release gate, and reading the MI report. Native MRP "
        "is assumed knowledge; these lessons cover the Southbrook deltas.",
        4,
    ),
    (
        3,
        "course_floor_management",
        "Floor Management",
        "Manufacturing Intelligence dashboards, Fabio recommendation queue, "
        "and OEE per workcenter — what a production manager watches and "
        "approves.",
        5,
    ),
    (
        4,
        "course_plm_design",
        "PLM + Design",
        "Engineering Change Orders, cut spec authoring, FreeCAD render "
        "pipeline, and Gemini-backed AI design assist. For designers and "
        "ECO engineers.",
        6,
    ),
    (
        5,
        "course_estimating_configurator",
        "Estimating + Configurator",
        "Turning a customer's kitchen design into a configured quote — "
        "OCA configurator vocabulary, the Southbrook Order Builder, the "
        "Marathon hardware catalog, and the v2 UX deltas.",
        7,
    ),
    (
        6,
        "course_customer_touchpoints",
        "Customer Touchpoints",
        "Customer portal (/my/kitchen-projects), dealer portal with "
        "scoped pricing visibility, and the Fabio queue from the CS "
        "perspective.",
        8,
    ),
    (
        7,
        "course_sysadmin",
        "Sysadmin",
        "Maintaining the platform — the 6 nightly orchestration crons, "
        "the QNAP backup pipeline, and the external Hermes Console "
        "recommendation queue.",
        2,
    ),
]


def _slug_to_xml_id(filename: str) -> str:
    """Turn '01_edge_banding_operator.md' into 'slide_01_edge_banding_operator'."""
    base = os.path.splitext(filename)[0]
    base = re.sub(r"[^a-zA-Z0-9_]", "_", base)
    return f"slide_{base}"


def _parse_frontmatter(text: str) -> Tuple[Dict, str]:
    """Strip ``---\\n...\\n---`` YAML block at top; return (meta, rest)."""
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    raw = text[3:end].strip()
    body = text[end + 4 :].lstrip("\n")
    try:
        meta = yaml.safe_load(raw) or {}
    except yaml.YAMLError:
        meta = {}
    return meta, body


def _md_to_html(body: str) -> str:
    """Convert lesson markdown to HTML.

    Extensions enabled:
      * tables — needed for the role × module matrix in the README and
        the quiz answer formatting
      * fenced_code — many lessons have ``` blocks
      * sane_lists — keep numbered lists numbered
      * toc — generates id="..." anchors so the eLearning slide can
        in-page-link to "Common mistakes" etc.
    """
    return markdown.markdown(
        body,
        extensions=["tables", "fenced_code", "sane_lists", "toc"],
        output_format="html5",
    )


def _xml_escape_cdata(s: str) -> str:
    """Escape only what XML's CDATA cannot tolerate (the ``]]>`` sequence)."""
    return s.replace("]]>", "]]]]><![CDATA[>")


def _course_no_from_meta(meta: Dict) -> Optional[int]:
    """Extract integer course number from frontmatter's ``course`` field.

    Accepts both raw ints (``course: 1``) and labelled strings
    (``course: "1 — Workcenter Operators"``).
    """
    raw = meta.get("course")
    if isinstance(raw, int):
        return raw
    if isinstance(raw, str):
        m = re.match(r"\s*(\d+)", raw)
        if m:
            return int(m.group(1))
    return None


def _chapter_to_sequence(chapter: object) -> int:
    """Map chapter like ``1.2`` → sequence 20 (so 1.1=10, 1.2=20, …)."""
    if not chapter:
        return 100
    m = re.match(r"\d+\.(\d+)", str(chapter))
    if not m:
        return 100
    return int(m.group(1)) * 10


def _short_description(meta: Dict, body_md: str) -> str:
    """Generate the slide's one-line description from frontmatter audience.

    Falls back to the first non-blank line of the markdown body so
    something always renders on the course catalog tile.
    """
    audience = meta.get("audience")
    if audience:
        return audience.strip().rstrip(".") + "."
    for line in body_md.splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            return line[:200]
    return ""


def build() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    sources = sorted(
        p
        for p in ELEARNING_SOURCE.glob("*.md")
        if p.name not in ("README.md", "_template.md")
    )
    if not sources:
        print(f"no lesson files found under {ELEARNING_SOURCE}", file=sys.stderr)
        sys.exit(1)

    parsed: List[Tuple[Path, Dict, str]] = []
    for path in sources:
        meta, body = _parse_frontmatter(path.read_text(encoding="utf-8"))
        parsed.append((path, meta, body))

    # ----- write the channels file -----
    channels_path = DATA_DIR / "elearning_courses.xml"
    with channels_path.open("w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="utf-8"?>\n')
        f.write("<odoo>\n")
        f.write("    <data noupdate=\"0\">\n")
        # Tag group so all 7 courses cluster under one heading on the
        # /odoo/e-learning catalogue.
        f.write(
            '        <record id="tag_group_internal" model="slide.channel.tag.group">\n'
            "            <field name=\"name\">Southbrook Internal</field>\n"
            "            <field name=\"sequence\">10</field>\n"
            "        </record>\n"
        )
        f.write(
            '        <record id="tag_internal" model="slide.channel.tag">\n'
            "            <field name=\"name\">Internal Custom Modules</field>\n"
            '            <field name="group_id" ref="tag_group_internal"/>\n'
            "            <field name=\"color\">3</field>\n"
            "        </record>\n"
        )
        for course_no, xml_id, name, desc, color in COURSE_META:
            f.write(f'        <record id="{xml_id}" model="slide.channel">\n')
            f.write(
                f"            <field name=\"name\">Course {course_no} — {html.escape(name)}</field>\n"
            )
            f.write(
                f"            <field name=\"description\">{html.escape(desc)}</field>\n"
            )
            f.write("            <field name=\"channel_type\">training</field>\n")
            f.write("            <field name=\"visibility\">public</field>\n")
            f.write("            <field name=\"enroll\">public</field>\n")
            f.write(f"            <field name=\"sequence\">{course_no * 10}</field>\n")
            f.write(
                "            <field name=\"is_published\" eval=\"True\"/>\n"
            )
            f.write(
                '            <field name="tag_ids" eval="[(6, 0, [ref(\'tag_internal\')])]"/>\n'
            )
            f.write(f"            <field name=\"color\">{color}</field>\n")
            f.write("        </record>\n")
        f.write("    </data>\n")
        f.write("</odoo>\n")
    print(f"wrote {channels_path.relative_to(ADDON_ROOT)}")

    # ----- write per-course slide files -----
    # Bucket lessons by integer course number from frontmatter; emit them
    # in chapter order. Lessons whose frontmatter is missing or malformed
    # become an explicit warning rather than silent drop.
    by_course: Dict[int, List[Tuple[Path, Dict, str]]] = {}
    for path, meta, body in parsed:
        course_no = _course_no_from_meta(meta)
        if course_no is None:
            print(f"WARN: {path.name} has no course number in frontmatter; skipping", file=sys.stderr)
            continue
        by_course.setdefault(course_no, []).append((path, meta, body))

    for course_no, xml_id, _, _, _ in COURSE_META:
        entries = sorted(
            by_course.get(course_no, []),
            key=lambda t: _chapter_to_sequence(t[1].get("chapter")),
        )
        if not entries:
            print(f"WARN: course {course_no} has no lessons", file=sys.stderr)
            continue

        slides_path = DATA_DIR / f"elearning_slides_{course_no:02d}.xml"
        with slides_path.open("w", encoding="utf-8") as f:
            f.write('<?xml version="1.0" encoding="utf-8"?>\n')
            f.write("<odoo>\n")
            f.write("    <data noupdate=\"0\">\n")
            for path, meta, body_md in entries:
                slide_xml_id = _slug_to_xml_id(path.name)
                title = (meta.get("title") or path.stem).strip()
                seq = _chapter_to_sequence(meta.get("chapter"))
                desc = _short_description(meta, body_md)
                html_body = _md_to_html(body_md)
                f.write(f'        <record id="{slide_xml_id}" model="slide.slide">\n')
                f.write(
                    f"            <field name=\"name\">{html.escape(title)}</field>\n"
                )
                f.write(f'            <field name="channel_id" ref="{xml_id}"/>\n')
                f.write("            <field name=\"slide_category\">article</field>\n")
                f.write(f"            <field name=\"sequence\">{seq}</field>\n")
                f.write(
                    f"            <field name=\"description\">{html.escape(desc)}</field>\n"
                )
                f.write(
                    "            <field name=\"html_content\"><![CDATA["
                    + _xml_escape_cdata(html_body)
                    + "]]></field>\n"
                )
                f.write(
                    "            <field name=\"is_published\" eval=\"True\"/>\n"
                )
                f.write("        </record>\n")
            f.write("    </data>\n")
            f.write("</odoo>\n")
        print(
            f"wrote {slides_path.relative_to(ADDON_ROOT)} ({len(entries)} slides)"
        )


if __name__ == "__main__":
    build()
