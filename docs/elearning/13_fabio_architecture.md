---
course: 13 — Fabio Deep Dive
chapter: 13.1
title: Fabio Architecture — The Four Pillars and How They Fit
duration: 30 minutes
audience: Every Fabio user (Production Manager, CS lead, Estimator, Sysadmin) and every developer touching the addon
prereqs: Lesson 3.2 (`03_hermes_fabio_approval.md`) for the in-Odoo approval queue end of the picture, the v1 design spec at `docs/superpowers/specs/2026-06-16-southbrook-os-and-hermes-platform-design.md` §§ 2–4, CLAUDE.md amendment 2026-06-16 ("Hermes platform shipped")
custom_modules: southbrook_hermes, southbrook_os
---

# Fabio Architecture — The Four Pillars and How They Fit

## Who this lesson is for

You're anyone who interacts with Fabio — the trade-partner-facing AI assistant
surface that Southbrook embeds inside Odoo. Maybe you click **Approve** on
recommendations (lesson 3.2). Maybe you're a dealer asking "where is my
kitchen?" from the Order Builder. Maybe you're a developer adding a thirteenth
tool. Before any of that goes anywhere useful, you need the same mental model
of *what Fabio actually is*.

The internal addon is called `southbrook_hermes`. The user-facing brand
everywhere — menus, partner record, the chat panel header — is **Fabio**. The
two names are the same thing. The spec uses "Hermes" (the platform), the UI
uses "Fabio" (the persona); this lesson uses whichever the surface you're
reading uses.

## Where this lives on the site

Fabio exposes itself through three concrete surfaces; you reach each one a
different way.

> **Fabio → Recommendations** — the in-Odoo approval queue (lesson 3.2).
> Requires the `southbrook_hermes.group_hermes_reviewer` group.

> **Fabio → Ask** — the in-Odoo conversation log (`southbrook.hermes.question`
> list), also reviewer-gated. Useful for reading prior turns.

> **Order Builder portal → chat panel** — the OWL chat panel that auto-mounts
> on the customer's Order Builder page (`southbrook_estimating_website.portal_order_builder`).
> Trade partners hit this; sysadmins don't. The panel mount HTML is injected
> by `views/order_builder_chat_inject.xml` and the auto-mount is wired up in
> `static/src/components/hermes_chat/hermes_chat.esm.js`.

System-parameter wiring lives at:

> **Settings → Technical → System Parameters** —
> `southbrook_hermes.sidecar_url`, `southbrook_hermes.sidecar_enabled`,
> `southbrook_hermes.jwt_secret`. These three knobs decide whether Fabio's
> chat is live, stubbed, or off. (Detail: lesson 13.3 + lesson 13.7.)

## What your screen shows

The "four pillars" framing makes Fabio understandable in one diagram. Each
pillar is a concrete chunk of code; each interacts with the others through a
single, documented contract.

### Pillar 1 — The recommendation queue (`southbrook.hermes.recommendation`)

The human-approval boundary. Every business mutation Fabio proposes — request
a revision, reschedule an install, raise a clarification — lands here as a
*draft* row that a human reviewer must approve and apply before the database
changes. Model lives in `models/hermes_recommendation.py`. State machine:
`draft → ready → approved → applied` with a sideways `rejected` exit. The
queue is what makes Fabio safe to deploy at all — a hallucinating agent
without an approval boundary would be a liability. Full depth: lesson 13.2.

### Pillar 2 — JWT auth + persona resolution (`utils/jwt_helper.py`)

Every Fabio call lives inside a short-lived HS256 JWT. The token carries
four claims: `tenant`, `persona`, `partner_id`, and `tier`. The minting +
verification helpers + the `resolve_persona(user)` function are in
`utils/jwt_helper.py`. Persona is derived from `res.users.share` plus group
membership — *not* from anything the browser sends. The tier is derived from
the persona, again server-side. This is the boundary that means a malicious
prompt or a leaked token can't escalate. Full depth: lesson 13.3.

### Pillar 3 — The tool registry (`@hermes_tool` + `TOOL_REGISTRY`)

