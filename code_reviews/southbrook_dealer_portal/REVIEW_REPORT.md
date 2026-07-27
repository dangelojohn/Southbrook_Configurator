# Code Review — `southbrook_dealer_portal`

**Module #34 of 46 · Odoo 19.0 CE**
**Version:** 19.0.0.1.0 → **19.0.1.0.0**
**Reviewed:** 2026-07-11
**Method:** 2 parallel audit agents (security; v19+correctness) → independent
source verification → HEAD baseline → real fixes + regression tests → live
`-i`+`-u`+tests on isolated DB (`ci_dportal`).

## What the module does
Dealer-channel portal (842 LOC): a dealer order list, a **KD (knock-down) JSON
export**, and an **installation-drawing PDF export** for production packages.

## Verdict
The channel gate (retail-vs-dealer) is implemented and tested, and the module is
**v19-clean** (installs/upgrades cleanly, no registry-breaking, all cross-module
fields traced to source). But **object-level authorization was entirely absent on
the two id-bearing export routes** — two **CRITICAL IDORs** letting any one dealer
download every other customer's production data. Fixed; **baseline 11 → 13 green**
(+2 IDOR regression tests).

## Findings

### Fixed — security (CRITICAL)
| # | Sev | Finding | Fix |
|---|-----|---------|-----|
| **C1** | **CRITICAL** | **KD-export IDOR.** `kd_export(pkg_id)` gated only the *channel* (`_require_dealer`), then `sudo().browse(pkg_id).export_kd_envelope()` with **no ownership check** (the code comment admits "*Phase 1 we accept any package the dealer can name*"). Any authenticated dealer could enumerate `pkg_id` and download the KD envelope — panel dims, substrate, grain, `mo_id`, hardware SKUs — of **every** other dealer's and retail customer's package. | Added `_fetch_owned_package` → `package._belongs_to_partner(user.partner_id)` (traces package → source order line, or MO's sale line → order → commercial partner); collapse to not-found for missing/not-owned. |
| **C2** | **CRITICAL** | **Installation-PDF IDOR** — identical pattern on `installation_pdf(pkg_id)` (leaks cut list, hardware schedule with SKUs/brands, pre-drilled hole coordinates for any package). | Same `_fetch_owned_package` gate. |
| **H2** | **HIGH** | The `sb.production.package` record rule had `domain_force=[]` (an **empty domain matches every record**), so any `base.group_portal` user had ORM read to **all** packages — the defense-in-depth layer that should have back-stopped C1/C2 was wide open. | Scoped the domain to the user's own orders (`sale_order_line_id`/`mo_id.sale_line_id` → `order_id.partner_id` == user's commercial partner). |
| **L1** | LOW | `Content-Disposition: filename="kd_{package.name}.json"` interpolated `package.name` unsanitized (a `"`/CR/LF breaks out of the filename / injects a header). | Sanitize the filename part (strip non-`[\w.\- ]`). |

### Verified NOT a bug
- **L2** (selection-label): the security agent worried `dict(field.selection)` could crash on callable selections; the v19 agent traced `panel_name`/`substrate`/`grain_dir` to **static** Selection lists (`PANEL_NAMES`/`SUBSTRATE_CHOICES`/`GRAIN_DIRECTIONS`) — the direct `dict(...)` calls are safe. No change.

### Documented (defense-in-depth — not changed)
- The `ir.model.access.csv` also grants `base.group_portal` read on `sb.cutlist` /
  `sb.cutlist_line` / `sb.hardware_package` / `sb.hardware_package_line` with no
  record rule → a portal user can still RPC-read those directly. The export path
  is now object-auth'd (controller), but these companion reads should be scoped
  (record rules via `mo_id`→SO→partner) or removed (the controller sudo-reads).

## Strong positives (verified)
- `dealer_orders` correctly scopes to `partner_id = user.partner_id` (no IDOR).
- All routes `auth="user"` (no public); exports are read-only GET; anonymous
  blocked (tested). Channel gate `_require_dealer` **fails closed**
  (`hasattr(...) else None`, strict `!= "dealer"`) — retail/tradesperson/kd
  rejected (tested).
- No `t-raw`/XSS; KD/PDF expose no explicit cost/margin (only a `pricing_pending`
  boolean); `_fetch_elevation_svgs` builds URLs from env vars (no SSRF).
- **v19-clean**: install/upgrade clean; the 458-line model has **zero** computes
  (no `@api.depends` registry risk); all cross-module fields (`cutlist_id`,
  `hardware_package_id`, `mo_id`, `res.partner.channel`, marathon/hardware `x_`
  related fields) traced to source; routes/exports use correct v19
  `make_response` headers.

## Validation
- `-i` (fresh DB) — clean install, registry ~43 s.
- `-u` — clean.
- Tests `--test-tags=/southbrook_dealer_portal` — **13/13 pass** (11 baseline + 2
  new IDOR regression tests). See `TEST_RESULTS.md`.
