# Southbrook Floor Traveler

Audit P8: per-`sb.production.package` PDF traveler with a QR code,
workcenter scan endpoint, and scan-driven tool-consumption telemetry —
without duplicating the existing `mrp.workorder.button_finish` debit.

## Pieces

1. **QWeb PDF report** `southbrook_floor_traveler.action_floor_traveler_report`
   (`ir.actions.report`, model `sb.production.package`). One page per
   package with header + cutlist table + QR panel. The QR encodes
   `sb-package:<id>` so external scanners are stable against ID
   schemes.

2. **Model extension** on `sb.production.package` adds:
   - `x_scan_log_json` (Text, default `"[]"`) — append-only scan log.
   - `qr_payload` (compute) — stable `sb-package:<id>` string.
   - `qr_image_base64` (compute) — base64 PNG. **Soft-deps on the
     `qrcode` Python lib** — without it the field is empty and the
     QWeb template shows a "QR unavailable" placeholder so the report
     still renders.
   - `record_scan(workcenter_code)` — appends a scan event AND calls
     `mrp.workorder.button_finish` on the next in-flight WO. Reuses
     the existing debit path so the audit's "no duplicate telemetry"
     bar holds.

3. **HTTP endpoint** `POST /southbrook/api/floor-traveler/scan`
   `{qr_payload, workcenter_code}` → calls `record_scan(...)`.

## No new permissions

The addon extends an existing model (`sb.production.package`) via
`_inherit`; existing ACLs apply. No `ir.model.access.csv` is shipped.
This is by design — the audit's hard rule §0.2 bars widening
permissions.

## Tests

```
test_p8_floor_traveler:
  - QR payload encodes the package id.
  - record_scan without a WO is a graceful no-op + log entry.
  - 3 sequential scans -> 3 log entries (no duplicate-telemetry).
  - With a real WO in 'progress', record_scan calls
    mrp.workorder.button_finish exactly once (mock spy).
  - The traveler PDF report renders and contains the QR payload.
```

## Rollback

Uninstall the addon. The `x_scan_log_json` column on
`sb.production.package` survives as an opaque JSON column but is
unused; remove it with a follow-up migration if you also want the
schema reverted.
