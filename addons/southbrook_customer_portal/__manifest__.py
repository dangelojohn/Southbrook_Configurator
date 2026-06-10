# SPDX-License-Identifier: LGPL-3.0-only
{
    "name": "Southbrook Customer Portal",
    "summary": "Customer-facing /my/kitchen-projects portal — review A/B/C "
               "concepts, approve one, download quote + drawings.",
    "description": """
Southbrook Customer Portal (Module 8 — Phase 1)
================================================

Extends Odoo's portal module with the customer-facing kitchen-project
review experience.

Routes:
  GET  /my/kitchen-projects                — list customer's projects
  GET  /my/kitchen-project/<id>            — review the A/B/C concepts
  POST /my/kitchen-project/<id>/select/<option_id>   — pick an option
  POST /my/kitchen-project/<id>/approve    — final customer approval

Approval wiring:
  Selecting an option flips sb.kitchen.design.option.is_selected
  (Module 5 one-of-N enforcement).
  Approving creates an sb.kitchen.approval (approver_type=customer)
  and advances the project state via action_customer_approves().

ACL discipline (init-doc):
  Public ACL boundary tested as anonymous SECOND customer. A customer
  must NEVER see another customer's project. Record rule on
  sb.kitchen.project: visible to a portal user only when partner_id
  matches their res.users.partner_id.

Three.js KitchenCanvas (Phase 2):
  The init-doc Module 8 calls for a Three.js live preview of the
  Configuration Engine output. That's a substantial OWL frontend
  deliverable; Phase 1 ships server-rendered QWeb option cards so the
  approval flow works end-to-end. KitchenCanvas plugs in via an extra
  template later — no model changes.
""",
    "author": "Southbrook Kitchens / OdooIQ",
    "license": "LGPL-3",
    "category": "Manufacturing",
    "version": "19.0.0.3.0",
    "depends": [
        "portal",
        "southbrook_kitchen_workspace",
        "southbrook_config_engine",
    ],
    "data": [
        "security/southbrook_customer_portal_security.xml",
        "security/ir.model.access.csv",
        "views/kitchen_portal_templates.xml",
    ],
    # NB: kitchen_canvas.js + kitchen_dims.js are NOT registered as
    # asset-bundle entries. Odoo's bundler does not transform their
    # native ES module imports (Three.js from CDN, relative
    # ./kitchen_dims.js). They are loaded directly via
    # <script type="module" src="..."> in views/kitchen_portal_templates.xml
    # and served from /southbrook_customer_portal/static/src/js/* by the
    # standard static-file handler.
    "installable": True,
    "application": False,
    "auto_install": False,
}
