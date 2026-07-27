# Test Results — `southbrook_elearning_internal` v19.0.1.4.0

**Date:** 2026-07-10 · **Runtime:** Odoo 19.0 CE (local `v19c-odoo`), Postgres 16
**Method:** staged into container addons; isolated DB `el_ci`; prod untouched; cleaned up after.

## 1. Cold install — PASS
`odoo -d el_ci -i southbrook_elearning_internal` — module state `installed`;
DB shows 28 `slide_channel` + 198 `slide_slide` records. The full ~49K-line XML
loaded with no ParseError → v19 field compatibility confirmed (`slide_category`,
`html_content`, channel visibility/enroll fields all valid).

## 2. Content scan — PASS (no leaked credentials)
Scanned all 28 data files for `password`/`api_key`/`secret`/`token`/`sk-`/
`AQ.Ab`/`AIza`/internal IPs. No real secrets — hits were lesson code examples
(`api_key = self.env.company.vendorx_api_key`) or CDATA substrings. The one
genuine exposure was infrastructure recon (IPs/SSH/backup path) in the Sysadmin
course — an access-control issue, fixed below.

## 3. Upgrade + security fix verification — PASS
`odoo -u ...` applied the `course_sysadmin` visibility change cleanly. DB query:
```
Course 7 — Sysadmin -> visibility=members enroll=invite   ✓
```

## 4. Automated test — PASS (1/1)
```
southbrook_elearning_internal: 0 failed, 0 error(s) of 1 tests
```
`test_sysadmin_course_is_members_and_invite_only` — regression guard for S1.

## Overall: PASS
Install clean ✓ · no leaked secrets ✓ · sysadmin course locked to members/invite ✓ · 1/1 test green ✓.
