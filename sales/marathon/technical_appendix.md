# Technical Appendix — KitchenForge × Marathon Integration
### For Marathon CTO / IT Lead

Platform: Odoo 19 CE. Addons: `kitchenforge_core`, `kitchenforge_marathon`, `kitchenforge_saas`. Existing hardware substrate: `southbrook_hardware_catalog` (Marathon partner + 20 finishes + 5 knob templates seeded). Live reference instance: `southbrookcabinetry.space`.

This document describes the three integration primitives and the contracts Marathon's systems consume or expose.

---

## 1. Telemetry endpoint

**Direction:** KitchenForge → Marathon BI
**Transport:** HTTPS POST, JSON, signed with per-tenant HMAC-SHA256 in `X-KF-Signature` header.
**Endpoint (Marathon-hosted):** `POST https://bi.marathon.example/kf/v1/spec_event`
**Auth:** API key in `X-Api-Key` (per-tenant, rotated quarterly via control plane).
**Cadence:** Fired on cabinet record commit and on quote-state transitions (`draft → sent`, `sent → won`, `won → cancelled`).

### Event schema (v1)

```json
{
  "event_id": "01HQXA8Z-uuid-v7",
  "event_type": "cabinet.specced",
  "occurred_at": "2026-06-15T14:22:31Z",
  "tenant": {
    "kf_tenant_id": "kf_tnt_8a31",
    "shop_name": "Halton Cabinet Co.",
    "branch_locator": "ON-L6H"
  },
  "project": {
    "kf_project_id": "kf_prj_44a9",
    "stage": "quoted",
    "total_cabinets": 18,
    "estimated_value_usd": 24800
  },
  "cabinet": {
    "kf_cabinet_id": "kf_cab_7720",
    "type": "B30",
    "finish_code": "MAR-FIN-014",
    "hardware_lines": [
      {"sku": "MAR-DS-21-FE", "qty": 2, "kind": "drawer_slide"},
      {"sku": "MAR-HG-110-SC", "qty": 4, "kind": "hinge"},
      {"sku": "MAR-PL-128-MB", "qty": 1, "kind": "pull"}
    ]
  },
  "marathon_spec_value_usd": 84.40,
  "schema_version": "1.0.0"
}
```

**Retry policy:** 3 attempts with exponential backoff (5s / 30s / 5min), then dead-letter queue at the KF side. Marathon endpoint must return `202 Accepted` within 2s; any 5xx triggers retry.
**Idempotency:** `event_id` is a UUIDv7. Marathon must dedupe on `event_id`.
**Volume estimate:** At base-case scale (460 shops × 45 cabinets/mo × ~3 state transitions) ≈ 62K events/mo, peaking ~5 events/sec end-of-month.

---

## 2. Rebate ledger schema

**Storage:** `kitchenforge_marathon.rebate_ledger` (Odoo model) on the KF control plane, replicated nightly to Marathon's finance system via a signed reconciliation file.
**Currency:** USD, stored as `Monetary` with `currency_id` FK.
**Reconciliation cadence:** Monthly cutover at 23:59 UTC on the last calendar day.

### Model: `kf.rebate.entry`

| Field | Type | Description |
|---|---|---|
| `id` | int (PK) | Odoo PK |
| `ledger_key` | char(48) | Stable hash of `event_id + cabinet_id` — dedupe key |
| `event_id` | char(36) | Originating telemetry event |
| `tenant_id` | many2one → `res.partner` | Shop that earned the rebate |
| `cabinet_ref` | char(64) | KF cabinet ID |
| `marathon_spec_value` | monetary | Spec'd Marathon hardware $ on this cabinet |
| `rebate_amount` | monetary | Default $8.00 USD; configurable per channel agreement |
| `accrued_at` | datetime | When cabinet hit `quote.won` state |
| `reconciled_at` | datetime | When monthly file was generated |
| `marathon_invoice_ref` | char(64) | Marathon-side invoice ref once paid |
| `state` | selection | `accrued / reconciled / invoiced / paid / disputed` |

