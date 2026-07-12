# Code Review — `southbrook_mrp_kitchen_tools`

**Module #30 of 46 · Odoo 19.0 CE**
**Version:** 19.0.0.4.0 → **19.0.1.0.0**
**Reviewed:** 2026-07-11
**Method:** 2 parallel audit agents (security+perf; v19+data) → independent source
verification → HEAD baseline → minimal real fixes + regression tests → live `-i` +
`-u` + tests on isolated DB (`ci_kt`, full southbrook dep stack staged).

---

## What the module does

Manufacturing tool control: tool **assets** (checkout/return via QR scan),
**consumables** (usage → cost rollup onto MOs + tool-life tracking), tool **cribs**
(locations), **kits**, a 3-level tool **category** tree (162-record seed), and a
**work-order readiness gate** that blocks starting a WO without its required tools.

---

## Verdict

The install/data surface is **v19-clean** (the 1176-line seed installs fine;
baseline was **67/67 green**). But the audits found a **critical runtime crash** on
the core "Start work order" button, and **three HIGH integrity defects** in the
QR checkout + cost paths — all fixed, baseline kept green (now 74/74).

---

## Findings

### Fixed — v19 correctness (critical runtime)

| # | Sev | Finding | Fix |
|---|-----|---------|-----|
| V1 | **HIGH (runtime)** | **`button_start` override crashed the standard UI Start.** v19's base signature is `button_start(self, raise_on_invalid_state=False)` and the standard "Start" server action calls it **with `raise_on_invalid_state=True`**; the override took no kwarg → `TypeError` on every UI Start (and silently dropped the flag). Tests missed it because they call `button_start()` without the kwarg. | Accept and forward `raise_on_invalid_state`. |
| V2 | cosmetic | Dead `name_get` on `tool_category` (removed in v19, never called). | Removed. |

### Fixed — security / integrity

| # | Sev | Finding | Fix |
|---|-----|---------|-----|
| **H1** | **HIGH** | **QR checkout allowed the same tool to be checked out twice and never updated asset state.** The handler `sudo().create`d a usage row with no open-usage guard and never set `lifecycle_state`/holder — so a tool could be "checked out" to two WOs at once, and because `is_available` keys off `lifecycle_state`, the readiness gate still counted the physically-issued tool **available** (defeating the module's core promise). | Reject a checkout when an open usage exists; on checkout set `lifecycle_state="checked_out"` + `current_holder_id` (cleared on check-in). |
| **H2** | **HIGH** | **Checkout attributed the operator as OdooBot.** The usage row was created on a `sudo()` recordset, so `checked_out_by` (default `env.user`) resolved to the superuser — the audit trail ("who checked out WO #5421's tools?") recorded OdooBot for every scan, even though the controller resolves the real operator. | Set `checked_out_by` to the real acting user explicitly. |
| **H3** | **HIGH** | **Consumable cost + tool-life trusted a freely-writable `quantity`/`unit_cost` with no constraint.** A **negative** quantity flowed into `_apply_to_asset_life` as `remaining_life − quantity` (silently *un-wearing* a dull blade back over its threshold) and `total_usage + quantity` (decreasing usage), and produced a negative `total_cost` that reduced the MO cost rollup. `unit_cost` was never sourced from the product. | `@api.constrains` rejecting negative `quantity`/`unit_cost`; `create` sources `unit_cost` from the product's `standard_price` when unset (explicit values preserved). |
| **M2** | MEDIUM | **Readiness category match was one level deep** (`category \| category.child_ids`) despite a 3-level seed tree — assets filed under a **grandchild** category weren't counted, so a requirement keyed on a top-level category falsely reported **blocked** and `button_start` hard-refused the WO. | `("tool_category_id", "child_of", category.id)` (whole subtree). |

### Documented (business-policy / perf — not unilaterally changed)

| # | Sev | Finding | Recommendation |
|---|-----|---------|----------------|
| M1 | MEDIUM | `lifecycle_state` is freely writable with no state-machine guard / terminal-state block — an operator can move a `scrapped`/`retired` asset back to `available` via a raw `write`. Internal-users-only. | Context-flag-guarded transitions + terminal-state block (sibling pattern). |
| M3 | MEDIUM | **No `company_id` and no record rules** on any transactional model (`tool.asset`/`.crib`/`.kit`/`.usage`/`.consumption`). Fine single-company; a cross-company gap if multi-company is enabled. | Decide company-scoped vs shared; add `company_id` + record rules if scoped. |
| L1 | LOW | Batch "Check readiness" is O(WOs × requirements) `search_count`s (e.g. 50×4 = 200 queries). | Collapse to a single grouped `read_group`. |
| L2 | LOW | If the sequence yields the `"New"` fallback, two such assets collide on `UNIQUE(code)` (hard error, edge case). | Guard the fallback. |

---

## Strong positives (verified)

- **HMAC QR verification uses `hmac.compare_digest`** (constant-time); payload
  parser rejects unexpected keys; label route DoS-capped at 200 ids; public PIN
  route IP-rate-limited and never echoes the PIN.
- **No XSS** (all scan/label HTML escaped via `markupsafe`); no `t-raw`; no SQL
  string-building; no `eval`.
- **Consumption `unlink()` correctly reverses** the life/usage it applied
  (snapshot + clamp — the P8 rollback fix is sound).
- **v19-clean data**: 162-record seed with no `<function obj()>` trap, correct v19
  `ir.cron`/`ir.sequence` schema, `models.Constraint` throughout, all `@api.depends`
  resolve, all views `<list>`/valid xpaths, cross-module fields traced to source.
- Category recursion guarded (`_has_cycle`); `reusable`/`consumable` mutual
  exclusion constrained; cron well-formed (root user, bounded, conservative).

---

## Validation

- `-i southbrook_mrp_kitchen_tools` (fresh DB, incl. the 162-record seed) —
  **clean install**, registry ~39 s.
- `-u` — **clean upgrade**.
- Tests `--test-tags=/southbrook_mrp_kitchen_tools` — **74/74 pass, 0 failed, 0
  errors** (67 baseline + 7 new regression tests). See `TEST_RESULTS.md`.
