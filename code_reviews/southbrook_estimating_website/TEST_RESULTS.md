# Test Results — `southbrook_estimating_website` (Module #18)

**Harness:** v19c-odoo, isolated DB, staged with the full dep chain
(southbrook_estimating, southbrook_qr_kit, southbrook_kitchen_3d_configurator —
the last carrying the Module-16 groups.xml install fix) over the 4 OCA modules.

## Install / upgrade
- Fresh install (`-i`): ✅ SUCCESS (no obj() trap; only data eval is `eval="False"`).
- Upgrade (`-u`): ✅ SUCCESS.

## Unit tests — CLEAN (baseline-verified)
- **Unmodified HEAD baseline:** 1 failed / 1 error / 85 tests.
- **After this pass:** 1 failed / 1 error / **86** — the +1 is the new
  `test_portal_user_cannot_send_to_manufacturing`, which **passes**.
- **Net: zero regressions** (install + upgrade identical).

### New regression test (passes)
`test_portal_user_cannot_send_to_manufacturing` — a portal (share=True) user firing
`send_to_manufacturing` on an order `_southbrook_resolve_order` grants them gets
`{"error":"forbidden"}`. Fails on pre-fix code.

## The 2 failures are PRE-EXISTING + cross-module (confirmed on HEAD)
- `test_bom_payload_per_line.test_panel_count_positive_for_seeded_line` — panel
  count is 0 without the `southbrook_dims` external panel-cut module.
- `test_design_3d_tab.TestDesign3dTab` setUpClass — needs a downstream-stack fixture.
Both pass in the deployed full stack; not caused by these changes.

## Audit cross-checks
- v19+JS: no install/web-client breakage; JS uses public_components registry; only
  `type="json"` (fixed).
- Security: only 2 auth=public routes (both safe); pricing server-side (money vector
  closed); IDOR closed (ownership guards); no XSS/eval. The portal→manufacturing
  escalation (H1, fixed) + PII backfill (M1, fixed) were the findings.

## Conclusion
Largest module in the suite; security posture materially improved (portal→
manufacturing escalation + PII backfill closed) with a passing regression test and
zero regressions. Bounded items (variant-rule bypass, docs DoS, N+1) documented.
