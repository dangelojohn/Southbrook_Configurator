# Code Review — `southbrook_hermes` ("Fabio")

**Module #32 of 46 · Odoo 19.0 CE**
**Version:** 19.0.4.7.2 → **19.0.5.0.0**
**Reviewed:** 2026-07-11
**Method:** 2 parallel audit agents (security; v19+correctness) → independent
source verification (incl. live probe of the failing tool path) → HEAD baseline →
minimal real fixes + test repairs → live `-i`+`-u`+tests on isolated DB (`ci_hermes`).

---

## What the module does

"Fabio" — a human-approved AI recommendation queue with **LLM tool-calling** into
Odoo. A stateless HS256 **JWT** (minted server-side per logged-in user, short TTL)
authenticates a sidecar; an HTTP **proxy** forwards to it; **read/write tools**
(870/194 LOC) let the LLM query and (behind a human gate) act on Odoo data.

---

## Verdict

Install/dispatch is **v19-clean**, and the core auth primitives are **sound**
(JWT alg-pinned, no SSRF, claim-bound tool args, read-tool IDOR checks, human-gated
apply). The real defects were a **HIGH sudo-write IDOR in a write tool** and
several **wrong cross-module field names** that 500'd the core `get_order_status`
tool. All fixed; **baseline 2 fail + 4 err → 0**.

---

## Findings

### Fixed — security

| # | Sev | Finding | Fix |
|---|-----|---------|-----|
| **S1** | **HIGH** | **`draft_customer_email` sudo-wrote to ANY `sale.order` with no ownership check.** It declared `scope="own_order"` but `sudo().browse(order_id)` with no `check_access` (every sibling write tool checks). An LLM — steerable via prompt-injection planted in an order thread Fabio reads — could post an attacker-controlled note onto **any** order in the DB. | Drop `sudo()`; run as the acting user and `check_access_rights/rule("write")` (mirrors `post_internal_note`). |
| **S7** | LOW | JWT `verify_jwt` pinned the algorithm (good, no alg-confusion) but didn't require `exp` — a forged token omitting expiry wouldn't be rejected as non-expiring. | Added `options={"require": ["exp"]}`. |

### Fixed — v19 correctness (were 500'ing the tool surface)

| # | Sev | Finding | Fix |
|---|-----|---------|-----|
| **V2** | **HIGH (runtime)** | `get_order_status` read `kj.southbrook_top_blocker` / `southbrook_next_best_action` / `southbrook_readiness_score` **unguarded** — wrong names (real: `top_blocker`/`next_best_action`/`readiness_score`, on `project.task` via `southbrook_project_mrp`, **not** a hermes dep) → `AttributeError`/500 once a kitchen job was linked. | Correct names + `getattr`-guard all (degrades to `None` when the module is absent). |
| **V3** | HIGH (runtime) | `_count_mos_for_order` searched `mrp.production.sale_order_line_id` — a field that exists nowhere on `mrp.production` → `ValueError`/500. | Use `sale_line_id` (sale_mrp's MO↔sale-line link, present in the stack). |
| **V5** | MEDIUM | Kitchen-project tools used `p.option_ids` (never resolves) instead of `p.design_option_ids` → silently returned 0 options / no selection. | Corrected to `design_option_ids`. |

### Documented (business-policy / infra / deprecation — not unilaterally changed)

| # | Sev | Finding | Recommendation |
|---|-----|---------|----------------|
| S2 | MEDIUM | No per-user/daily cost cap on the LLM path — only a global `sidecar_enabled` kill-switch. | Add a per-user/day cap (the campaign pattern; kill-switch already present). |
| S3 | MEDIUM | `main.py` `auto_apply` fast-path create-and-applies a `prospect` recommendation in one API call, bypassing the human-approval gate (limited to the "reversible" prospect type + `X-Api-Key`). | Rate-limit / config-gate the fast-path. |
| S4 | MEDIUM | SoD — same reviewer can approve then apply; `group_hermes_reviewer` can `write({'state':'approved'})` directly (though writing `applied` directly skips the side effects, limiting laundering value). | Second-approver + a `write()` state guard. |
| S5 | LOW/MED | `get_os_section` (sudo, `trade_partner` persona) fetches any `southbrook.os.section` by slug — a trade partner can read internal OS sections, not just `*_faq`. | Allowlist customer-safe slugs. |
| S6 | LOW | `conversation/log` sudo-creates rows with attacker-chosen `order_id`/`project_id` (partner_id is JWT-bound). Data pollution only. | Ownership-check the ids. |
| V1 | — | `check_access_rights`/`check_access_rule` used in ~10 places — **deprecated but functional shims** in this v19c build (empirically verified: the failing tool passed the check and failed later on a field). | Migrate to the unified `check_access(op)` for forward-compat. |
| V6 / misc | LOW | `read_group` deprecated (→ `_read_group`); `datetime.utcnow()` (3.12); JSON-schema `required` shape; `implied_ids` on `base.group_system` via `<record>` (may no-op — use `<function>`); manifest declares no `external_dependencies` for PyJWT (module degrades gracefully). | Migrate/clean as noted. |

---

## Strong positives (verified)

- **JWT verify pins `algorithms=[HS256]`** (no alg-confusion/`none`); secret is
  sudo-config-param sourced, placeholder-guarded, never logged; PyJWT uses
  constant-time compare.
- **No SSRF** — the proxy target is a fixed admin-set `sidecar_url`, not client-
  supplied; JWT forwarded only to that host; timeout set; stream closed on all paths.
- **Claim-bound tool args** — `persona`/`partner_id`/`tenant` are overwritten from
  verified JWT claims after body parse, so a hallucinated tool call can't
  self-attribute or self-elevate.
- **Read tools IDOR-safe** (browse → `check_access` → run as the partner's user, not
  sudo); **LLM write stays behind the human gate** (`propose_recommendation` only
  creates `state="draft"`; `action_apply` requires `approved`).
- **No XSS** (OWL `t-esc`), no SQL string-building, no `eval`; JWT is stateless (no
  token model to record-rule).
- **v19-clean install/dispatch**: routes `type="http"` + `csrf=False`, `<list>`,
  `models.Constraint`, all `@api.depends` resolve.

---

## Validation

- `-i` (fresh DB) — **clean install**, registry ~41 s.
- `-u` — clean.
- Tests `--test-tags=/southbrook_hermes` — **86/86 pass, 0 failed, 0 errors**
  (baseline: 2 fail + 4 err). See `TEST_RESULTS.md`.

### Env note
PyJWT is not preinstalled in the v19c test container (the module lazy-imports `jwt`
and degrades gracefully). Installed it (`pip install --break-system-packages PyJWT`,
2.13.0) so the 3 JWT-helper tests run — same pattern as `southbrook_dims`. The
module's manifest should declare `external_dependencies: {"python": ["jwt"]}`
(documented above).