Thirteen tools at v1.0 — 9 read + 4 write. Each is a plain Python function
decorated with `@hermes_tool(slug, personas, tier, scope, description)`.
The decorator (`tools/decorator.py`) registers the function into a
process-level `TOOL_REGISTRY` list at import time. The sidecar fetches the
registry from `GET /api/hermes/tools` and dispatches individual calls via
`POST /api/hermes/tools/<slug>` — both routes in `controllers/hermes_tools_api.py`.
Persona × tier filtering happens at registry time AND at dispatch time;
record-rule scoping happens inside the tool, via
`request.env(user=portal_user)`. Full depth: lessons 13.4, 13.5, 13.6.

### Pillar 4 — The chat panel + Vercel sidecar (OWL + Next.js)

The OWL component (`HermesChat` in
`static/src/components/hermes_chat/hermes_chat.esm.js`) is what the trade
partner sees. It POSTs to `/hermes/v1/ask` (controller in
`controllers/hermes_proxy.py`), which mints a JWT and then either (a) calls a
configured Vercel sidecar over HTTP and streams the response back to the
browser, or (b) returns a JSON stub when `sidecar_enabled` is `false`. The
sidecar (in `sidecar/` at the repo root) does the LLM call + RAG retrieval +
tool dispatch + conversation logging. The Odoo side never talks to the LLM
directly. Full depth: lesson 13.7.

### What `southbrook_os` provides (the foundation Fabio grounds in)

`southbrook_os` is a separate addon (manifest in
`addons/southbrook_os/__manifest__.py`, depends: `base, mail, product, mrp,
southbrook_estimating`) that ships the Southbrook business knowledge as
markdown sections. Ten **canonical** files under `addons/southbrook_os/canonical/`
(`00_charter.md`, `01_company.md`, … `99_glossary.md`); four **generated**
files that the nightly cron rebuilds from live Odoo state (catalog,
attributes, cut spec, work centers). All sections surface through the
`southbrook.os.section` model and are exposed publicly as JSON at
`GET /southbrook/os.json`. The sidecar's RAG index is built from that JSON
at deploy time. Without an OS, Fabio has nothing to ground in; `southbrook_hermes`
hard-depends on `southbrook_os` for exactly this reason.

## Your daily flow

You don't run Fabio's architecture — you use one of its three surfaces. The
flow you follow depends on your role.

**1. Trade partner (the originating persona of a Fabio chat):**

- Open your order in the portal Order Builder.
- Find the chat panel below the order header.
- Type your question. The panel POSTs to `/hermes/v1/ask`, your JWT is
  minted in-place, your persona is resolved as `trade_partner` because
  `env.user.share == True`, the question goes to the sidecar (or stub),
  the answer streams back into the panel.
- If the answer creates a draft recommendation
  (`propose_recommendation` was called by the model), the chat tells you
  so. The recommendation is now in Fabio's queue for a Southbrook
  reviewer.

**2. Production manager / CS lead (the human approval side):**

- Open **Fabio → Recommendations**, default `Open` filter applied (state
  in draft/ready/approved).
- Read the recommendation, decide, approve/reject/apply. Lesson 3.2
  walks the queue end-to-end. Lesson 13.2 goes one level deeper into the
  state machine, the audit fields, the `_create_project_task` mechanic,
  and the security group that gates the menu.

**3. Developer (adding or changing a tool):**

- Read the spec (§ 6 catalog, § 4 ACL model).
- Read lessons 13.4 (registry) + 13.5 (read tools) + 13.6 (write tools +
  tier model).
- Add the function in `tools/read_tools.py` or `tools/write_tools.py`,
  decorate with `@hermes_tool`, decide personas + tier + scope honestly.
- For T2 tools, route through `propose_recommendation` — do NOT write
  business state directly.
- Update the OS section that documents the concept the tool exercises
  (the `test_os_coverage.py` CI gate enforces this).
- Smoke-test with `scripts/smoke_hermes.sh`.

**4. Sysadmin (the platform owner):**

- Settings → Technical → System Parameters. The three relevant keys
  decide Fabio's state: `sidecar_url` (where), `sidecar_enabled`
  (whether), `jwt_secret` (signed by what). Lesson 13.3 covers
  rotation policy.

## Common mistakes + how to recover

**"I deployed `southbrook_hermes` but the Fabio menu doesn't show up."**

The menu is gated by `southbrook_hermes.group_hermes_reviewer`. Your user
needs to be in that group. Note from `security/hermes_security.xml`:
`base.group_system` (Settings → Users → Internal User → Administration:
Settings) inherits the reviewer group, so any sysadmin sees it for free.
Production managers need to be added explicitly. Trade partners are share
users and never see this menu — that's correct.

