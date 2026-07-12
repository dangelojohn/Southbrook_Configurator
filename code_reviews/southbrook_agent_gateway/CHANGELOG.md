# CHANGELOG — `southbrook_agent_gateway`

## 19.0.1.1.0 — 2026-07-11 — Code-review pass (Module #24)

### Fixed
- **[HIGH] `/quote-request` + `/quote` no longer 500 for every new customer.**
  `_find_or_create_partner`'s create-new-partner branch returned a bare recordset
  while `submit()` unpacks `(partner, is_new)` — so creating a new partner (the
  common case) raised `ValueError: not enough values to unpack`. Now returns
  `(new_partner, True)`. (Pre-existing bug; caught by live validation — the module's
  core lead-capture was broken.) `models/southbrook_agent_inquiry.py`.

### Security
- **[CRITICAL → mitigated] Anti-abuse brakes on the anonymous verify-email path.**
  The public POST emailed a Southbrook-branded verify link to a caller-chosen
  address (reflected-phishing / email-bomb relay). Added a global daily send
  ceiling (`southbrook_agent_gateway.max_daily_verify_emails`, default 200; 0 =
  kill-switch) + a per-recipient cooldown
  (`southbrook_agent_gateway.verify_email_cooldown_hours`, default 24).
  `models/southbrook_agent_inquiry.py`.

### Tests
- Added `test_verify_email_killswitch_and_cooldown`. **35/35 green** (was 2 failed /
  8 errors — all the B1 unpack crash).

### Notes (documented, not changed)
- Spoofable/per-worker IP rate-limiter (H1); pre-verification CRM pollution (H2);
  no API-key/CAPTCHA on anonymous write routes (C1 full); token TTL, openapi
  cache-control, pre-read body cap (L1/L2/L3). Input handling is otherwise
  excellent (strong tokens, email_normalize, no mass-assignment, server-side
  pricing, IDOR-closed, no XSS) — verified.
