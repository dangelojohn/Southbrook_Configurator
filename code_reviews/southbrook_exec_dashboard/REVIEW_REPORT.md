# Code Review — `southbrook_exec_dashboard`

**Module #42 of 46 · Odoo 19.0 CE**
**Version:** 19.0.1.0.0 → **19.0.2.0.0**
**Reviewed:** 2026-07-11
**Method:** 2 parallel audit agents (security+KPI-math; v19+OWL-frontend) →
independent source verification incl. reading the controller + `southbrook.api.key`
schema → HEAD baseline → real fixes + regression test → live `-i`+`-u`+tests on
isolated DB (`ci_exec42`, full MI/kitchen/quality/finance/integrations dep stack).

## What the module does
A single-pane **executive morning briefing**: a controller (`/exec/morning`) serves a
KPI/tile JSON payload (yesterday's units, FPY, OTD, WIP, bottleneck, **30-day revenue,
cash position**) to an OWL client (`morning_briefing.js`) and mobile clients;
`exec_snapshot.py` computes 12 KPIs across mrp/sale/stock/account/quality/finance.

## Verdict
The backend/OWL path was correctly ACL-gated, but the **HTTP controller was an
unguarded twin** — `auth="public"` + any-session + a `.sudo()` compute handed company
**revenue/cash** to every logged-in user, **including portal customers** (CRITICAL,
same class as module 41's C1). The **OWL dashboard also rendered blank** (a removed v19
service) and **three tiles showed dead/zero data** (wrong NCR states + WIP field name).
Fixed **2 CRITICAL + 1 HIGH scope + 1 HIGH frontend + 3 MED + the baseline**. Baseline
**3/3 → 4/4** (+1 negative security regression test).

## Findings

### Fixed — security
| # | Sev | Finding | Fix |
|---|-----|---------|-----|
| **C1** | **CRITICAL** | **`/exec/morning` leaked all company financials to any logged-in user.** Route `auth="public"`, `_authenticate` returned any `session.uid` (a shop-floor operator, or a **portal dealer/customer** with a website session), and the payload was computed under `.sudo()` — so revenue/cash/margin went to anyone with a session. `.with_user(uid).sudo()` was misleading (sudo → superuser regardless of uid). The OWL/backend twin was correctly gated; this controller bypassed it. | Added an **executive-group + internal-user gate** (`has_group(...group_southbrook_exec_dashboard_user)` + `_is_internal()`) **before** the sudo compute → 403 otherwise. |
| **C2** | **CRITICAL** | **API-key auth branch was broken AND unscoped.** It did `ApiKey.search([("key","=",api_key)])` — but the key model has **no `key` field** (stored as `key_hash`), so it referenced a non-existent field (runtime error) and bypassed the timing-safe hash comparison; no scope/expiry/active check. | Use the model's `verify()` (hashes + indexed-equality); the C1 group gate now also covers the key path. |
| **H1** | **HIGH** | **NCR counts not company-scoped** — every other KPI filtered `company_id`, but the two NCR `search_count`s didn't → an exec of company A saw company B's critical-NCR count, and the FPY numerator (all companies) against a company-A denominator understated/zeroed FPY. | Added `("company_id","=",company_id)` (field-guarded) to both NCR domains. |

### Fixed — frontend / KPI correctness
| # | Sev | Finding | Fix |
|---|-----|---------|-----|
| **F1** | **HIGH** | **Dashboard rendered blank** — `useService("user")` was removed in v19; requesting it in `setup()` threw, so the OWL component never mounted (install succeeds, dashboard dead). | `import { user } from "@web/core/user"`; drop the service; `userName` → `user.name`. |
| **F2/F3** | MED | **"Critical NCRs Open" tile always 0.** The NCR `state` filter used `open/new/in_progress`, which don't exist on `southbrook.ncr` (`draft/quarantine/rework/scrap/released/cancelled`) — matched nothing; the OWL drill-through had the same dead states and no severity filter. | Use the non-terminal states `draft/quarantine/rework`; OWL drill-through fixed + `severity="critical"` added. |
| **F4** | MED | **WIP tile always $0** — the field-name guess tuple missed the real field `total_wip_value` on `southbrook.finance.wip_report`. | Added `total_wip_value` first in the tuple. |
| **M3** | MED | **Snapshot table grew unbounded** — the OWL client called `create({})` on every open/Refresh, inserting a fresh row each time. | Route the OWL path through `get_or_create_today` (5-min dedup window); made it return an int id for the RPC. |
| **L3** | LOW | **Cash could double-count** — two bank/cash journals sharing one `default_account_id` summed that account twice. | Dedupe account ids before summing. |

### Documented (business-policy / perf / minor — not changed)
| # | Sev | Finding | Note |
|---|-----|---------|------|
| M1 | MED | **Day-boundary KPIs mix tz-local dates with UTC-naive datetimes** — `context_today` (local) + `Datetime.to_datetime` (UTC midnight) shifts the "yesterday" window ~5h for Toronto, misattributing near-midnight MOs. | Build boundaries in the user tz then convert to UTC — a multi-window tz refactor left for careful implementation. |
| M2 | MED | **No rate limit + full recompute per call** (all KPIs `store=False`; `get_or_create_today` dedups only row creation, not the compute) → a caller can loop the endpoint to hammer the DB (raw-SQL cash aggregate). | Cache the payload on the row (JSON) within the 5-min window; add a throttle. |
| M4 | MED | **Revenue excludes credit notes** (`out_invoice` only, no `out_refund`) → returns overstate revenue. | Net vs gross is a CFO-definition call; label or subtract refunds. |
| L1/L2 | LOW | Takt compares MOs *finished* yesterday vs *scheduled* yesterday (disjoint sets → can exceed 100%); FPY/OTD default to 100% on an empty day ("empty = perfect"). | Business-policy. |
| F5/F6/F7/F8 | LOW | Missing `web_icon` file (broken app icon); bottleneck tile soft-deps `southbrook_mes_mps` (not in `depends` → "n/a" unless installed); a dead `action_exec_snapshot_list` (form-only, no menu); viewer group has `perm_create` (needed for `get_or_create_today`). | Cosmetic / soft-guarded. |

## Strong positives (verified)
- **SQL is parameterized** (`%s` bind tuple — no interpolation); **no eval/exec/safe_eval**. Error responses are generic (no stack leak).
- **Exec group correctly restrictive** (implies `base.group_user`, not the reverse); model ACL exec-only; the backend/OWL path *was* properly gated — only the controller wasn't (now fixed).
- **Most KPIs company-scoped** (the NCR gap was the exception). Div-by-zero guarded.
- **v19-clean** (v19 agent): controller `type="http"` (not the json trap); `@api.depends` valid; OWL imports from `@odoo/owl`, registers a real client action, `t-esc` (no `t-raw`); asset paths resolve; core field refs (mrp `date_finished`, account, stock) valid.

## Validation
- `-i` (fresh DB, full dep stack) — **clean**, registry ~64 s.
- `-u` — clean (2.2 s).
- Tests `--test-tags=/southbrook_exec_dashboard` — **4/4 pass** (3 baseline + 1 new
  negative: non-exec user → 403), from a baseline of 3/3. See `TEST_RESULTS.md`.
