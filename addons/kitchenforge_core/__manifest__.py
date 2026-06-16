# SPDX-License-Identifier: LGPL-3.0-only
{
    "name": "KitchenForge Core",
    "summary": "Project-template-as-spine for kitchen MRP. Quote-to-MO in 6 clicks. "
               "AI-agent-native filesystem surface for design + manufacturing workflows.",
    "description": """
KitchenForge Core
=================

Turns Odoo Project into the manufacturing PM spine for kitchen cabinet shops.

* **Spine** — `project.project.is_template` + seed templates (Full Kitchen,
  Partial Reno, Single Custom). A one-click wizard instantiates a Project +
  draft Sale Order with configurator lines pre-populated, dropping
  quote-to-released-MO from ~125 clicks to ~6.
* **Auto-route to MRP** — configurator-generated variants are auto-routed to
  `manufacture`, so SO confirm spawns confirmed MOs through procurement
  without the salesperson context-switching to the Manufacturing app.
* **AI-agent-native** — `/agent/v1/files/*` filesystem surface (read/write/diff
  over templates, projects, catalog, shop) + `/agent/v1/tools/*` typed action
  endpoints. Modelled after magicpath.ai/files: a navigable, schema-validated
  tree LLM agents can list, read, mutate, and act on. Bring-your-own-agent —
  works with Claude/GPT/Gemini via the published OpenAPI + manifest.

Sits on top of (does not duplicate) southbrook_project_mrp, southbrook_estimating,
product_configurator_*, southbrook_api, southbrook_hardware_catalog, southbrook_plm.
""",
    "version": "19.0.1.0.0",
    "license": "LGPL-3",
    "author": "Southbrook Cabinetry / OdooIQ",
    "category": "Manufacturing/Project",
    "depends": [
        "southbrook_project_mrp",
        "southbrook_estimating",
        "product_configurator_sale",
        "product_configurator_mrp",
        "southbrook_hardware_catalog",
        "southbrook_api",
    ],
    "data": [
        "security/kitchenforge_security.xml",
        "security/ir.model.access.csv",
        # NOTE: ACL for new models (kitchenforge.template.line,
        # kitchenforge.instantiate.wizard) is applied post-install via ORM.
        # See kf_zip_install.py's _post_install_acl() — base_import_module
        # processes data files BEFORE Python classes register, so model_id
        # lookups for new models can't resolve at parse time.
        "data/ir_sequence.xml",
        "data/project_templates.xml",
        "views/project_views.xml",
        "views/sale_order_views.xml",
        "wizards/instantiate_from_template_views.xml",
        "views/menus.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "kitchenforge_core/static/src/js/order_builder_grid.esm.js",
        ],
    },
    "installable": True,
    "application": True,
}
