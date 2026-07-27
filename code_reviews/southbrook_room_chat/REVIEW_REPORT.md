# Code Review — `southbrook_room_chat`

**Module #26 of 46 · Odoo 19.0 CE**
**Version:** 19.0.2.2.1 → **19.0.2.3.0**
**Reviewed:** 2026-07-11
**Method:** 2 parallel audit agents (security+perf; v19+JS) → independent source
verification → minimal real fixes + regression tests → live `-i` + `-u` + tests on
isolated DB (`ci_room_chat`, full southbrook dep stack staged).

---

## What the module does

Conversational AI room-builder. `southbrook.room.chat.agent` runs a **native
Anthropic tool-calling loop** (Claude Sonnet 5) so a customer can describe their
kitchen in chat and have geometry built up one tool call at a time.
`southbrook.room.chat.session` (one per order) holds the JSON draft, transcript,
gathered customer profile, and the follow-up `crm.lead`. A single JSON-RPC route
(`/southbrook/api/order/<id>/room/chat`) fronts it; an OWL widget renders the chat.

**Critical safety invariant (verified):** tool calls mutate an **in-memory draft
dict only** (persisted as JSON) — this model NEVER creates `southbrook.room`/`.wall`/
`.constraint` records. Persistence always goes through the existing human-gated
"Set Up Your Room" wizard + `southbrook.room.validate_geometry`. The loop is bounded
(`_MAX_TOOL_ITERATIONS=12`, `_MAX_TRANSCRIPT_TURNS=20`, `_MAX_MESSAGE_CHARS=4000`).

---

## Verdict

Strong module — excellent tool-allowlist/validation, no XSS, key hygiene,
race-safe session, geometry never trusted. **Two HIGH issues fixed** (one a real
IDOR/gate-bypass, one the missing cost cap); four MEDIUMs are access-model /
infra / business-policy tradeoffs, documented for owner decision.

---

## Findings

### Fixed

| # | Sev | Finding | Fix |
|---|-----|---------|-----|
| **H2** | **HIGH** | **IDOR + rate-limit + spend bypass.** `handle_turn` was a **public** `@api.model` method that immediately `.sudo()`s the session and does `get_or_create_for_order(order_id)` with **no ownership check of its own** — the only ownership + rate-limit gates live in the controller. Public methods are `call_kw`-dispatchable, so any authenticated **portal** user could POST `call_kw(model="southbrook.room.chat.agent", method="handle_turn", args=[<victim_order_id>, …])` and: read another customer's draft/profile/transcript (all returned), mutate their session, plant a CRM lead, and drive paid Anthropic calls — **both gates bypassed**. | Renamed `handle_turn` → **`_handle_turn`** (leading underscore ⇒ **not** RPC-dispatchable). Its sole caller is the controller, which already enforces ownership (`_southbrook_resolve_order`) + rate limit. Controller updated to call `_handle_turn`. +2 regression tests (non-dispatchable; controller ownership rejection still passes). |
| **H1** | **HIGH** | **No global spend cap / kill-switch on the paid Anthropic path.** Only limiter was the per-worker in-memory `_RATE_BUCKETS` (60 turns/hr/user) — N workers ⇒ N×60, resets on deploy. Each turn fans out up to **12** Sonnet-5 calls, so the real multiplier is ~12×. The reused sibling (`southbrook_room_capture`) has a cross-worker daily cap; **this module reused the key but dropped the cap.** | Added a **global daily call cap + kill-switch**, counted **per real call** (bounds the 12× fan-out): `_consume_daily_quota()` gates every `_call_anthropic`. `ir.config_parameter southbrook_room_chat.max_daily_calls` (default **1000**); **0 = hard kill-switch**. Over-cap on the first call → `rate_limited`; mid-turn → stops gracefully, persists the partial draft. Mock backend never gated. +4 regression tests. |
| **F1** | LOW→v19 | Route + docstring used the deprecated `type="json"` alias (siblings all use `jsonrpc`). | → `type="jsonrpc"` (`controllers/main.py:9,92`). |

### Documented (access-model / infra / business-policy — not unilaterally changed)

