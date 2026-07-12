# CHANGELOG — southbrook_training_hub

## 19.0.2.0.0 — 2026-07-11 (code-review campaign, module #45)

### Fixed — security
- **Hermes role-gate identity (S1, MED).** `tools/find_training.py` — dropped the
  `.sudo()` so `search_for_user`'s `role_group_ids` gate binds to the real persona
  (the Hermes dispatch passes a persona-bound `env`); under sudo it resolved against
  the superuser and matched every item, exposing internal-role-gated training to a
  trade_partner persona.
- **Internal-only HTTP routes (S2, LOW-MED).** `controllers/training.py` — both
  `/training/recommended` and `/training/search` now require `_is_internal()` (403
  otherwise). The routes sudo the catalogue read (model ACL bypassed), so a portal
  user could otherwise page every un-gated (fail-open default) item incl. internal
  runbooks; the trade-partner path is the Hermes tool, not these routes.
- **URL scheme constraint (S3, LOW).** `models/training_item.py` — `@api.constrains`
  requires `url` to be `http(s)://` or a leading-slash path (no `javascript:`).

### Fixed — v19
- **`name_get` → `_compute_display_name` (V1).** `models/training_tag.py` — v19 no
  longer calls `name_get`; the `[Kind] Name` tag label was silently dead.

### Not changed (documented in REVIEW_REPORT.md)
- V2 `ir.ui.menu` computed-m2m relation-table-name collision (inert; store=False);
  V3 unused menu-scoped search path.

### Manifest
- Version `19.0.1.3.0` → `19.0.2.0.0`.
