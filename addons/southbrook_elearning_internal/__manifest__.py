# SPDX-License-Identifier: LGPL-3.0-only
{
    "name": "Southbrook Internal E-Learning",
    "summary": "Internal training series for Southbrook custom modules — "
               "29 lessons across 7 courses, auto-installed into "
               "Odoo's eLearning portal.",
    "description": """
Southbrook Internal E-Learning
==============================

Installs a 7-course, 29-lesson internal training series into Odoo's
website_slides eLearning portal at /odoo/e-learning, covering ONLY the
Southbrook custom modules (the OOTB Odoo courses are taught separately).

Course matrix
-------------

  Course 1 — Workcenter Operators (7 lessons): edge banding (SB-EDGE),
    CNC (SB-CNC-BORE + CNC02 backup), assembly (SB-ASSY + SB-DOOR),
    sanding/finishing (SAND/PAINT/CURE), downtime logging, cut spec.
  Course 2 — Production Planning (5 lessons): kitchen projects, release
    gate, bottleneck scheduling, the 6 orchestration crons, MI reports.
  Course 3 — Floor Management (3 lessons): MI dashboards, Fabio
    approvals, OEE.
  Course 4 — PLM + Design (4 lessons): ECOs, cut specs, FreeCAD bridge,
    AI design assist (Gemini).
  Course 5 — Estimating + Configurator (4 lessons): OCA configurator
    basics, quote build, hardware catalog (Marathon), v2 UX deltas.
  Course 6 — Customer Touchpoints (3 lessons): customer portal, dealer
    portal, Fabio CS view.
  Course 7 — Sysadmin (3 lessons): orchestration crons, backups,
    external Hermes Console.

How the content is generated
----------------------------

The lesson source-of-truth lives at ``docs/elearning/*.md`` in the
southbrook-v19cr repo. ``scripts/build_data_xml.py`` (in this addon)
reads each markdown file, parses its YAML frontmatter, converts the
body to HTML, and emits one ``elearning_courses.xml`` plus per-course
``elearning_slides_NN.xml`` data files. Re-run the script any time a
lesson is edited; commit the regenerated XML; ``odoo -u
southbrook_elearning_internal`` refreshes the live records.

Why the channels + slides are published by default
--------------------------------------------------

``visibility=public`` + ``enroll=public`` + ``is_published=True`` so
the courses appear at /odoo/e-learning the moment the addon is
installed. Internal staff can navigate the catalogue without any
group-membership setup. If you want the courses behind a login,
flip ``visibility`` to ``members`` in the XML and re-upgrade.
""",
    "version": "19.0.1.0.0",
    "license": "LGPL-3",
    "author": "Southbrook Cabinetry",
    "website": "https://southbrookcabinetry.space",
    "category": "Website/eLearning",
    "depends": ["website_slides"],
    "data": [
        "data/elearning_courses.xml",
        "data/elearning_slides_01.xml",
        "data/elearning_slides_02.xml",
        "data/elearning_slides_03.xml",
        "data/elearning_slides_04.xml",
        "data/elearning_slides_05.xml",
        "data/elearning_slides_06.xml",
        "data/elearning_slides_07.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
