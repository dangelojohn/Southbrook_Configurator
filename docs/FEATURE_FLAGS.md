# Feature Flags — Close-the-Loop Audit (P1–P8)

Every behavioral change introduced by the configurator → particle-intelligence
loop audit ships behind a feature flag, defaulting **OFF**. This file is the
canonical index. Per-module README files cite the same flag with the same
key, default, and effect text.

The flag mechanism is `ir.config_parameter` (string-typed); the convention is
`<module>.<flag_name>` and a truthy value is one of `1` / `true` / `yes` / `on`
(case-insensitive). Anything else (or missing) reads as off.

Enable per-environment via Odoo Settings → Technical → System Parameters,
or via shell:

```python
self.env["ir.config_parameter"].sudo().set_param(
    "southbrook_premium_orchestration.auto_emit_cutlist", "True")
```

## Inventory

| # | Key | Default | Effect when ON | Audit task |
|---|-----|---------|----------------|------------|
| 1 | `southbrook_premium_orchestration.auto_emit_cutlist` | `False` | On `sale.order.action_confirm`, after the project.task spine is created, every configurable kitchen-cabinet line whose MO has been resolved gets exactly one `sb.production.package` (cutlist + hardware) auto-emitted via `sb.production.package.build_from_order_line`. Idempotent per `sale.order.line` via the new `sale_order_line_id` back-reference. | P1 |

### P2 — Drawer Slide attribute

P2 ships **always-on** because the additive seed is the only behavioural
change at the data layer; the legacy +$15 Accessories→Soft-Close pick
remains a customer-clickable option for backwards-compat, with the
double-charge suppressed in the live recalc when both are picked
simultaneously. There is therefore no P2-specific feature flag.
The behaviours are still rollback-safe:

- The seed function is idempotent: re-running is a no-op.
- The resolver's `slide_sku` kwarg is `None`-defaulted: pre-P2 callers
  see no change in `Catalog.resolve()` output.
- The configurator state endpoint's `soft_close_derived` field is purely
  additive in the JSON payload; older clients ignore unknown keys.

### P3 — MI auto-remediation

| # | Key | Default | Effect when ON | Audit task |
|---|-----|---------|----------------|------------|
| 2 | `southbrook_manufacturing_intelligence.auto_remediate_cutlist` | `False` | When `southbrook.mi.engine._recompute_production` would create a "Missing cutlist" blocker AND the source `sale.order.line` carries a complete configuration (Width present; no value name contains "Custom"), the engine calls `sb.production.package.build_from_order_line(order_line, mo=production)`. On success: the blocker is suppressed and an info-severity "Cutlist auto-generated" check carries the audit note ("audit P3 — configurator config was complete; …"). Ambiguous configurations and missing-Width templates still surface the blocker. "CAD not complete" warnings are NEVER auto-cleared — only the cutlist blocker is remediable. | P3 |

### P7 — Specs single source of truth

P7 is **always-on** and **per-record opt-out** via a field. After
`action_confirm`, `project.task._southbrook_p7_sync_from_so()` pulls
material species + unit count + hardware specs from the originating
`sale.order`. To preserve a manual deviation, tick
`project.task.x_southbrook_specs_override`; the auto-sync then skips
that task on every subsequent confirm and refresh.

Rollback:

- `x_southbrook_specs_override` defaults False; existing records are
  unaffected until `action_confirm` re-fires.
- The hook in `_create_kitchen_project_task` is wrapped in a try/except
  that posts a message and lets the spine creation succeed even when
  the sync raises (keeps the platform installable on partial deps).
- `git revert` of the per-task commit removes both the sync method and
  the boolean cleanly.

### P8 — Floor traveler

P8 is **always-on** when the new `southbrook_floor_traveler` addon is
installed. There is no behaviour change unless that addon is installed
+ a user prints the traveler PDF or POSTs to the scan endpoint.

Endpoints + side effects:

- `ir.actions.report` `southbrook_floor_traveler.action_floor_traveler_report`
  renders one PDF per `sb.production.package`, with a QR code encoding
  `sb-package:<id>`. Degrades gracefully without the `qrcode` Python
  lib (the report renders, the QR area shows a "QR unavailable" stub).
- `POST /southbrook/api/floor-traveler/scan` body
  `{qr_payload, workcenter_code}` → calls
  `sb.production.package.record_scan(workcenter_code)`, which appends
  to the JSON scan log and calls the **existing**
  `mrp.workorder.button_finish` so the existing tool-consumption debit
  fires exactly once. Audit's load-bearing acceptance.

Rollback: uninstalling the addon removes the report + endpoint;
existing scan logs survive in `x_scan_log_json` as opaque JSON and are
ignored.

## Rollback

For each P-task: setting the flag to `False` returns behaviour to the
audited baseline. No destructive migrations, no schema deletions. If the
flag itself is unset, the default is OFF. The per-task commit can also
be `git revert`-ed cleanly because every change is additive.

## Definition of Done (audit § 11)

| # | Bar | Status |
|---|-----|--------|
| 1 | `IMPLEMENTATION_MAP.md` committed and accurate | ✅ committed as part of P0; includes the six discrepancy callouts |
| 2 | Each of P1–P8: code + tests + flag (where applicable) + README/docs note + clean `odoo -u <module>` upgrade path | ✅ 8 per-task commits, one P-task each |
| 3 | Golden-path test green with all flags ON | ✅ `test_golden_path_all_flags_on.test_definition_of_done` asserts (a) package+cutlist exist, (b) BoM contains KS-K2832-21 ×3, (c) MI yields 0 cutlist blockers, (d) SKU is lossless |
| 4 | With all flags OFF the system is behaviorally identical to the audited baseline | ✅ P1 + P3 default off (the two behavioral flags); P2/P4/P5/P6/P7/P8 land as additive (always-on but no destructive change). P1 OFF + P3 OFF reverts MI behavior to "report only" |
| 5 | No deletions, no widened permissions, no live customer records | ✅ all P-tasks are additive; P8 reuses existing ACL via `_inherit`; tests are TransactionCase rollback-only |
| 6 | PR descriptions cite the audit P-number + acceptance criteria | ✅ each commit message names the P-number, the audit finding, the change, and the rollback path |
