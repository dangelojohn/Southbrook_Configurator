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
    (
        8,
        "course_estimating_deep",
        "Estimating Deep Dive",
        "Six deep-dive lessons on the Southbrook Estimating addon — "
        "architecture, Order Builder walkthrough, zone/channel pricing "
        "math, quote-to-MO handoff, QWeb reports, and the revision/"
        "versioning chain. Goes deeper than Course 5.",
        9,
    ),
    (
        9,
        "course_productgraph",
        "ProductGraph PLM",
        "Six deep-dive lessons on ProductGraph — the OpenBOM-mirror PLM "
        "platform sitting next to (NOT inside) Southbrook. Property "
        "templates, vendor stubs, the native BoM editor, the MCP "
        "sidecar, and the Southbrook bridge.",
        10,
    ),
    (
        10,
        "course_configurator_deep",
        "Configurator Deep Dive",
        "Seven deep-dive lessons on the 5-addon configurator stack. "
        "Architecture, new-product setup, session state machine, sale + "
        "MRP integration, the v2 UX overlay, and the common gotchas "
        "(exclusion explosions, rule ordering, performance).",
        11,
    ),
    (
        11,
        "course_new_product_workflow",
        "Creating a New Product End-to-End",
        "Eight cross-system lessons walking a new cabinet from "
        "conception through ProductGraph entry, cut spec, BoM, "
        "configurator setup, pricing, first MO, and release. The "
        "course that ties every module together.",
        1,
    ),
    (
        12,
        "course_kitchen_ops_deep",
        "Kitchen Ops Module",
        "Seven deep-dive lessons on the Kitchen Ops umbrella menu — "
        "the parent menu architecture, project lifecycle, jobs board, "
        "production release queue, floor load dashboards, MI engine "
        "observability, and the cut/hardware/production package trio.",
        4,
    ),
    (
        13,
        "course_fabio_module",
        "Fabio Module (Hermes)",
        "Seven deep-dive lessons on the Southbrook Fabio AI assistant "
        "surface — architecture, the recommendation queue, JWT auth + "
        "persona resolution, the tool registry, all 13 read+write "
        "tools, and the OWL chat panel + Vercel sidecar.",
        5,
    ),
    (
        14,
        "course_project_module",
        "Project Module (Customized)",
        "Seven deep-dive lessons on Southbrook's customizations of "
        "Odoo's Project module — kitchen vs general projects, the 13-"
        "gate readiness algorithm, 5 release sign-offs, task→MO "
        "linkage, custom views, and project-level reporting.",
        6,
    ),
    (
        15,
        "course_manufacturing_module",
        "Manufacturing Module (Customized)",
        "Seven deep-dive lessons on Southbrook's customizations of "
        "Odoo's Manufacturing module — architecture, MO + workorder + "
        "BoM extensions, the workcenter surface, custom Kanbans, and "
        "the MO↔cut-list↔hardware-package linkage.",
        7,
    ),
    (
        16,
        "course_whmis_base",
        "WHMIS Base Training (Cabinet Shop)",
        "Six base-training lessons on Workplace Hazardous Materials "
        "Information System (WHMIS 2015 / GHS) for Southbrook cabinet "
        "manufacturing — overview, pictograms, labels, Safety Data "
        "Sheets, cabinet-shop-specific hazards, and worker rights + "
        "emergency response. Required for every employee on hire + "
        "annual refresher.",
        9,
    ),
    (
        17,
        "course_jtbd_micros",
        "JTBD Micro Library — In-the-Moment Help",
        "Forty short, verb-phrase task tutorials — each one answers a "
        "specific 'how do I...?' question users hit during their day. "
        "Designed for the in-app Help systray, not for sit-down "
        "learning. Indexed by department: Sales (8), Design (5), "
        "Planning (4), Floor (6), Maintenance (4), Quality (4), "
        "Finance (4), Payroll (5).",
        2,
    ),
    (
        18,
        "course_quality_persona",
        "Quality Inspector — Persona Track",
        "Five lessons for the QC inspector / quality manager: menu "
        "orientation, NCR open + escalate, SPC sampling discipline, Cpk "
        "+ capability analysis, supplier scorecards. Anchored on "
        "southbrook_quality v19.0.1.0.0.",
        5,
    ),
    (
        19,
        "course_payroll_persona",
        "Payroll Administrator — Persona Track",
        "Five lessons for the payroll admin running the bi-weekly cycle "
        "on CRA 2026 brackets: menu orientation, pre-run checks, "
        "compute + approve, EFT + bank upload, mid-cycle adjustments. "
        "Anchored on southbrook_payroll_ca v19.0.1.0.0.",
        7,
    ),
    (
        20,
        "course_finance_persona",
        "Controller — Persona Track (Monthly Close)",
        "Five lessons for the controller doing the monthly close: "
        "menu orientation, WIP reconciliation deep-dive, CCA "
        "depreciation + asset register, HST input/output filing, "
        "period lock + audit pack. Anchored on southbrook_finance_pack "
        "v19.0.1.0.0.",
        8,
    ),
    (
        21,
        "course_exec_persona",
        "Executive / Owner — Persona Track",
        "Four lessons for the owner / Plant GM using the daily "
        "morning briefing dashboard: 5-minute scan, tile drill-through, "
        "OEE + bottleneck reading, approving + delegating via Hermes. "
        "Anchored on southbrook_exec_dashboard v19.0.1.0.0.",
        9,
    ),
    (
        22,
        "course_quality_module",
        "Quality Module — Deep Dive",
        "Seven lessons on southbrook_quality internals: architecture, "
        "NCR state machine, SPC sample + control limit math, Cpk "
        "compute, quality dimension master, supplier defect rollup + "
        "MI engine integration, customisation patterns.",
        5,
    ),
    (
        23,
        "course_payroll_module",
        "Payroll CA Module — Deep Dive",
        "Seven lessons on southbrook_payroll_ca internals: "
        "architecture, salary rule chain, CRA bracket math, EFT "
        "format support, T4 + ROE generation, integration with native "
        "hr.payslip, customisation for new pay scenarios.",
        7,
    ),
    (
        24,
        "course_finance_module",
        "Finance Pack Module — Deep Dive",
        "Seven lessons on southbrook_finance_pack internals: "
        "architecture, CCA depreciation engine, WIP report query + "
        "GL reconciliation, HST return + tax accounts, budget model, "
        "MI engine integration, extension points.",
        8,
    ),
    (
        25,
        "course_integrations_module",
        "Integrations Module — Deep Dive",
        "Seven lessons on southbrook_integrations internals: "
        "architecture, Homag iX simulator, 3PL ASN inbound/outbound, "
        "MCP tool registry (vs Hermes registry), label printer "
        "integration, building a new vendor adapter, monitoring.",
        2,
    ),
    (
        26,
        "course_mes_mps_module",
        "MES + MPS Module — Deep Dive",
        "Seven lessons on southbrook_mes_mps internals: architecture, "
        "MPS period + rolling 13-week generator, workcenter capacity "
        "calc, OEE snapshot, bottleneck report query, MI engine "
        "integration, MPS customisation.",
        4,
    ),
    (
        27,
        "course_cmms_module",
        "CMMS + WMS Module — Deep Dive",
        "Seven lessons on southbrook_cmms_wms internals: architecture, "
        "breakdown alert + maintenance.request bridge, MTBF/MTTR math, "
        "service contracts, oversize permit / landed cost templates, "
        "MI engine, adding new equipment types.",
        6,
    ),
    (
        28,
        "course_exec_dashboard_module",
        "Exec Dashboard Module — Deep Dive",
        "Seven lessons on southbrook_exec_dashboard internals: "
        "architecture + tile registry, tile compute + cron, OWL view + "
        "mobile-first layout, drill-through wiring, adding a custom "
        "tile, Hermes integration, performance + caching.",
        9,
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
            # visibility=connected — any LOGGED-IN user can see the channel
            #                       on the catalogue (anonymous visitors
            #                       are bounced to the login page).
            # enroll=public        — any logged-in user can self-enroll
            #                       without admin invite. Together: internal
            #                       staff sign in to Odoo, see the catalogue,
            #                       click Join, immediately read lessons.
            #
            # The combo `visibility=members + enroll=public` is rejected by
            # the slide_channel_check_enroll constraint (members-only but
            # self-enrolling is contradictory). For an admin-gated internal
            # roll-out, flip enroll to 'invite' AND visibility to 'members'.
            f.write("            <field name=\"visibility\">connected</field>\n")
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