### Reconciliation file

Nightly NDJSON drop to a Marathon-controlled S3 bucket (or SFTP — Marathon's choice). Each line is one `kf.rebate.entry` in `state=accrued`, transitioned to `reconciled` on successful drop. Marathon's AP system flips state to `paid` on settlement; KF accepts a return file (same schema, `paid_at` + `marathon_invoice_ref` populated).

**Dispute window:** 30 days from `reconciled_at`. Disputed entries flip to `disputed` and require manual reconciliation between Southbrook and Marathon ops.

---

## 3. Auto-RFQ flow

**Trigger conditions (any of):**
- Cabinet hardware line value > $500 USD (configurable per shop)
- SKU not in Marathon's branch stocking depth for the shop's `branch_locator`
- Shop manually clicks "Request quote from Marathon" in the cabinet editor

**Direction:** KitchenForge → Marathon branch system (via Marathon-hosted RFQ ingestion endpoint, or email-to-API fallback for branches not yet on the digital RFQ stack).

### RFQ payload

```json
{
  "rfq_id": "kf_rfq_01HQ...",
  "originated_at": "2026-06-15T14:25:00Z",
  "shop": {
    "kf_tenant_id": "kf_tnt_8a31",
    "shop_name": "Halton Cabinet Co.",
    "branch_locator": "ON-L6H",
    "contact_email": "shop@halton.example",
    "contact_phone": "+1-905-555-0142"
  },
  "project_summary": {
    "kf_project_id": "kf_prj_44a9",
    "cabinet_count": 18,
    "estimated_close_date": "2026-07-10"
  },
  "lines": [
    {
      "sku": "MAR-DS-21-FE",
      "qty": 36,
      "kind": "drawer_slide",
      "needed_by": "2026-06-28",
      "kf_cabinet_refs": ["kf_cab_7720", "kf_cab_7721", "..."]
    }
  ],
  "callback_url": "https://api.kitchenforge.app/v1/rfq/kf_rfq_01HQ.../quote",
  "callback_token": "Bearer eyJ..."
}
```

Marathon's branch quote comes back via `POST` to `callback_url` with line-level pricing, lead time, and availability. KF surfaces the quote in the shop's quoting tool within seconds — the shop accepts/declines without leaving the workflow.

**SLA target:** Branch responds within 4 business hours during pilot, 1 business hour at steady state.

---

## Security, data residency, and ops

- **Tenancy isolation:** Per-shop Postgres schemas behind a shared Odoo control plane; cross-tenant queries blocked at the ORM layer.
- **Auth:** Per-tenant `X-Api-Key` rotated quarterly; HMAC-SHA256 request signing on the telemetry channel.
- **Data residency:** Telemetry and rebate ledger primary store is Canadian (QNAP Mississauga-region datacenter today; production-grade hosting evaluated as part of SaaS rollout).
- **PII scope:** Shop contact info only. No end-customer PII in telemetry. Rebate ledger has no consumer data.
- **Logging:** Application logs rotate nightly, retained 30 days; rebate ledger entries retained 7 years per CRA recordkeeping rules.
- **Observability:** Marathon gets read-only Grafana access to a channel dashboard (event volume, RFQ latency, rebate accruals, reconciliation status).
- **Sandbox:** Marathon's IT team gets a non-production tenant + staging endpoints from day one. The first 4 weeks of integration happen in sandbox before any production traffic flips.

---

## What we need from Marathon IT to start

1. A telemetry ingestion URL (we'll provide a sample receiver in Python or Node if helpful).
2. SFTP or S3 drop target for the nightly reconciliation file.
3. RFQ ingestion endpoint (or confirmation of email-to-API fallback for branches not yet digital).
4. A primary IT contact for the 4-week sandbox integration window.
5. Full Marathon SKU master under NDA — attributes we care about: SKU, finish, dimension, weight class, branch stocking depth, list price. CSV or API, either is fine; we have the import wizard either way.
