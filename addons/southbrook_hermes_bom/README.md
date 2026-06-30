# Southbrook Hermes — Product Research & BOM Builder

Wizard-driven product research and BOM proposal flow for Odoo 19.0 CE,
built on top of the OCA `product_configurator` suite. From a
Configurable Template (or a Configured Variant), a Hermes Reviewer
dispatches a research job to an external Hermes endpoint, reviews
proposed enrichment + a derived BOM, and selectively applies the
changes back to `product.template` / `mrp.bom`.

Sibling addon to `southbrook_hermes` (Fabio recommendation queue) —
the two share no models, no security groups, and no
`ir.config_parameter` namespace. Either can be installed without the
other.

---

## Quick start

```bash
# 1. Install the module on a southbrook (or any product_configurator-enabled) DB.
docker exec <odoo-container> bash -lc \
    "odoo --stop-after-init -d <db> -i southbrook_hermes_bom --no-http"

# 2. Bring up the staging mock so the wizard has somewhere to call.
docker compose -f staging/docker-compose.yml up -d --build

# 3. Set the API key (any string — the mock accepts whatever the
#    Dockerfile sets in HERMES_MOCK_TOKEN; default "TEST-KEY").
#    The endpoint defaults to http://localhost:7100/v1/research on
#    fresh installs.
docker exec <odoo-container> bash -lc \
    "echo \"env['ir.config_parameter'].sudo().set_param('southbrook_hermes_bom.api_key', 'TEST-KEY')\" \
     | odoo shell -d <db> --no-http"

# 4. Open any Configurable Template, click "Research & Build BOM with
#    Hermes", run the wizard.
```

When you're ready to point at a real Hermes service, override
`southbrook_hermes_bom.endpoint` via Settings → Technical → System
Parameters.

---

## Dependencies

- `base`, `mail`, `mrp` (Odoo core)
- `product_configurator` + `product_configurator_mrp` (OCA, v19)

The OCA modules ship the `product.config.session`, `product.config.step`,
the Configure / Reconfigure Product buttons, and the `mrp.bom.config_ok`
+ `mrp.bom.line.config_set_id` extensions this addon hooks into.

---

## What it adds

| Surface | Where | Notes |
|---|---|---|
| Launch button | Configurable Templates form header | After OCA's "Configure Product" button. Group-gated. |
| Launch button | Configured Variants form header | After OCA's "Reconfigure Product" button. Same group. |
| Smart-button counter | Template form `button_box` | Click → filtered jobs list. Single grouped query, no N+1. |
| Wizard | `hermes.wizard` (TransientModel) | collecting → researching → review → applying → done/error. |
| Audit row | `hermes.research.job` | `mail.thread` + `mail.activity.mixin`. Read+create for users; write via wizard sudo() only. |
| Menu | Manufacturing → Hermes BOM → Research Jobs | Filtered list with state coloring. |
| Cron | Nightly | GC drops draft/running/review/failed older than `retention_days` (default 180). Applied jobs immortal. |

---

## Configuration (`ir.config_parameter`)

All keys are namespaced `southbrook_hermes_bom.*` — distinct from
`southbrook_hermes.*` (Fabio) so install order is irrelevant.

| Key | Default | Purpose |
|---|---|---|
| `southbrook_hermes_bom.api_key` | _(empty)_ | Bearer token sent in `Authorization: Bearer …`. Missing → clean `UserError`. |
| `southbrook_hermes_bom.endpoint` | `http://localhost:7100/v1/research` | POST URL. Default lands on the staging mock — repoint at a real service when one exists. |
| `southbrook_hermes_bom.retention_days` | `180` | GC cron retention window for non-applied jobs. `0` disables GC. |

`data/hermes_config_data.xml` is `noupdate="1"`, so existing deploys
keep their current values on `-u` — only fresh installs get the new
defaults.

---

## Security model

- `southbrook_hermes_bom.group_hermes_user` — "Hermes BOM Builder".
  Implies `mrp.group_mrp_user`. `base.group_system` is implied into
  this group at install time so admins inherit access; an
  `uninstall_hook` tears the link down on uninstall so reinstall is
  clean.
- `hermes.research.job` ACL: `read=1, write=0, create=1, unlink=0` for
  the user group. The wizard `sudo()`s every state-write — a Hermes
  reviewer cannot directly tamper with the audit trail.
- `hermes_request_payload` field on the audit row is restricted to
  `base.group_system`. The other audit fields (parsed enrichment,
  applied fields, source URLs) stay visible to the reviewer; the raw
  collected product context (cost, internal notes, southbrook_*) is
  admin-only.