**"The chat panel says '(Stub answer — sidecar not yet wired)'."**

That's not broken. That's the design. The proxy returns a stub answer when
`southbrook_hermes.sidecar_enabled` is unset/false OR `sidecar_url` is empty
(see `controllers/hermes_proxy.py` lines around the `_is_truthy(... sidecar_enabled)`
check). The stub still exercises JWT mint + verify so you know the auth
path works. Flip `sidecar_enabled` to `true` after the Vercel deploy
lands. See lesson 13.7 for the deploy.

**"I added a new tool, it's in `tools/`, decorated with `@hermes_tool`, but
the sidecar's tool list doesn't have it."**

The sidecar caches the registry at cold start. `lib/tools.ts` keys the
cache by `tenant::persona::tier` (post-fix per spec § 14.8). A Vercel
redeploy invalidates it; an addon upgrade alone doesn't. If you want the
sidecar to pick up a new tool, redeploy: `vercel deploy --prod` (see
lesson 13.7).

**"The recommendation queue is empty but the chat says 'I've queued a
draft.'"**

Check what user the chat is authenticated as. The
`controllers/hermes_tools_api.py` dispatch creates the recommendation in
`sudo()` mode (explicit § 4.4 carve-out: a draft recommendation is owned
by Fabio, not the requesting partner). It's visible to reviewers via the
`group_hermes_reviewer` group, not to the partner who proposed it. The
trade-partner UI shows nothing; the reviewer UI shows the row in `draft`
state. That's working as designed.

**"I want to read what Fabio is grounded in but the OS sections are out of
date."**

Generators rebuild the four `*.generated.md` sections nightly (see
`addons/southbrook_os/data/ir_cron.xml`). For manual refresh, the spec
section § 5.4 prescribes a Settings button. Hit `/southbrook/os.json` to
see what's published *right now* — the response cache is 5 minutes
(`Cache-Control: public, max-age=300` in
`addons/southbrook_os/controllers/os_public.py`). The sidecar's RAG corpus
is a build-time snapshot of that JSON; a fresh corpus requires a sidecar
redeploy. Trade partners can't trigger this; sysadmins can.

## What the system is doing behind the scenes

The four pillars wire together like this on a single trade-partner turn:

1. The OWL chat panel POSTs `{q, order_id}` to `/hermes/v1/ask`.
2. `HermesProxyController.ask` calls `jwt_helper.resolve_persona(request.env.user)`.
   For a share user this returns `"trade_partner"`. For a non-share user with
   the salesman group, `"sales_rep"`. For a non-share user with
   `southbrook_kitchen_workspace.group_kitchen_ops`, `"mfg_manager"`.
   Otherwise `AccessError`.
3. Tier is derived: `tier_for_persona(persona)` returns `"T0+T1+T2"` for
   all three personas (per the § 14.1 implementation delta — the tier mask
   was widened to T0+T1+T2 because `propose_recommendation` is the
   "universal T2 escape hatch" and the trade-partner safety boundary
   moved *into* the tool itself via `_TRADE_PARTNER_INTENTS`).