| # | Sev | Finding | Recommendation |
|---|-----|---------|----------------|
| M1 | MEDIUM | **Lead/order can be pinned to a guessed existing partner.** `_save_followup_lead` resolves the partner from **chat-supplied** email via `_southbrook_resolve_customer(trusted=False)`. `trusted=False` correctly refuses to *mutate* a matched contact — but still **returns** it, then repoints the caller's order onto it (`session.py:200-204`, the `cur.id == self.env.user.partner_id.id` branch) and creates a `crm.lead` with `partner_id=victim` + attacker-controlled notes. Net: lead-phishing / order mis-attribution onto any partner whose email is guessed. Not account takeover (existing fields never overwritten; description is `plaintext2html`-escaped). | Only repoint/attach when the resolved partner was **newly created** or **is the acting user's own** commercial partner; otherwise keep the order on its current partner and create the lead unlinked. This is an identity-trust policy call (authenticated user vs typed email). |
| M2 | MEDIUM | **No per-user/day lead cap across orders.** `save_lead` is idempotent per session, but one session per order + no global lead cap ⇒ N draft orders → N leads (each optionally on a guessed partner via M1). The gateway sibling bounds this. | Add a per-user/day lead-creation cap (mirror `southbrook_agent_gateway`). |
| M3 | MEDIUM | **Synchronous upstream call can hold a worker up to ~12 min.** `httpx.post(timeout=60s)` runs inside the loop up to 12×/turn (`agent.py`), so worst case ~720 s of worker occupation → pool starvation. (H1's daily cap bounds *spend*, not *per-request wall-clock*.) | Offload to a job queue (OCA `queue_job`) / async, or add a per-turn wall-clock budget + lower `_TIMEOUT`/iteration cap. Same class as `southbrook_room_capture` R2 / `southbrook_ai_design` R2 (infra). |
| M4 | MEDIUM | **Every internal user reads all customers' gathered PII.** `ir.model.access.csv` grants `base.group_user` read on `southbrook.room.chat.session` (customer name/email/phone/address in `customer_json`, `transcript_json`) with no record rule scoping to owning team/salesperson. | Conscious decision: acceptable for sales staff, or add a record rule scoping to the order's team/salesperson. |
| R1 | — | The per-worker `_RATE_BUCKETS` still has no shared state (H1's cap bounds total spend, not cross-worker per-user fairness). | Back the limiter with a shared store (Redis / DB counter). Same as `southbrook_room_capture` R1. |

---

## Strong positives (verified against source)

- **Draft-only mutation, geometry never trusted/persisted** — human-gated wizard +
  `validate_current_draft` reuse `southbrook.room.validate_geometry`; tests assert
  zero `southbrook.room` side effects.
- **Tool allowlist + server-side validation** — `_TOOL_SPECS` allowlist,
  `unknown_tool` rejected, enum checks, `_coerce_int` + bounds checks, no
  mass-assignment (explicit kwargs, `**args` TypeError caught).
- **No XSS** — OWL template renders via `t-esc` only (no `t-raw`/innerHTML);
  `crm.lead.description` built with `plaintext2html`.
- **API key hygiene** — sudo-only via `_get_api_key`, `x-api-key` header (not URL),
  response body never logged (status only).
- **Email/phone** — `email_normalize`, phone validated; `trusted=False` resolver
  never mutates an existing contact.
- **Race-safe** `get_or_create_for_order` (savepoint + `UNIQUE(order_id)` +
  IntegrityError recovery); controller never raises (`upstream_error`).
- **v19 clean** — all cross-module fields/models/xmlids resolve (traced to source);
  `rpc`/mount/`t-inherit` correct; `models.Constraint` not `_sql_constraints`; no
  `name_get`/`check_access_rights`/`groups_id`; no correctness/return-shape bug in
  the tool loop or CRM path (the sibling-500 class was specifically checked — clean).

---

## Validation

- `-i southbrook_room_chat` (full dep stack) — **clean install**.
- `-u southbrook_room_chat` — **clean upgrade**, idempotent.
- Tests `--test-tags=southbrook_room_chat` — **47/47 pass, 0 failed, 0 errors**
  (incl. 5 new). See `TEST_RESULTS.md`.