- Applied audit rows refuse `unlink` for non-admins (`UserError` with
  the job name). Admins can still drop them; the GC cron uses `sudo()`
  to bypass the guard for retention sweeps.

---

## Idempotency + concurrency

- **BOM marker.** Hermes-managed BOMs are identified by EXACT code
  match `"<default_code> Hermes"`. Substring matching was the v1 bug
  — it false-positively matched user BOMs whose code happened to
  contain "Hermes" and silently destroyed them. Detection +
  creation use the same expression in `_hermes_bom_code()`.
- **Advisory lock.** `pg_advisory_xact_lock(HERMES_BOM_LOCK_NS,
  template_id)` is held across `_find_hermes_bom` → create so two
  concurrent reviewers can't both observe "no existing BOM" and
  create duplicates. Namespace constant is `0x48424F4D` ("HBOM"); held
  until end of transaction.
- **TOCTOU re-check.** `existing_bom_state` is captured at research
  time for UX; the apply step re-reads
  `mrp.production.search_count(bom_id=…)` against live state and
  refuses if any MO now references the BOM.
- **Empty-BOM guard.** If every proposed line fails matching/validation,
  the wizard refuses to touch an existing Hermes BOM rather than
  leaving it with zero lines. The reviewer sees a chatter post listing
  every skipped line + reason.

---

## Apply-time rules

- **`bom_type`.** CE 19 selection is `normal`/`phantom` only.
  `subcontract` is Enterprise — a Hermes proposal of `subcontract`
  falls back to `normal` (warning logged) rather than raising
  `ValueError` on create.
- **Product matching.** SKU exact (`default_code = …`, `active = True`)
  first; then `name =` fallback restricted to `active = True`, ordered
  `id asc` for determinism. Hermes payload `qty` is REQUIRED and must
  be `> 0` — no silent default to 1.0.
- **Enrichment writes.** Only `name`, `description_sale`, `description`,
  `description_purchase` are auto-applied. Manufacturer fields are
  shown in review but never auto-written (target fields are
  Marathon-Hardware-specific). Writes obey `HIGH_CONFIDENCE_THRESHOLD`
  (`0.85`): low-confidence proposals do NOT overwrite non-empty
  existing values. Names get an extra placeholder list
  (`"e.g. Cheese Burger"`, etc.) so the Odoo-default scaffold name is
  always overwritable.

---

## Error handling

- `_mark_error` writes through `self.env.registry.cursor()` — a fresh
  cursor with its own transaction — so a re-raised `UserError`
  rolling back the surrounding HTTP-dispatcher savepoint doesn't
  erase the failure state. The audit row reliably ends up in
  `state='failed'` with `error_message` populated.
- `services/hermes_service.py` converts every transport, JSON, and
  shape error into a `UserError` so the browser-side widget gets a
  readable message. The API key is never embedded in any log line,
  exception, or chatter post.

---

## Tests

24 cases across three test modules — `~60s` cold, `~30s` warm. Run
locally:

```bash
docker exec <odoo-container> bash -lc \
    "odoo --stop-after-init -d <db> -u southbrook_hermes_bom \
        --no-http --test-enable --test-tags=/southbrook_hermes_bom"
```

CI runs the same suite on every push — see `.forgejo/workflows/tests.yml`.

Coverage:

- BOM-creation happy path (`tests/test_hermes_bom_creation.py`)
- Duplicate prevention (`tests/test_hermes_duplicate_prevention.py`)
- Gap coverage — TOCTOU, canonical-code vs decoy, confidence gating,
  `subcontract` fallback, all-invalid → existing BOM untouched, GC
  cron, unlink guard, admin-only payload field
  (`tests/test_hermes_gap_coverage.py`)

---

## Staging mock

`staging/` ships a stdlib-only HTTP server that responds with a canned
hermes-shaped payload. End-to-end verification against the live
southbrook stack used this mock — see `staging/README.md` for the
runbook.

---

## License

LGPL-3.0-only. © Southbrook Cabinetry.

---

## Related

- `southbrook_hermes` (Fabio recommendation queue + JWT tool dispatcher)
  — sibling addon, distinct namespaces.
- `product_configurator` (OCA, v19) — provides the configurator
  session and step models this addon reads.
- `product_configurator_mrp` (OCA, v19) — provides the
  `mrp.bom.config_ok` + `mrp.bom.line.config_set_id` extensions.

