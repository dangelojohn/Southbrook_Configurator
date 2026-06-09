# SPDX-License-Identifier: LGPL-3.0-only
{
    "name": "Southbrook Kitchen Workspace",
    "summary": "The designer-facing workspace for a kitchen project — "
               "photos, AI analysis, design options A/B/C, appliance layout, "
               "approval lifecycle, and the bridge into production.",
    "description": """
Southbrook Kitchen Workspace (Module 5)
========================================

Five first-class entities the workspace orchestrates:

* sb.kitchen.project — the parent record. State machine
  (draft → designing → awaiting_customer → approved → in_production →
  done / cancelled), partner + opportunity link, theme, photos via
  mail.thread, links to all the child records below.
* sb.kitchen.design.option — concept A/B/C. Per project; one-of-N
  selection (selecting one clears the others). Carries a JSON
  placement_data field that Module 7 fills.
* sb.kitchen.ai.analysis — Gemini's output for one project. Carries
  the confirmed_by_human boolean that gates downstream config-engine
  work (GAP-02 / human-confirmation gate per init doc Module 6).
* sb.kitchen.appliance — appliance items present in the room (stove,
  fridge, dishwasher, sink, etc.). Each carries dimensions, required
  clearances, and its own confirmed_by_human flag.
* sb.kitchen.approval — approval records (concept / design / engineering
  / production-release) for the project lifecycle.

The 3-panel OWL workspace UX (Left: customer/opp/theme; Center: photos/
AI/options; Right: CAD/revisions/approval; Footer: validate/generate/
quote/submit/release) is a Phase-2 frontend deliverable. This commit
ships the data model + standard backend views; the OWL components land
when the design + spec are written.
""",
    "author": "Southbrook Kitchens / OdooIQ",
    "license": "LGPL-3",
    "category": "Manufacturing",
    "version": "19.0.0.1.0",
    "depends": [
        "mail",
        "crm",
        "southbrook_estimating",
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/sequence_data.xml",
        "data/mail_templates.xml",
        "views/sb_kitchen_project_views.xml",
        "views/sb_kitchen_design_option_views.xml",
        "views/sb_kitchen_ai_analysis_views.xml",
        "views/sb_kitchen_appliance_views.xml",
        "views/sb_kitchen_approval_views.xml",
        "views/southbrook_kitchen_workspace_menus.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
