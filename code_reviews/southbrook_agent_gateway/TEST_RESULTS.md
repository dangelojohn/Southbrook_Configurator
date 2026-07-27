# Test Results — `southbrook_agent_gateway` (Module #24)

**Harness:** v19c-odoo, isolated DB, staged with southbrook_estimating + southbrook_qr_kit
over the OCA modules.

## Install / upgrade
- Fresh install (`-i`): ✅ SUCCESS. v19-CLEAN (no obj() trap; post_init_hook(env)
  correct + idempotent; all data files + phone_validation E.164 valid).
- Upgrade (`-u`): ✅ SUCCESS.

## Unit tests
`--test-enable --test-tags southbrook_agent_gateway` → ✅ **0 failed / 0 error / 35 tests**
(install + upgrade).

### The validation caught a real HIGH bug (both audit agents missed it)
- First run: **2 failed / 8 error(s) / 35** — ALL 10 traced to one root cause:
  `submit()` → `_find_or_create_partner(cleaned)` raised
  `ValueError: not enough values to unpack (expected 2, got 1)`. The create-new
  branch returned a bare recordset. This 500'd `/quote-request` + `/quote` for
  every new customer — the module's core function.
- After returning `(new_partner, True)`: **0 failed / 0 error / 35**.

### New regression test (passes)
- `test_verify_email_killswitch_and_cooldown` — asserts the daily-cap kill-switch
  (cap=0 → email suppressed) and the per-recipient cooldown (same address within
  the window → suppressed).

## Audit cross-checks
- v19: **install-CLEAN**, no registry issues. Security: input handling excellent
  (strong tokens, email_normalize, control-char strip, cleaned-payload, server-side
  pricing, IDOR-closed, no XSS, PII ACL) — the anti-abuse relay (C1) was the finding.

## Conclusion
A well-hardened public gateway whose one broken core path (500 on every new
customer) is fixed — a bug only live validation surfaced — plus a self-contained
anti-abuse brake on the email relay. Install + upgrade clean, full suite green. The
deeper anti-abuse hardening (API key / defer-CRM / CF-only ingress) is documented.
