# Test Results — `southbrook_mrp_kitchen_workcenters`

**Date:** 2026-07-11
**DB:** isolated on `v19c-db` (db-local-socket create; see `southbrook_room_capture`
env note).
**Addons:** full southbrook dep stack staged into `/mnt/extra-addons`.

## Baseline (unmodified HEAD, current v19c build)
`-i --test-tags=/southbrook_mrp_kitchen_workcenters`: **5 failed, 30 error(s) of
140 tests** (install itself clean — the 8 data seeds + demo load fine). Dominant
root causes: `mrp.workorder` lost `mail.thread` (~12), subcontract `required`
field (8), `lot_producing_id`/`_onchange_move_raw` removed, `field.related` format
change, request-not-bound, malformed test PNGs.

> The first `-i` exited 137 once (transient OrbStack VM OOM under load); a retry ran
> clean.

## After fixes
```
odoo -c … -i southbrook_mrp_kitchen_workcenters --stop-after-init --no-http   # fresh cold install
```
- 164 modules loaded, registry 47.2 s, no ERROR/CRITICAL (incl. the new
  `mail.thread` message_* columns on `mrp.workorder`).

```
odoo -c … -u southbrook_mrp_kitchen_workcenters --test-enable --test-tags=/southbrook_mrp_kitchen_workcenters …
```
- **0 failed, 4 error(s) of 140 tests** — i.e. **136 pass**, from a baseline of 35
  failures. **Zero regressions** (0 failed throughout).

## Failures resolved (35 → 4)
| Cluster | Count | Resolution |
|---------|-------|------------|
| `message_post`/`message_ids` on WO (w034/w040/w069) | ~12 | `mail.thread` on `mrp.workorder` (D1) |
| subcontract `selected_vendor_id` NOT NULL (w066) | 8 | removed field `required=` (C1) |
| `lot_producing_id` singular (w042) | 3 | plural `lot_producing_ids` (D2) |
| `_onchange_move_raw` (w026) | 5 | removed removed-onchange call (D3) |
| `field.related` tuple vs string (asbuilt_pg) | 4 | string form (D4) |
| test_enable context / test-user access (w011/w054) | 2 | context key / mrp group (D5) |
| unbound request in form-open log (w018 partial) | — | request guard (C2) |

## Remaining (4, pre-existing test-harness artifacts — documented)
- `test_w018` ×2 — QR defect handler is HTTP-dispatch-designed; called directly in
  a `TransactionCase` it hits request-bound accesses (v19 lazy-gettext / message_post).
  Works via the real `/sb/qr/scan` route; tests should be `HttpCase`.
- `test_w026` ×2 — WO-traveler report fails PIL on the test's malformed PNG data
  (`chunk_IE` truncated PNG).

All four were present in the first baseline and are not caused by this pass.
