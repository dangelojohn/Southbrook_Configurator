# SPDX-License-Identifier: LGPL-3.0-only
{
    "name": "KitchenForge SaaS Control Plane",
    "summary": "Multi-tenant control plane: tenants, plans, Stripe billing, "
               "white-label branding, and a control REST API for provisioning "
               "isolated KitchenForge instances.",
    "description": """
KitchenForge SaaS Control Plane
===============================

The control-plane addon for productizing KitchenForge as a multi-tenant SaaS.
Mirrors the QNAP demo-stack pattern (one isolated Odoo+Postgres+Caddy stack
per cabinet shop subscriber) as a first-class Odoo model, then wraps it in
billing, lifecycle automation, and a programmatic REST surface so
provisioning can be driven from CI, dashboards, or partners.

* **Tenants** — `kitchenforge.tenant` is one record per cabinet-shop
  subscriber. Tracks status (pending/provisioning/live/suspended/cancelled),
  pricing tier, Stripe customer + subscription, MRR, seat count, 30-day
  cabinet throughput, and pointers to the provisioned docker-compose +
  Caddy snippet on the host.
* **Lifecycle** — `action_provision()`, `action_suspend()`, `action_resume()`,
  `action_cancel()` flip status, stamp timestamps, write a
  `kitchenforge.tenant.event` audit row, and (for provision) emit a
  webhook signal to an off-Odoo provisioner that owns the docker side.
* **Plans** — `kitchenforge.subscription.plan` carries pricing tiers
  (Marathon Channel $149, Direct $599, Enterprise $2500) with seat /
  active-project caps and a Marathon-rebate eligibility flag.
* **Stripe** — `models/stripe_client.py` is a thin wrapper that pulls the
  secret from `ir.config_parameter` and degrades gracefully (log-only) if
  the `stripe` package isn't importable. A `/saas/webhooks/stripe` route
  receives subscription events.
* **White-label** — `res.company` gains brand logo + primary/secondary
  colour fields plus a `kitchenforge_tenant_id` back-link, so a single
  Odoo can host a branded surface per tenant.
* **Control REST** — `/saas/v1/tenants` (list/create/get) plus
  `/saas/v1/tenants/<id>/suspend|resume|cancel`. Auth reuses the
  southbrook_api `requires_api_key` decorator; intended for superuser
  keys only.

Sits on top of (does not duplicate) kitchenforge_core, kitchenforge_marathon,
southbrook_api.
""",
    "version": "19.0.1.0.0",
    "license": "LGPL-3",
    "author": "Southbrook Cabinetry / OdooIQ",
    "category": "Manufacturing/Project",
    "depends": [
        "kitchenforge_core",
        "kitchenforge_marathon",
        "southbrook_api",
    ],
    "data": [
        "security/kitchenforge_saas_security.xml",
        "security/ir.model.access.csv",
        "data/ir_cron.xml",
        "data/subscription_plans.xml",
        "views/tenant_views.xml",
        "views/tenant_event_views.xml",
        "views/subscription_plan_views.xml",
        "views/res_company_views.xml",
        "views/menus.xml",
    ],
    "installable": True,
    "application": False,
}
