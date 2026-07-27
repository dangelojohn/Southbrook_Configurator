# Code Review — `southbrook_command_center`

**Module #46 of 46 (APEX) · Odoo 19.0 CE · 2197 LOC**
**Version:** 19.0.1.1.1 → **19.0.2.0.0**
**Reviewed:** 2026-07-11
**Method:** 2 parallel audit agents (security+bus; v19+OWL+cross-module) → independent
source verification incl. the scoring library's sudo path + bus channel model + adversarial
call_kw reachability → HEAD baseline → real fixes + regression tests → live `-i`+`-u`+tests
on isolated DB (`ci_cmd46`, the full ~15-module southbrook dep chain — the whole platform).

## What the module does
The apex aggregation node: a `/command_center/bootstrap` controller serving 5 dashboard
panels (factory health / production flow / exception queue / Hermes recs / alert stream),
a read-time scoring **AbstractModel** (`southbrook.command.center` — zero stored fields,
**zero `@api.depends` across foreign models**), one new `southbrook.command.exception`
model (accountable exception queue), and a bus.bus live-update layer.

## Verdict
An **impressively defensive apex**: v19-clean (v19 agent — the "zero foreign `@api.depends`"
claim verified true by AbstractModel design, every cross-module field across ~15 modules
verified to exist, OWL/bus API correct), every panel read runs **as the calling user inside
try/except** (so the model ACL is the real gate and non-members degrade to empty), **no
eval/SQL**, and — adversarially confirmed — **margin/PO-risk are NOT exposed** (test-only
callers). The gaps were **authorization-hardening**: client-trusted `company_id`, no route
group gate, no company `ir.rule`, and a latent bus cleartext leak. Fixed **2 HIGH + 1 latent
HIGH + 2 LOW**; baseline **19/19 → 21/21** (+2 gate regression tests). Campaign complete.

## Findings

### Fixed — security
| # | Sev | Finding | Fix |
|---|-----|---------|-----|
| **S1** | **HIGH** | **Client-trusted `company_id` + no `ir.rule`.** `cid = int(company_id)` was taken verbatim (never checked against the user's companies), the exception model had **no company record rule**, and `_flow`/`_recommendations`/`_alerts` ignored company entirely — so a Central Command user (multi-company) could read another company's exception queue + flow/alerts. | Server-side `_validated_company_id` clamps `cid` to `env.user.company_ids`; added company domains to `_flow`/`_recommendations`/`_alerts` (field-guarded); added a **global multi-company `ir.rule`** on `southbrook.command.exception` (so direct call_kw is scoped too). |
| **S3** | MED-HIGH | **No route group gate.** Both routes are `auth="user"` (any session incl. portal); `_factory_health`/`_flow` were served to non-Central-Command internal users, and `factory_health_score()` reaches `exec_dashboard.snapshot.get_or_create_today()` — **a write** from a nominally read endpoint. | `_require_cc_member` (internal + membership in any of the 6 command-center groups) → `AccessError` on both `bootstrap` and `help_lookup` (the latter also closes the training-catalogue enumeration to portal). |
| **S2** | HIGH (latent) | **Bus alerts leaked `impact_summary` cleartext.** The live layer publishes to guessable, **unauthenticated** company string channels (`sb_cc_alerts_<cid>`) — Odoo doesn't per-user-authorize arbitrary string channels — and the alerts payload carried the breakdown description in cleartext. (Latent: delivery isn't wired until the Caddy `/websocket` split.) | Dropped `impact_summary` from the bus payload — the client re-fetches the summary by `res_id` through the ACL-checked ORM (the bus handler already re-authorizes on read). |

### Fixed — v19 (LOW)
| # | Sev | Finding | Fix |
|---|-----|---------|-----|
| V1 | LOW | Bus lifecycle listeners used `"connect"/"disconnect"/"reconnect"`; v19 emits `"BUS:CONNECT"/…`. The "live" badge wouldn't flip on a socket drop + no auto-resync on reconnect (latent). | Use the `BUS:` prefixes. |
| V2 | LOW | `type="json"` on both routes (a working v19 alias that warns). | `type="jsonrpc"`. |

### Documented (design / policy / latent — not changed)
| # | Note |
|---|------|
| **Bus re-scoping** | The durable fix for S2 is publishing to the owner's **user/partner record channel** (which Odoo *does* authorize) rather than guessable company string channels — a design change for the Phase-3 websocket rollout. |
| role param | `role` is client-supplied and only *narrows* the view (all command-center groups read the whole model), so it's a **presentation hint, not an authorization boundary** — derive server-side if role separation is ever required. |
| exception SoD | `group_command_center_user` has model-wide write/create (no owner `ir.rule`) → can acknowledge/resolve/spoof any exception. The **five role groups are read-only** (mitigating). Add an owner `ir.rule` if SoD matters. |
| misc | `bottleneck_line_ids` doesn't exist on the report → the Bottleneck sub-panel always renders empty (guarded); `priority` Selection sorts by stored key; 3 scoring methods (`schedule_confidence`/`job_margin`/`po_delivery_risk`) are dormant (test-only callers). |

## Strong positives (verified)
- **Zero foreign `@api.depends`** (AbstractModel scoring — the apex registry-break trap is absent by construction); **every** cross-module field/method across ~15 modules verified to exist in v19.
- Every panel read runs **as the caller in try/except** → ACL is the effective gate; **margin/PO-risk not exposed** (adversarially confirmed — the scoring methods need a recordset arg, unreachable via call_kw). No eval/SQL/injection; sudo bounded to config-params/system-materializer/bus.
- Kill-switch (`hooks_enabled` ships `0`) on all write hooks; `super()`-first + try/except on every override; idempotent upsert; bus client re-fetches through the ACL-checked ORM.
- **v19-clean**: correct `ir.cron` schema, `models.Constraint`, `@api.model_create_multi`, OWL imports (`rpc`/`user` from the new modules), correct bus API, migration post-schema.

## Validation
- `-i` (fresh DB, full ~15-module platform dep chain) — **clean**, registry ~80 s.
- `-u` — clean.
- Tests — **21/21 pass** (19 baseline + 2 new HttpCase gate regressions:
  non-member → error envelope, member → result). See `TEST_RESULTS.md`.
