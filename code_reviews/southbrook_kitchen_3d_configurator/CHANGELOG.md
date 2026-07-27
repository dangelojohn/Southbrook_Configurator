# CHANGELOG — `southbrook_kitchen_3d_configurator`

## 19.0.5.7.0 — 2026-07-11 — Code-review pass (Module #16)

### Fixed
- **[CRITICAL] Module now installs on Odoo 19 CE.** `security/groups.xml`'s
  user-sweep used `obj()` inside a `<value>` child of `<function>`, where v19
  does not inject `obj` → `NameError` → registry load failure. Moved the sweep
  into `models/res_groups.py::_southbrook_kitchen_sweep_managers` (real
  `self.env`); the data file calls it argument-free. `security/groups.xml`,
  `models/res_groups.py` (new), `models/__init__.py`.
- **[HIGH] `save_design` no longer trusts a client-supplied price.** Each line is
  repriced server-side from the resolved channel pricelist (`_channel_price`);
  the client `item["price"]` — which flowed verbatim into the quotation — is
  never persisted. `controllers/main.py`.
- **[HIGH] `action_create_quotation` no longer crashes without southbrook_mrp_pm.**
  Guarded the `force_production_release` write (`"force_production_release" in
  order._fields`) — that field is defined in the Tier-5 mrp_pm module this Tier-3
  module can't hard-depend on. `models/kitchen_design.py`.
- **[MEDIUM] `save_design` IDOR hardening.** Added `exists()` + `check_access("write")`
  (graceful degrade, mirroring save_position/delete_line) and persist the
  ACL-validated partner instead of the raw client `partner_id`. `controllers/main.py`.
- **[MEDIUM] `save_design` N+1.** Batched the per-item catalog lookup into one
  ACL-respecting `search`. `controllers/main.py`.
- **[MEDIUM] Indexed** `kitchen.design.sale_order_id` and `partner_id`.
  `models/kitchen_design.py`.
- **[MEDIUM/v19] `type="json"` → `type="jsonrpc"`** on all 7 routes (deprecated
  alias). `controllers/main.py`.

### Tests
- Added `test_07_client_price_is_ignored_server_reprices` (HIGH-1 money-vector).
- Result: **28/28 green** (install + upgrade) — module previously did not install.

### Notes (documented, not changed)
- The `group_kitchen_manager` sweep (kept, now v19-valid) nullifies per-designer
  isolation — retiring it is a business-policy decision (D1).
- Catalog `qty_available`/per-product pricelist N-scaling (D2); `zone`
  default-masks-compute (D3); cron/mrp sudo hygiene (D4).
