# SPDX-License-Identifier: LGPL-3.0-only
{
    "name": "Southbrook Project",
    "summary": "Cabinetry-shop polish on stock Odoo Project — responsive "
               "Kanban, seeded tags, project-1 defaults, task-dependency + "
               "milestone toggles, and cabinetry-specific custom fields on "
               "project.task.",
    "description": """
Southbrook Project
==================

Targets the manual-QA findings on the live southbrookcabinetry.space
project instance. Four tiers, each in a separate commit:

* **Tier 1** — Responsive Kanban: forces multi-column layout at
  desktop widths (>=1280 px) and eager card load for projects with
  small task counts. Pure SCSS asset; no JS patching.
* **Tier 2** — Configuration data: 6 `project.tags` (Rush, Custom,
  Warranty, Repair, Kitchen, Vanity); description + planned date +
  email alias on project ID 1. Stages were already seeded.
* **Tier 3** — Feature toggles: `allow_task_dependencies` +
  `allow_milestones` enabled on project 1. Recurring + billable
  left as operator toggles.
* **Tier 4** — Cabinetry fields on `project.task`:
  `x_southbrook_material_species`, `x_southbrook_unit_count`,
  `x_southbrook_hardware_specs`, `x_southbrook_sale_order_id`.
  Plus a child-count compute that does NOT inflate the parent's
  task count, and a clarified priority label.

Guardrails respected:

* No ACL / share / follower / visibility changes.
* No user account creation.
* No credential handling.

These are flagged in the README for a human operator.
    """,
    "author": "Southbrook Cabinetry / OdooIQ",
    "license": "LGPL-3",
    "category": "Services/Project",
    "version": "19.0.0.1.0",
    "depends": [
        "project",
    ],
    "data": [
        "data/project_tags.xml",
        "views/project_task_views.xml",
    ],
    "post_init_hook": "post_init_backfill_project_1",
    "assets": {
        "web.assets_backend": [
            "southbrook_project/static/src/scss/kanban_responsive.scss",
        ],
    },
    "installable": True,
    "application": False,
    "auto_install": False,
}
