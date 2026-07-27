# Changelog — `southbrook_dealer_portal`

## 19.0.1.0.0 — 2026-07-11 (code-review pass, module #34)

### Security — Fixed
- **C1/C2 (CRITICAL) — export IDOR.** The KD-export and installation-PDF routes now
  authorize the package object, not just the dealer channel: a new
  `_fetch_owned_package` helper requires `package._belongs_to_partner(
  request.env.user.partner_id)` (the package must trace, via its source order line
  or its MO's sale line, to one of the acting dealer's own sale orders), collapsing
  missing/not-owned to the same not-found response. Previously any dealer could
  enumerate `pkg_id` and download every other customer's KD envelope / installation
  PDF.
- **H2 (HIGH) — record rule.** `rule_portal_dealer_production_package` `domain_force`
  changed from `[]` (matched every record) to an own-orders domain.
- **L1 (LOW)** — `Content-Disposition` filename now sanitized via
  `_safe_filename_part` (was raw `package.name`).

### Tests (+2 regression)
- `test_dealer_cannot_export_another_partners_package` (C1/C2 negative),
  `test_dealer_can_export_own_package` (positive).

### Not changed (documented in REVIEW_REPORT.md)
- Companion `base.group_portal` read ACL on `sb.cutlist`/`sb.hardware_package`
  (+lines) should also be record-rule-scoped or removed (defense-in-depth).
