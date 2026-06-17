# Southbrook OS + Hermes Platform — Design

**Status:** brainstorm-validated · 2026-06-16
**Authors:** John D'Angelo + Claude Code (brainstorm session)
**Supersedes (extends):** `2026-06-16-hermes-agent-design.md` (the Fabio v0 sidecar pattern, already shipped)
**Relates to:** `docs/CUSTOMER_TO_MANUFACTURING_FLOW.md`, `CLAUDE.md` (estimating brief),
`addons/southbrook_premium_orchestration/docs/DESIGN_SPEC.md`

---

## 0 · Mission

Build a formal, governed, multi-consumer **Southbrook Operating System** as a
first-class layer of the platform — and surface it through **Hermes**, a
persona-aware AI agent that grounds itself in the OS plus live Odoo state. The
OS is the product (Southbrook's self-knowledge as a structured artifact);
Hermes is the interface (a chat that translates the OS into answers and
human-approved actions for trade partners, sales reps, and manufacturing
managers).

The architecture is built to scale from the single Southbrook tenant to a
fleet of tenants on the same QNAP (Porterly, Tribancs, Sapienzium, etc.), each
with their own OS + Hermes, all overseen by a future **Overseer Hermes**
control plane.

---

## 1 · Decisions captured during brainstorm

The six gating decisions, with the option picked and a short rationale.

| # | Question | Pick | Why |
|---|---|---|---|
| 1 | Primary persona | **D — all three (trade partner / sales rep / mfg manager), persona-aware single agent** | One Hermes routes by persona via `res.users.share` + group; avoids two competing products. |
| 2 | Surface | **B — persona-native surfaces, API-first contract underneath** | Trade-partner chat embedded in Order Builder; sales-rep side-panel in backend; Kitchen Ops widget. Three deliberate surfaces, one `/hermes/v1/ask`. |
| 3 | Read/write boundary | **B — tiered T0/T1/T2 with persona-gated unlocks** | T0 logging + T1 communication are direct writes; every T2 (business mutation) flows through the existing Fabio v0 `southbrook.hermes.recommendation` draft → approve → apply path. |
| 4 | Grounding strategy | **C — hybrid RAG + tools** | Static OS knowledge in RAG, live Odoo state through tool calls. Tools are the natural persona-ACL boundary. |
| 5 | MVP sequencing | **A — trade partner first, full depth** | The original "where is my kitchen?" example is a trade-partner answer; portal record rules already do per-partner data scoping for free. |
| 6 | LLM runtime | **E2 — Vercel AI Gateway, OpenAI primary, Gemini + free models routable** | User has OpenAI account in hand. Gateway lets cheap/long-context workloads route to Gemini without coupling Hermes code to a provider. |

Plus, after design § 1, three multi-tenant follow-ups:
- Overseer: **chat + dashboard** surface
- Overseer scope: **ops-only** (never tenant business data without explicit opt-in elevation)
- Overseer timing: **v1.x** (after Southbrook tenant Hermes is live)

---

## 2 · Architecture

Two new addons + one new Vercel project. The Fabio v0 `southbrook_hermes`
addon (already deployed 2026-06-16) is extended, not replaced. `southbrook_os`
is new and depended on by `southbrook_hermes`. Per-tenant from day one even
though Southbrook is the only tenant in v1.0.

### 2.1 The OS layer (`southbrook_os`, NEW addon)

```
addons/southbrook_os/
├── __manifest__.py                          v19.0.1.0.0, depends: base, mail, southbrook_estimating
├── canonical/                               ← hand-curated narrative (markdown)
│   ├── 00_charter.md                        mission, customer model, one-paragraph identity
│   ├── 01_company.md                        trade-partner-only model, three customer types
│   ├── 02_catalog.md                        cabinet families, SKU prefix taxonomy
│   ├── 03_attributes.md                     16 attributes, series definitions, restriction rules
│   ├── 04_lifecycle.md                      Draft → Estimating → Approval → Confirmed → In Prod → Install
│   ├── 05_production.md                     15-step routing, work centers, bottleneck taxonomy
│   ├── 06_plm.md                            ECO types, cut spec, ProductGraph relationship
│   ├── 07_partner_faq.md                    20 most common partner questions + canonical answers
│   ├── 20_systems_topology.md               for Overseer + ops persona — QNAP stack, tunnels, Caddy
│   └── 99_glossary.md                       authoritative term definitions
├── generated/                               ← regenerated from Odoo on cron + ECO apply
│   ├── 02_catalog.generated.md              from product.template
│   ├── 03_attributes.generated.md           from product.attribute + product.config.line rules
│   ├── 06_cut_spec.generated.md             from active southbrook.cut.spec
│   └── 08_work_centers.generated.md         from mrp.workcenter + OEE telemetry
├── models/
│   ├── os_section.py                        southbrook.os.section — slug, version, source, body, last_updated
│   ├── os_revision_order.py                 southbrook.os.revision — OSRO; mirrors ECO stage pipeline
│   └── os_publication.py                    snapshot of OS at a version; pinnable from sale.order
├── controllers/
│   └── os_public.py                         /southbrook/os, /southbrook/os.json, /southbrook/os.pdf
├── exports/
│   ├── rag_corpus_export.py                 builds the LLM grounding bundle for the Hermes sidecar
│   └── schema_export.py                     JSON ontology of concepts: Cabinet, Order, Job, ECO, Tool…
├── data/
│   ├── ir_cron.xml                          nightly regenerate of generated/ + index rebuild trigger
│   └── os_section_seed.xml                  seed records pointing at canonical/ files
└── tests/
    ├── test_os_coverage.py                  asserts every Hermes tool has OS-section coverage
    └── test_generators_match_canonical.py   asserts no contradiction between canonical and generated
```

**The canonical/generated split is the load-bearing idea.** Hand-written narrative
stays under `canonical/` and is never overwritten by code. Anything that mirrors
live Odoo state (catalog, attribute matrix, cut spec values, work-center status)
lives under `generated/` and is rebuilt by `ir_cron`. The Hermes RAG indexer
treats both as input; downstream consumers (public viewer, Overseer, agents)
treat them as one published OS.

### 2.2 The agent layer (`southbrook_hermes`, EXISTING — extend)

Fabio v0 already deployed today gives us:
- `southbrook.hermes.question` (conversation log)
- `southbrook.hermes.recommendation` (draft/approve/apply pipeline)
- Backend `Fabio > Ask` menu + portal `/my/fabio` route
- `southbrook_api` sidecar boundary (manifest summary)

v1.0 adds (inside `southbrook_hermes`):
- `tools/` package — Python functions decorated with `@hermes_tool(personas=[...], tier="T0|T1|T2", scope=...)`. ~12 tools for v1.0 trade-partner persona.
- `controllers/hermes_proxy.py` — Odoo controller that mints short-lived JWTs and forwards to the Vercel sidecar.
- `controllers/hermes_tools.py` — Odoo controller that exposes the tool registry and individual tool dispatchers; called BACK by the sidecar with the same JWT.
- `static/src/owl/hermes_chat/` — OWL component bundled into the Order Builder asset bundle. Persona-aware (chat panel for trade partner).
- Bumps `__manifest__.py` depends to add `southbrook_os` (mandatory) — Hermes cannot run without an OS to ground in.

### 2.3 The sidecar (Vercel project, NEW)

Stateless inference. One Vercel project, namespaced internally by tenant.

```
hermes-sidecar/                              repo: dangelojohn/hermes-sidecar (or sibling of southbrook-v19cr)
├── app/api/hermes/
│   ├── ask/route.ts                         POST /api/hermes/ask — receives JWT, returns SSE stream
│   ├── tools/route.ts                       GET /api/hermes/tools — pulls the tool registry from a tenant Odoo
│   └── conversation/log/route.ts            POST /api/hermes/conversation/log — persists Q+A back to Odoo
├── lib/
│   ├── jwt.ts                               verify tenant-scoped JWT; extract { tenant, persona, partner_id, tier }
│   ├── rag.ts                               in-memory vector retrieval over /data/index/<tenant>/index.json
│   ├── tools.ts                             call tenant Odoo /api/hermes/tools/<name> with the same JWT
│   └── prompts.ts                           system + persona-voice + RAG-injection prompt assembly
├── data/
│   ├── grounding/<tenant>/                  ← populated by southbrook_os.exports.rag_corpus_export.py
│   │   ├── canonical/*.md
│   │   └── generated/*.md
│   └── index/<tenant>/index.json            ← vector embeddings, built at deploy time
├── scripts/
│   └── build-rag.ts                         pnpm build:rag <tenant> — pulls fresh grounding from a tenant Odoo,
│                                            embeds with text-embedding-3-small, writes index.json
├── vercel.json                              Node runtime, AI Gateway config, env scoping
└── package.json                             @vercel/ai, openai, @google/genai (routed by Gateway)
```

**Critical invariants of the sidecar:**
- Stateless — every fact in front of the LLM came from either `data/grounding/<tenant>/` (static, built at deploy) or a tool call (live, JWT-scoped).
- Tenant-namespaced — JWT `tenant` claim drives all filesystem paths + Odoo URL resolution.
- No business state ever persists in the sidecar beyond the request lifetime.
- AI Gateway routes by Hermes hint: `openai/gpt-4o` default; `gemini-2.5-flash` for long-context retrieval turns; opus-class only for T2 draft synthesis.

### 2.4 Overseer (v1.x, separate)

Out of scope for this spec's implementation, but locked-in architecturally:
- Own Vercel project (`hermes-overseer` or similar), own domain, own auth (Clerk / Auth0).
- Cross-tenant tools only (`list_tenants`, `queue_depth_by_tenant`, `pending_recommendations_global`, `rag_reindex(tenant)`, `sidecar_health(tenant)`, `audit_log_search(tenant, q)`).
- Authenticates against each tenant Odoo via a privileged service account distinct from any tenant-user JWT.
- Reads each tenant's `/southbrook/os.json` plus its own meta-OS (the fleet's `systems_topology.md` writ large).
- **Ops-only.** No tenant business data — ever, in v1.x. If a future operational need surfaces (e.g., debugging a specific tenant order on the tenant's request), it's solved by logging into that tenant Odoo directly, not by widening the Overseer's scope.

### 2.5 Diagram

```
                  ┌────────────────────────────────────────────────────────────────────┐
                  │   Overseer Hermes (v1.x — control plane, ops-only, chat + dash)    │
                  └─────────────────────────────────┬──────────────────────────────────┘
                                                    │ privileged service-account JWT
                                                    │ (scoped to ops-only tools)
                  ┌─────────────────────────────────┴──────────────────────────────────┐
                  ▼                                  ▼                                  ▼
        ┌────────────────────┐             ┌────────────────────┐            ┌────────────────────┐
        │ Southbrook Odoo    │             │ Porterly Odoo (v2) │            │ Tribancs Odoo (v2) │
        │ ├─ southbrook_os   │             │ ├─ porterly_os     │            │ ├─ tribancs_os     │
        │ ├─ southbrook_hermes│            │ ├─ porterly_hermes │            │ ├─ tribancs_hermes │
        │ └─ southbrook_api  │             │ └─ porterly_api    │            │ └─ tribancs_api    │
        └─────────┬──────────┘             └─────────┬──────────┘            └─────────┬──────────┘
                  │ POST /hermes/v1/ask              │                                  │
                  │ Bearer JWT { tenant:"southbrook",│                                  │
                  │              persona, partner_id,│                                  │
                  │              tier, order_id }    │                                  │
                  └──────────────────┬───────────────┴──────────────────────────────────┘
                                     ▼
                  ┌────────────────────────────────────────────────────────────────────┐
                  │  Hermes Sidecar (Vercel, single project, tenant-namespaced)        │
                  │  ─ stateless, JWT-routed                                           │
                  │  ─ /data/grounding/<tenant>/ + /data/index/<tenant>/               │
                  │  ─ AI Gateway → OpenAI default / Gemini routable                   │
                  │  ─ tool dispatch → POST tenant Odoo /api/hermes/tools/<name>       │
                  └────────────────────────────────────────────────────────────────────┘
```

---

## 3 · Data flow (single trade-partner turn)

The full per-turn sequence is in the brainstorm record (this conversation's
§2 diagram). Three invariants the flow enforces:

1. **Sidecar never holds business state.** Every fact comes from the
   tenant-namespaced RAG index OR a tool call executed during this turn.
2. **Record rules are the single source of truth for ACL.** When the sidecar
   calls a tool, Odoo re-resolves the persona from the JWT and runs the
   underlying ORM query in that user's security context.
3. **JWT lifetime = inner request, not conversation.** 60-second JWTs; new
   `/ask` call mints a fresh one. If the user's session expires mid-conversation,
   the next turn fails cleanly at JWT issuance, never deep inside a tool call.

**Action-creation variant (T2 path).** LLM emits
`propose_recommendation(type, payload, summary)` tool call → sidecar POSTs to
Odoo to create a draft `southbrook.hermes.recommendation` → Hermes answers
*"I've queued a draft (#REC-1234). Approve it in the Recommendations panel and I'll apply it."*
No business state moves without a human click.

**Failure paths.** AI Gateway timeout → 503 + `retry_after_ms` to chat panel.
Tool call exception → `{error, code}` JSON to LLM, which recovers or surrenders.
LLM hallucination guard → tool calls are the ONLY way live data enters context;
system prompt instructs "if you don't have a tool result, say you don't know."

---

## 4 · Persona model, ACL, action tiers

### 4.1 Resolution

```python
# southbrook_api/controllers/hermes_proxy.py
def resolve_persona(env_user):
    if env_user.share:
        return "trade_partner"                       # v1.0
    if env_user.has_group("sales_team.group_sale_salesman"):
        return "sales_rep"                           # v1.1
    if env_user.has_group("southbrook_kitchen_workspace.group_kitchen_ops"):
        return "mfg_manager"                         # v1.2
    raise AccessError("Hermes is not available for this user role.")
```

Per turn. Baked into the 60s JWT. No client-side trust.

### 4.2 Tier matrix

| Persona | T0 — logging | T1 — communication | T2 — business mutation |
|---|---|---|---|
| **Trade Partner** (v1.0) | own-order chatter, internal notes, conversation log | resend spec PDF, schedule own follow-up activity | ✗ — proposes via `propose_recommendation`, sales rep approves |
| **Sales Rep** (v1.1) | any owned record's chatter | partner emails, internal calls, opportunity activities | drafts auto-approve under threshold; manager approve above |
| **Mfg Manager** (v1.2) | MO/WO/job chatter, downtime notes | ops emails (delay, reschedule) | draft only; 2-eyes review modal for reschedule, CAD approve, MO confirm |

### 4.3 ACL = tool registry

Each tool function decorated:

```python
@hermes_tool(personas=["trade_partner", "sales_rep"], tier="T0", scope="own_order")
def get_order_status(env, order_id: int) -> dict:
    order = env["sale.order"].browse(order_id)       # record rules apply
    return {...}
```

The sidecar fetches the registry at boot, cached, refreshed on Hermes addon
upgrade. Per turn, the function list shown to the LLM is exactly the slice
allowed for `(persona, tier)`. **Forbidden tools don't exist** in the LLM's
function definitions — no "tried to call a forbidden tool" path.

### 4.4 Guardrails shipping in v1.0 even though they only matter later

1. **Tier downgrade in a single turn** — sales rep asking about an out-of-book
   order gets `{error: "out_of_scope"}` from record-rule denial; LLM rewords
   as "I don't have access to that order."
2. **Hard ban on `sudo()` inside tools** — record rules always apply. Only
   exception is explicitly tier-gated T2 tools with a documented reason
   (e.g., minting a recommendation crosses users by design).
3. **Per-tenant tool prefix** — `southbrook__get_order_status`, not
   `get_order_status`. Prevents misrouted cross-tenant calls when v1.x adds
   Porterly.

---

## 5 · OS layer detail

### 5.1 `southbrook.os.section` model

Fields:
- `slug` (Char, indexed, unique) — e.g. `02_catalog`
- `name` (Char, translatable)
- `source` (Selection: canonical / generated)
- `body` (Text, markdown)
- `body_html` (Text, computed, sanitized)
- `version` (Integer, monotonic, bumped on OSRO apply)
- `last_updated_at` (Datetime)
- `last_updated_by` (Many2one res.users)
- `applies_to_publication_ids` (Many2many southbrook.os.publication)

### 5.2 OS Revision Order (`southbrook.os.revision`, OSRO)

Mirrors the existing ECO state machine (`southbrook.eco`):

```
Draft → Under Review → Approved → Applied → (Rejected)
```

An OSRO carries `target_slug` (which section it edits), `proposed_body`,
`change_summary`, `reviewer_ids`, and `apply_handler` (the method run on
approve). Applying an OSRO bumps the section's `version` and snapshots into
the current publication.

### 5.3 OS Publication (`southbrook.os.publication`)

Snapshot of every section at a moment in time. Identified by a calendar string
(`2026-06`, `2026-07`, …) plus a build hash. Pinnable from `sale.order` via
`os_publication_id` — exactly like the cut-spec snapshot in
`southbrook_estimating/models/sale_order.py`.

### 5.4 Generators

`generated/*.md` files are produced by `models/os_generators.py`:

```python
def generate_catalog_md(env) -> str:
    templates = env["product.template"].search([("active", "=", True), ...])
    return render_catalog_template(templates)
```

Triggers:
- Nightly `ir.cron` (3 AM) for routine refresh
- On ECO apply (cut-spec or BoM changes)
- On manual button (Settings → Southbrook OS → Regenerate)

Each generator writes its file, computes a hash, updates the corresponding
`southbrook.os.section`. If the hash is unchanged, the section is unaltered
(no spurious version bumps).

### 5.5 Public endpoints

- `GET /southbrook/os` — full HTML, TOC + search, public (no auth). Mode: light.
- `GET /southbrook/os/<slug>` — single-section deep link.
- `GET /southbrook/os.json` — agent-consumable structured form (sections + metadata + ontology).
- `GET /southbrook/os.pdf` — printable, branded, used for new-hire packets and investor handoffs.

### 5.6 Coverage tests

`tests/test_os_coverage.py` iterates every `@hermes_tool` and every entry in
`07_partner_faq.md` and asserts each is grounded by a referenced
`southbrook.os.section`. Prevents drift — if a new tool ships without an OS
section that documents the concept it touches, CI fails.

---

## 6 · Tool catalog (v1.0 trade partner)

Twelve tools, all in `addons/southbrook_hermes/tools/`:

| Tool | Tier | Scope | Returns |
|---|---|---|---|
| `list_my_orders` | T0 read | own | `[{ref, stage, partner, install_due}…]` |
| `get_order_status` | T0 read | own | `{stage, mos, bottleneck, blocker, next_action, install_due, readiness, version}` |
| `get_order_line` | T0 read | own | `{sku, variant, qty, attributes, retail, channel, flags}` |
| `list_my_kitchen_projects` | T0 read | own | `[{ref, stage, option_count, selected}…]` |
| `get_kitchen_project` | T0 read | own | `{options:[A,B,C], approval_status, drawings_url}` |
| `get_install_schedule` | T0 read | own | `{date, dispatch, risk_flag, risk_reason}` |
| `get_quote_pdf_url` | T0 read | own | `{pdf_url, valid_until}` |
| `list_my_recommendations` | T0 read | own | `[{rec_id, type, summary, state}…]` |
| `get_os_section` | T0 read | global | `{slug, body, version}` |
| `post_internal_note` | T0 write | own | posts mail.message internal note |
| `send_spec_pdf_email` | T1 comm | own | resends spec PDF to partner's own email |
| `schedule_followup_activity` | T1 comm | own | creates mail.activity on partner's user |
| `propose_recommendation` | T2 propose | own | creates draft `southbrook.hermes.recommendation` |

Trade-partner-allowed `type` values for `propose_recommendation`:
`request_revision`, `request_install_reschedule`, `request_clarification`.
Other types reject with `not_allowed_for_persona`.

**Explicit non-tools in v1.0:** no billing, no payments, no refund requests,
no cad-drawing-direct-download, no SKU-price-without-existing-config (no
"shop the catalog through chat").

---

## 7 · RAG corpus (sourced from `southbrook_os`)

```
data/grounding/southbrook/
├── canonical/                ← copied verbatim from southbrook_os/canonical/
└── generated/                ← copied from southbrook_os/generated/ (latest publication)
```

Indexed at sidecar build time with `text-embedding-3-small` (1536d). Flat
`index.json` per tenant. Top-K = 5 per turn. No external vector DB at v1
scale (corpus ~30 KB); reconsider at 10× growth.

**Refresh trigger.** When `southbrook_os.exports.rag_corpus_export.py` runs
(post-OSRO-apply, nightly cron, or manual), it writes a new bundle into
`hermes-sidecar/data/grounding/southbrook/` and triggers a Vercel redeploy
of the sidecar via a webhook. No business-data downtime — sidecar restart is
seconds.

---

## 8 · Phasing

| Phase | Ships | Acceptance |
|---|---|---|
| **v1.0** | `southbrook_os` (canonical + generators + JSON endpoint), `southbrook_hermes` trade-partner surface (12 tools, RAG corpus, OWL chat panel in Order Builder), **and the three multi-tenant hooks** baked in from day one (JWT carries `tenant` claim; sidecar paths namespace by tenant; tool dispatch reads tenant→Odoo from a registry config). The hooks cost ~50 LOC at v1.0 and avoid a non-trivial refactor when tenant #2 lands. | A trade partner asking "where is my kitchen?" gets a correct, sourced answer in <8s p95 on a real prod order. `/southbrook/os.json` returns a valid sectioned doc. JWT verification logs show `tenant: "southbrook"` on every turn. |
| **v1.1** | OSRO governance + public HTML viewer (`/southbrook/os`) | An OSRO can be drafted, reviewed, approved, applied; the public HTML shows the updated section within 5 minutes. |
| **v1.2** | Sales-rep backend chat panel + sales-rep tool set (~8 new tools) | A sales rep using the Order Builder backend can ask "which of my orders are at risk this week?" and get a sourced list. |
| **v1.3** | Mfg-manager Kitchen Ops widget + mfg tools (~6 new tools) | Manufacturing manager on the Kitchen Job Command Center can ask "what's blocking S00235?" with bottleneck + next-action correctly identified. |
| **v1.x (later)** | **Overseer** + meta-OS for the fleet | Once a 2nd tenant exists, Overseer can list tenants, query ops state per tenant, and trigger reindexes — without ever touching tenant business data. |

---

## 9 · Testing strategy

- **Unit (Odoo):** every `@hermes_tool` has a unit test exercising record-rule
  scoping + payload shape.
- **Unit (sidecar):** JWT verify, tool dispatch, RAG retrieval, prompt assembly.
- **Integration:** end-to-end "trade partner asks X" test runs the full loop
  in a sandbox sidecar against a seeded Odoo DB. Asserts both shape and
  sourcing.
- **OS coverage:** `tests/test_os_coverage.py` asserts every tool and every
  FAQ entry maps to an OS section (no orphan concepts).
- **Hallucination eval:** a curated set of 30 trade-partner questions with
  expected anchor facts; sidecar must cite tool calls / RAG hits for each
  factual claim. Fails CI if hallucination rate > 2%.
- **Persona ACL:** matrix of `(persona, tool, scope)` × `(allowed/denied)`,
  asserted by integration tests.

---

## 10 · Error handling

| Failure | Symptom | Behavior |
|---|---|---|
| AI Gateway timeout | sidecar `/ask` returns 503 + retry hint | chat panel shows "Hermes is temporarily unavailable" + retry button |
| Tool exception | tool returns `{error, code}` | LLM gets it as a function result; recovers or surrenders gracefully ("I can't reach that data right now") |
| JWT expired mid-turn | sidecar 401 on tool callback | turn aborts; next user message mints fresh JWT |
| LLM hallucinates a non-sourced fact | (no automatic detection in v1.0) | mitigation = system prompt + tool-call-only data + post-hoc eval |
| RAG corpus unbuilt for tenant | sidecar `/ask` returns 503 with `code=corpus_missing` | chat panel shows admin-targeted error; resolved by triggering rebuild |
| OSRO apply fails | `southbrook.os.revision.state` stays at `Approved`, error in chatter | nothing user-visible breaks; admin sees the failure on the OSRO record |
| Sidecar redeploy mid-conversation | conversation loses streaming connection | OWL component reconnects; partial answer dropped, last logged Q remains in `southbrook.hermes.question` |

---

## 11 · Explicit non-goals for v1.0

- No billing / payments surface in Hermes.
- No cross-tenant data flow (Overseer is v1.x).
- No write actions for trade partners that don't pass through a recommendation.
- No external integrations (no Slack, no Teams, no email-driven conversations).
- No mobile-native client; the OWL component runs in the existing portal/backend chrome.
- No multi-language; English only.
- No conversation memory beyond the current `southbrook.hermes.question` thread.
  (Cross-conversation memory is a v2 question.)
- No vector DB; flat per-tenant `index.json` on Vercel disk.
- No image / file uploads in chat. Text-only Q+A.

---

## 12 · Open questions to resolve before implementation plan

These don't gate the design but must be answered before writing-plans:

1. **Embedding model freeze.** `text-embedding-3-small` is fine for v1; if you
   want `text-embedding-3-large` for better recall, decide before the RAG
   index format is committed.
2. **OWL chat panel placement.** Floating bottom-right overlay, or a docked
   side panel inside the Order Builder? Both work; visual choice.
3. **JWT secret rotation policy.** v1.0 ships with a static `HERMES_JWT_SECRET`
   env var; if you want rotation from day one, we add JWKS endpoint complexity.
4. **Sidecar repo location.** Sibling of `southbrook-v19cr` (new repo
   `hermes-sidecar`), or a subdirectory inside `southbrook-v19cr/sidecar/`?
   Multi-tenant later argues for sibling.
5. **Generators for `02_catalog.generated.md` etc. — Markdown style.** Plain
   tables, or YAML-style frontmatter + Markdown body? Affects how Hermes
   quotes them.

---

## 13 · References

- `docs/CUSTOMER_TO_MANUFACTURING_FLOW.md` — the four-persona architecture lock
- `CLAUDE.md` — the estimating brief (canonical for product-level decisions)
- `addons/southbrook_premium_orchestration/docs/DESIGN_SPEC.md` — orchestration spine (cron, MI, project-task)
- `addons/southbrook_hermes/` — Fabio v0 implementation (deployed 2026-06-16)
- `2026-06-16-hermes-agent-design.md` — Fabio v0 sidecar pattern (predecessor of this spec)
- `2026-06-16-fabio-agent-identity-design.md` — Fabio's branded agent identity (predecessor)
- The 63-step canonical Southbrook OS narrative supplied in the brainstorm prompt — this becomes the seed for `southbrook_os/canonical/*.md`

---

## 14 · Implementation deltas (added 2026-06-16 post-build)

Spec ↔ implementation drift captured after Plan B1 + B2 landed. These are
the places where the shipped code diverges from the brainstorm-validated
design above; every one is intentional, surfaced by the xhigh-effort code
review pass, and is reflected in the live `southbrook_os 19.0.1.0.0` +
`southbrook_hermes 19.0.3.2.0` build.

### 14.1 Persona tier mask widened to include T2

§ 4.2's matrix marks T2 as "✗" for trade partners while § 6 calls
`propose_recommendation` a "T2 universal escape hatch." Strictly enforcing
the mask blocks every trade-partner call to a T2 tool at the dispatch
controller's tier check.

Resolved by widening `tier_for_persona` to return `T0+T1+T2` for all three
personas. The trade-partner safety boundary moves from the tier mask
(always going to leak the moment one T2 tool needed to be addressable by
trade partners) to the tool's own intent allow-list:
`propose_recommendation` enforces `_TRADE_PARTNER_INTENTS` directly, and
dispatch injects the persona claim before the tool runs so a caller can't
forge it. Net behavior = exactly what § 4.2 wanted; only the enforcement
layer moved.

### 14.2 Dispatch claim-binding overrides caller-supplied args

§ 4.3 says "ACL = tool registry" but doesn't specify how persona context
reaches each tool function. The first implementation accepted `persona`,
`partner_id`, and `tenant` as ordinary tool args — which the LLM (or a
malicious prompt injection) could forge to attribute a recommendation to
another partner or lift its own intent guard.

Resolved: dispatch now inspects each tool's signature and, for any of
`persona` / `partner_id` / `tenant`, overrides the request-body value
with the verified JWT claim before calling. Tools that don't declare
those args are unaffected.

### 14.3 Dispatch returns 403 when partner has no `res.users`

§ 4.3's tool dispatch resolved partner → user via `partner.user_ids[:1]`.
If empty (e.g., a partner imported without a portal invite), the original
code fell back to `request.env.user` — which on the `auth='public'` route
is the public user. Every subsequent tool call then ran as the
least-privileged identity, surfacing as confusing 500s with no signal
that the root cause was a missing user link.

Resolved: dispatch now returns 403 `partner_has_no_user` with a clear
detail message, AND 403 `unknown_partner` if the partner record itself
is missing. See § 14.11 for the full error table addition.

### 14.4 Read tools derive partner from `env.user`, not args

`list_my_kitchen_projects` and `list_my_recommendations` originally took
a `partner_id` arg and ran a `.sudo()` search keyed on it — the LLM
could pass any other partner's ID to enumerate their data. Resolved:
both tools now ignore the args-supplied `partner_id` and key off
`env.user.partner_id.id` (which dispatch sets from the verified JWT).
The arg signature is preserved for backward compatibility but
documented as informational only.

### 14.5 `check_access_rule` added everywhere it was missing

§ 4.4 rule 2 ("Hard ban on `sudo()` inside tools") was missed in three
read tools and one write tool. `get_install_schedule`,
`get_quote_pdf_url`, and `schedule_followup_activity` called
`check_access_rights` (model-level ACL) but skipped `check_access_rule`
(record-rule scope). All three now call both checks. `get_order_status`
was likewise sudo-reading `project.task` and `mrp.production`; dropped
to bare search so record rules apply.

### 14.6 Conversation log carries `sale_order_id`

§ 6's tool catalog and § 3's data flow assume the conversation persists
with order context. The original `southbrook.hermes.question` model had
`project_id` (kitchen project) but no `sale_order_id`, so the sidecar's
`order_id` was dropped at the controller. Added `sale_order_id`
Many2one + `order_id` kwarg on `log_conversation` + controller plumbing.
Persisted Q+A records now link back to the order the partner was
looking at.

### 14.7 JWT TTL widened from 60s to 120s

§ 3 invariant 3 says "JWT lifetime is the inner request, not the
conversation." The 60-second default was correct in spirit but, on a
slow model run with 4–5 tool roundtrips, the token expired mid-loop and
the next tool call returned 401 to the LLM as a confusing tool-error
result. Resolved: `hermes_proxy.py:_JWT_TTL_FOR_ASK = 120`. Lifetime is
still per-request (not per-conversation) but covers the realistic
worst-case agent loop within Vercel's 60s function cap.

### 14.8 Sidecar registry cache key

§ 2.3's "cached per tenant for the lifetime of the cold start" was
implemented as `tenant + last-12-chars-of-jwt`. Since each request mints
a fresh JWT the suffix is random — the cache never warmed across
requests AND could collide on base64url-suffix matches. Resolved: cache
key is now `tenant::persona::tier` from verified claims.

### 14.9 Sidecar `verifyJwt` surfaces config errors

A missing `HERMES_JWT_SECRET` env var was being swallowed by a bare
`catch{}` and returned as `null` — operationally indistinguishable from
a bad token. Resolved: `getSecret()` now throws outside the try so a
config error propagates to the route handler's 503 `jwt_config`
response instead of masquerading as 401 `invalid_token`.

### 14.10 Other minor deltas

- `convertToModelMessages()` removed from the agent loop — was incorrect
  for already-typed `CoreMessage[]`, could silently drop the RAG
  injection + persona-voice system messages.
- `tenants.ts` validates every TENANT_REGISTRY value is a non-empty
  string at parse time, preventing `null` values from poisoning the
  module-global cache.
- `hermes_proxy.py` explicitly closes the upstream `requests.Response`
  on the non-2xx error branch — was leaking sockets under sustained
  sidecar errors.
- `os_loader.py` writes the full vals dict on re-import (was dropping
  `source` + `audience_tags`, updating only `body` + `name`).
- OWL chat panel's `TextDecoder` is flushed after the stream ends so
  multi-byte UTF-8 sequences in the final chunk (accented characters,
  em-dashes) aren't silently dropped.

### 14.11 Error envelopes the spec § 10 table didn't anticipate

Added to the live error contract:

| Surface | Code | Status | When |
|---|---|---|---|
| dispatch | `partner_has_no_user` | 403 | partner is JWT-authenticated but has no `res.users` row |
| dispatch | `unknown_partner` | 403 | `partner_id` claim points at a deleted/non-existent partner |
| proxy | `hermes_not_configured` | 503 | JWT secret unset OR PyJWT not installed |
| proxy | `sidecar_unreachable` | 502 | `requests.RequestException` from the sidecar POST |
| proxy | `sidecar_error` | passthrough | sidecar returned non-JSON 4xx/5xx |
| sidecar `/ask` | `jwt_config` | 503 | `HERMES_JWT_SECRET` env var missing |
| sidecar `/ask` | `unknown_tenant` | 403 | JWT tenant claim not in `TENANT_REGISTRY` |
| sidecar `/ask` | `empty_question` | 400 | empty `body.q` |

All verified end-to-end by `scripts/smoke_hermes.sh`.

