# KitchenForge SaaS Control Plane

The third addon in the KitchenForge stack. Productizes the QNAP-style
per-tenant Odoo+Postgres+Caddy demo pattern as a multi-tenant SaaS, with
Odoo itself as the control plane.

## Position in the stack

```
kitchenforge_saas        ← THIS ADDON (control plane, billing, provisioning)
        │
        ├── kitchenforge_marathon   (channel partner integration)
        │
        └── kitchenforge_core       (project-template spine + agent FS)
                │
                └── southbrook_api  (X-Api-Key + idempotency framework)
```

`kitchenforge_saas` consumes the southbrook_api auth layer for its REST
surface, and consumes the marathon channel-config + rebate ledger to
know which tenants should participate in partner economics.

## What it owns

### Models

| Model | Role |
|---|---|
| `kitchenforge.tenant` | One row per cabinet-shop subscriber. Status, tier, billing, lifecycle timestamps, infra pointers. |
| `kitchenforge.tenant.event` | Audit log of every status transition + webhook. |
| `kitchenforge.subscription.plan` | Pricing tiers: Marathon Channel $149, Direct $599, Enterprise $2500. |
| `res.company` (inherit) | White-label branding fields + `kitchenforge_tenant_id` back-link. |

### Lifecycle

```
pending ──[action_provision]──▶ provisioning ──[mark_provisioned]──▶ live
                                       │                              │
                                       │                       [action_suspend]
                                       │                              │
                                       │                              ▼
                                       │                          suspended
                                       │                              │
                                       │                       [action_resume]
                                       │                              │
                                       │◀─────────────────────────────┘
                                       │
                                       └──[action_cancel]──▶ cancelled (terminal)
```

`action_provision` is fire-and-forget: it flips status, signals an
off-Odoo provisioner via the `kitchenforge_saas.provisioner_webhook_url`
config parameter, and waits for that provisioner to call back into
`mark_provisioned()` once the docker-compose + Caddy snippet are wired.

### REST API — `/saas/v1/*`

Auth: `X-Api-Key` header (reuses `southbrook_api.requires_api_key`).
ACL: intended for keys whose user has
`group_kitchenforge_saas_operator`.

| Method | Path | Effect |
|---|---|---|
| `GET` | `/saas/v1/tenants` | List, optional `?status=` filter. |
| `POST` | `/saas/v1/tenants` | Create + auto-provision unless `auto_provision: false`. |
| `GET` | `/saas/v1/tenants/<id>` | Fetch one. |
| `POST` | `/saas/v1/tenants/<id>/suspend` | `action_suspend()`. |
| `POST` | `/saas/v1/tenants/<id>/resume` | `action_resume()`. |
| `POST` | `/saas/v1/tenants/<id>/cancel` | `action_cancel()`. |
| `POST` | `/saas/v1/tenants/<id>/provision` | Re-trigger provisioning. |
| `POST` | `/saas/webhooks/stripe` | Stripe event receiver (signature verified). |

### Stripe integration

`models/stripe_client.py` is intentionally thin. It reads the secret
from `ir.config_parameter` (`kitchenforge_saas.stripe_secret_key`)
and the webhook secret from
`kitchenforge_saas.stripe_webhook_secret`. If the `stripe` package isn't
importable, or either secret is missing, every method is a logged
no-op — the addon installs and tests cleanly without Stripe credentials.

Plans are matched to Stripe Prices via `lookup_key = plan.code`. The
operator pre-creates `marathon_channel`, `direct`, `enterprise` Prices
in Stripe.

### Cron

`cron_recompute_usage` runs daily, counting cabinets (sale order lines)
confirmed in the last 30 days per live tenant.

### Security groups

| Group | Powers |
|---|---|
| `group_kitchenforge_saas_operator` | Full CRUD on tenants + events + plans. Sees every tenant. |
| `group_kitchenforge_saas_billing` | Read-only on tenants + events; CRUD on plans. Cannot lifecycle. |

## Configuration

After install, set the following `ir.config_parameter` entries:

| Key | Purpose |
|---|---|
| `kitchenforge_saas.stripe_secret_key` | Stripe API secret (`sk_live_…` / `sk_test_…`). |
| `kitchenforge_saas.stripe_webhook_secret` | Stripe webhook signing secret (`whsec_…`). |
| `kitchenforge_saas.provisioner_webhook_url` | URL the off-Odoo provisioner listens on for `provision`/`suspend`/`resume`/`cancel` signals. |

## What it deliberately does NOT do

- The docker-compose write, Caddy reload, and Postgres bootstrap stay
  with an external provisioner (script / Ansible / k8s operator). The
  Odoo side just signals it. This keeps the control plane portable
  across infra targets.
- Real Stripe usage-based billing — only sticker-price subscriptions.
  Per-cabinet rebate accounting lives in `kitchenforge_marathon`.
- DNS / certificate provisioning — done out-of-band; the Caddy config
  the provisioner writes is the seam.