4. JWT is minted by `jwt_helper.mint_jwt` with `ttl=120s` (widened from the
   spec's 60s default per delta § 14.7 to cover multi-step agent loops).
5. If `sidecar_enabled` is true, the proxy POSTs to `<sidecar_url>/api/hermes/ask`
   with `Authorization: Bearer <jwt>`. The sidecar verifies the JWT
   (`lib/jwt.ts`), retrieves top-K RAG hits from `data/index/southbrook/`,
   fetches the tool registry from `GET /api/hermes/tools` (cached by
   tenant::persona::tier), and runs an OpenAI / Gemini call through the
   Vercel AI Gateway.
6. The LLM may call tools. Each tool call goes back to Odoo at
   `POST /api/hermes/tools/<slug>` with the same JWT. Dispatch
   (`hermes_tools_api.dispatch`) enforces persona membership + tier mask
   + record-rule scope (`env(user=portal_user)`). Claim-bound args
   (`persona`, `partner_id`, `tenant`) are overridden from JWT claims
   before the tool is called (delta § 14.2 — closes the prompt-injection
   self-attribution hole).
7. The streamed answer flows back through `/hermes/v1/ask` to the OWL
   panel.
8. After the turn, the sidecar fire-and-forgets a
   `POST /api/hermes/conversation/log` with `{question, answer, order_id, …}`,
   which `controllers/hermes_conversation_api.py` writes as a
   `southbrook.hermes.question` record. The `order_id` is stored on the
   `sale_order_id` field (delta § 14.6).

If `sidecar_enabled` is false (the default after install), step 5–8
collapses to a JSON stub from the proxy. The OWL panel still rendered the
panel, the JWT was still minted + verified, you have proof the platform
is wired correctly before the sidecar is deployed.

## Quiz (5 questions, applied)

**1.** You SSH into the QNAP, install `southbrook_hermes` for the first
time, and a trade partner immediately opens their Order Builder. What
does the chat panel display when they ask "where is my kitchen?"

> A JSON stub answer of the form
> `"(Stub answer — sidecar not yet wired.) Question received: 'where is my
> kitchen?'."`. `southbrook_hermes.sidecar_enabled` defaults to `false`
> at install (see `data/ir_config_parameter.xml`), so the proxy short-
> circuits to a stub. JWT mint+verify still ran, so you have confirmation
> the auth path works.

**2.** A developer adds a new tool `get_order_invoices` decorated
`@hermes_tool(personas=["trade_partner"], tier="T0", scope="own_order")`,
ships the addon, restarts the Odoo container — but a trade partner asking
about invoices gets "I don't have a tool for that." What's most likely
wrong?

> The sidecar caches the tool registry at cold start (`lib/tools.ts`), and
> an addon upgrade alone doesn't invalidate that cache. The fix is a
> Vercel redeploy of the sidecar: `vercel deploy --prod`. The new tool
> will then be in the registry returned by `GET /api/hermes/tools` on the
> next cold start.

**3.** Why does `southbrook_hermes` hard-depend on `southbrook_os` in
its manifest (`depends = [..., "southbrook_os"]`)?

> Because Fabio is grounded in the OS. Without canonical knowledge to
> ground in — Southbrook's customer model, catalog, lifecycle, partner
> FAQ — the LLM has nothing but its own pretraining, which is the
> hallucination path the spec § 11 calls out as a v1.0 non-goal. The
> dependency forces the OS to install first; the RAG corpus is built
> from `/southbrook/os.json` which is `southbrook_os`'s endpoint.

**4.** Trade partner Fred chats Fabio: "actually reschedule my install
for next Tuesday." The LLM emits a `propose_recommendation` tool call.
Where does the change to Fred's install date happen?

> Nowhere — yet. `propose_recommendation` creates a *draft*
> `southbrook.hermes.recommendation` row (in `sudo()`, owned by the Fabio
> agent partner). A Southbrook reviewer in `group_hermes_reviewer` sees
> the row at **Fabio → Recommendations**, reads it, and clicks **Approve**
> → **Apply** to actually act on the request. Trade partners cannot move
> recommendation state. This is pillar 1's whole point.

**5.** A sysadmin asks "is Fabio's chat panel hitting the sidecar right
now?" You don't have shell access, only the Odoo backend. What do you
check?

> Settings → Technical → System Parameters →
> `southbrook_hermes.sidecar_enabled`. If it's `false`, the proxy stubs;
> live path is off. If it's `true`, also check `southbrook_hermes.sidecar_url`
> is non-empty — both conditions must hold for the proxy to actually
> call out. Cross-check by opening the chat panel and asking a question:
> the stub answer begins `"(Stub answer — sidecar not yet wired.)"`, so
> if you see that prefix you're in stub mode regardless of the parameter
> state.

---

## What this lesson does NOT cover

- The recommendation queue's state machine in source-level detail —
  lesson 13.2.
- JWT mint + verify internals and persona resolution — lesson 13.3.
- The `@hermes_tool` decorator, the registry endpoint, and dispatch ACL
  layering — lesson 13.4.
- The 9 read tools one by one — lesson 13.5.
- The 4 write tools and the T0/T1/T2 tier model — lesson 13.6.
- The OWL chat panel + Vercel sidecar streaming wire format — lesson 13.7.
- Approving recommendations (the floor manager's daily flow) —
  lesson 3.2 (`03_hermes_fabio_approval.md`).
- The CS-side view of the queue — lesson 6.3 (`06_hermes_cs_view.md`).
- Sysadmin recommendations (separate operator surface at hermes.odooiq.com)
  — lesson 7.3 (`07_hermes_sysadmin.md`).
