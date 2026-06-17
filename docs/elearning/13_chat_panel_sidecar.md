---
course: 13 — Fabio Deep Dive
chapter: 13.7
title: The OWL Chat Panel and the Vercel Sidecar
duration: 35 minutes
audience: Estimator / trade-partner-facing dealer (the chat panel user), IT admin / sysadmin (the sidecar operator), developer (the panel + proxy + sidecar code)
prereqs: Lesson 13.1 (`13_fabio_architecture.md`) for the four-pillar context; lesson 13.3 (`13_jwt_auth_personas.md`) for JWT + system parameters; lesson 13.4 (`13_tool_registry.md`) for the registry endpoint the sidecar consumes; CLAUDE.md amendment 2026-06-16 "Going live with chat" + sidecar deploy section
custom_modules: southbrook_hermes
---

# The OWL Chat Panel and the Vercel Sidecar

## Who this lesson is for

You're a dealer or estimator about to use the chat panel for the first
time and want to understand what's happening when you type a question.
You're an admin flipping `sidecar_enabled` to `true` for the first
time. You're a developer wiring a sidecar redeploy on a Vercel preview
URL.

The chat panel is the user-facing surface; the Vercel sidecar is the
LLM brain that powers it. The Odoo proxy controller is the bridge. This
lesson walks the round trip end-to-end.

## Where this lives on the site

### As the trade partner using the chat panel

> Sign in at **southbrookcabinetry.space/odoo**, navigate to your portal:
> **My** → **Orders** → click one of your orders → opens the **Order
> Builder** portal page.
> A chat panel appears below the order header card, labeled **Ask
> Hermes** with a subtitle "Order #235" (or whatever your order ref is).

The mount is injected by `views/order_builder_chat_inject.xml`:

```xml
<template id="hermes_chat_inject_order_builder"
          inherit_id="southbrook_estimating_website.portal_order_builder"
          name="Hermes Chat — Order Builder mount">
  <xpath expr="//div[hasclass('o_southbrook_portal_header')]" position="after">
    <div class="o_hermes_chat_wrap mt-3 mb-3"
         data-hermes-chat-mount="1"
         t-att-data-order-id="order_id or ''"/>
  </xpath>
</template>
```

This adds a `<div data-hermes-chat-mount="1">` to the Order Builder
portal page. The OWL bundle's `autoMount()` finds that div and mounts
a `HermesChat` component into it.

### As the IT admin operating the chat surface

> **Settings → Technical → System Parameters** — three keys:
> `southbrook_hermes.jwt_secret`, `southbrook_hermes.sidecar_url`,
> `southbrook_hermes.sidecar_enabled`. Flip `sidecar_enabled` to
> `true` to wire chat to the live sidecar; leave at `false` for stub
> mode.

### As the developer working on the sidecar

> Sidecar code lives at `/Users/naadmin/southbrook-v19cr/sidecar/`. Routes
> in `sidecar/app/api/hermes/ask/route.ts` (TBD — agent didn't read
> file). Vercel project linked via `vercel link` at repo root. Deploy:
> `vercel deploy --prod` from `sidecar/`.

## What your screen shows

### The chat panel UI

The OWL template at `static/src/components/hermes_chat/hermes_chat.xml`
renders four sections:

- **Header.** "Ask Hermes" title, with "· Order #235" subtitle when
  the panel knows the order context.
- **Message scroll area.** Empty state placeholder ("Ask about your
  order, the configurator, or anything in the Southbrook OS. Try:
  'where is my kitchen?' or 'what attributes can I configure?'") until
  the first message. Each subsequent message renders as
  `o_hermes_chat__msg o_hermes_chat__msg--{user|assistant}`. The
  in-progress assistant message shows a `▍` block cursor while
  streaming.
- **Error line.** Renders `state.error` if set (e.g. "Hermes is
  unavailable").
- **Input row.** A two-row textarea + an Ask button. Cmd-Enter (or
  Ctrl-Enter) submits.

### What clicking "Ask" does

`HermesChat.submit()` in `hermes_chat.esm.js`:

```javascript
async submit() {
    const q = (this.state.inputValue || "").trim();
    if (!q || this.state.sending) return;
    this.state.error = null;
    this.state.sending = true;
    this.state.messages.push({ role: "user", content: q, streaming: false });
    const assistant = { role: "assistant", content: "", streaming: true };
    this.state.messages.push(assistant);
    this.state.inputValue = "";
    this._scrollToBottom();
    try {
        const resp = await fetch(ENDPOINT, {  // ENDPOINT = "/hermes/v1/ask"
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ q, order_id: this.orderId }),
        });
        ...
    }
}
```

Two things happen in parallel as the click lands:
1. The user's message is appended to `state.messages` and the input
   clears.
2. A placeholder assistant message is appended (with
   `streaming: true`), so the cursor shows immediately.

Then `fetch('/hermes/v1/ask', ...)`. The Odoo proxy mints a JWT (lesson
13.3), calls the sidecar (if `sidecar_enabled`), and streams the
response back. The OWL component handles two response modes:

**JSON mode.** When `content-type` includes `application/json`. This
is the stub mode or an error from the sidecar. The component reads
`j.answer` (or `j.stub`-flagged stub answer) and sets it as the
assistant message content.

**Stream mode.** When `content-type` is `text/plain` (or similar). The
component reads `resp.body.getReader()` and decodes chunks with a
streaming `TextDecoder`:

```javascript
const reader = resp.body.getReader();
const decoder = new TextDecoder();
while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    assistant.content += decoder.decode(value, { stream: true });
    this._scrollToBottom();
}
assistant.content += decoder.decode();  // flush trailing buffered bytes
assistant.streaming = false;
```

The `decoder.decode()` after the loop is the delta § 14.10 fix: flushes
the TextDecoder's internal buffer for any UTF-8 multi-byte sequence
split across the stream boundary. Without this, accented characters,
em-dashes, and currency symbols at the end of an answer get silently
dropped.

### The three system parameters

| Key | Effect when set | Default |
|---|---|---|
| `southbrook_hermes.sidecar_enabled` | When `true`, proxy calls sidecar. When `false`, returns JSON stub. | `false` |
| `southbrook_hermes.sidecar_url` | The base URL the proxy POSTs to (appending `/api/hermes/ask`). | `https://hermes.southbrookcabinetry.space` |
| `southbrook_hermes.jwt_secret` | HS256 signing key. Must match sidecar's `HERMES_JWT_SECRET` env var. | `PLACEHOLDER_ROTATE_BEFORE_PRODUCTION` |

The two-key gate is intentional: an admin can set the URL without
flipping enabled (preparing for deploy), or flip enabled without a
sane URL (which the proxy then catches as "URL empty" and falls back
to stub). Both must be set + truthy for the live path to actually run.

### The proxy controller (`POST /hermes/v1/ask`)

In `controllers/hermes_proxy.py`. End-to-end:

1. Parse the JSON body (`{q, order_id}`).
2. Resolve persona from `request.env.user` (lesson 13.3). 403 if
   `AccessError`; 503 if `RuntimeError`.
3. Mint JWT with `ttl=120s` (the `_JWT_TTL_FOR_ASK` constant, widened
   from the helper default per delta § 14.7).
4. Read `sidecar_enabled` + `sidecar_url` system parameters.
5. If either is unset/falsy, return a JSON stub:
   ```python
   stub_answer = (
       f"(Stub answer — sidecar not yet wired.) Question received: "
       f"'{body.get('q', '')}'.")
   return self._json({
       "stub": True, "answer": stub_answer,
       "persona": persona, "tier": tier, "jwt_iat_seen": claims["iat"],
   })
   ```
   The stub still exercises the JWT mint+verify path (the
   `jwt_iat_seen` field surfaces the verified `iat` claim so a
   developer can confirm the loop ran).
6. If both set, POST to `<sidecar_url>/api/hermes/ask` with
   `Authorization: Bearer <jwt>` and a 65s timeout (one second over
   Vercel's 60s function cap, so the proxy errors out cleanly when
   the upstream hits its limit). `stream=True` so the requests library
   doesn't buffer.
7. If the upstream HTTP call raises (`requests.RequestException`),
   return 502 `sidecar_unreachable` with the exception detail.
8. If the upstream returns non-2xx, try to JSON-decode and pass
   through the upstream error envelope. Always `upstream.close()` to
   avoid socket leaks (delta § 14.10).
9. On 2xx, stream the upstream body to the browser:
   ```python
   def generate():
       try:
           for chunk in upstream.iter_content(chunk_size=_STREAM_CHUNK):
               if chunk:
                   yield chunk
       finally:
           upstream.close()
   ```
   4 KiB chunks. The mimetype is read from the upstream's
   `Content-Type` header.

### The Vercel sidecar

The sidecar is a Next.js app at `sidecar/` (repo subdirectory). Its
three relevant routes:

> **`POST /api/hermes/ask`** — receives the JWT + question + order_id,
> runs the LLM agent loop (RAG retrieval + tool calls + streaming
> response).

> **`GET /api/hermes/tools`** — (called by the sidecar internally, not
> by Odoo) — proxies to Odoo's `/api/hermes/tools` with the same JWT
> to populate the LLM's function list. Cached per
> `tenant::persona::tier` (delta § 14.8).

> **`POST /api/hermes/conversation/log`** — (called by the sidecar
> internally at end of turn) — POSTs `{question, answer, partner_id,
> scope, project_id, order_id}` back to Odoo's
> `/api/hermes/conversation/log`, which persists as a
> `southbrook.hermes.question` record (delta § 14.6 added `order_id`
> plumbing).

The sidecar's responsibilities, in order:

1. **JWT verify** (`lib/jwt.ts`). Extract `tenant, persona,
   partner_id, tier` claims. Fail closed: missing `HERMES_JWT_SECRET`
   env var raises 503 `jwt_config` (delta § 14.9 fixed the bare
   try/catch that was swallowing this as 401 invalid_token).
2. **RAG retrieval** (`lib/rag.ts`). Top-K=5 over the per-tenant
   index in `data/index/<tenant>/index.json`. Index is built at
   sidecar deploy time from Odoo's `/southbrook/os.json`.
3. **Tool registry fetch** (`lib/tools.ts`). Hit Odoo
   `/api/hermes/tools` with same JWT, cache by
   `tenant::persona::tier`.
4. **LLM call** (`lib/ai.ts`). System prompt + persona-voice +
   RAG-injection messages + tool list → OpenAI through Vercel AI
   Gateway. Default model `openai/gpt-4o`; Gemini routable for
   long-context.
5. **Tool calls.** Each `tools.func_call` from the LLM is dispatched
   back to Odoo `/api/hermes/tools/<slug>` with the same JWT. Results
   feed back into the next LLM turn within the agent loop.
6. **Stream answer.** SSE / text stream of tokens back through the
   proxy to the OWL panel.
7. **Conversation log.** Fire-and-forget `POST
   /api/hermes/conversation/log` with the full Q+A turn.

### The agent loop budget

Vercel functions have a 60-second cap. The agent loop must fit within
that: RAG → LLM → tool → LLM → tool → LLM → stream out. The JWT TTL is
120s for slack (delta § 14.7). Realistic budget:
- RAG retrieval: 200ms.
- LLM round 1 (decide tools): 1–2s.
- Tool round-trip: 200–500ms each, often 2–4 tools per turn = 1–2s.
- LLM round 2 (synthesize): 2–4s.
- Stream out: variable, until model emits stop.

Total: typically 5–8s for a clean answer; up to ~30s for a hard
question with many tool roundtrips. >60s → Vercel kills the function;
the proxy times out at 65s and returns `sidecar_unreachable` to the
panel.

### The stub fallback

The single most important fact about the system for an admin to know:

> When `sidecar_enabled=false`, the chat panel STILL WORKS. It just
> returns a stub answer. The JWT was minted, persona was resolved, the
> auth path was exercised. The panel renders the stub message. There's
> no error — this is the intentional "before sidecar is deployed"
> mode.

This is what gives the team confidence to deploy the addon and roll
out the panel UI to users *before* the Vercel side is wired up. Users
see a "Hermes is in setup, here's a placeholder" experience rather
than a broken UI.

## Your daily flow

### As a trade partner using chat

1. Open your order in the portal.
2. Type your question in the chat panel's textarea.
3. Click **Ask** (or hit Cmd-Enter / Ctrl-Enter).
4. The assistant message starts streaming. If you see "(Stub answer
   — sidecar not yet wired.)" — the platform is in stub mode, contact
   your salesperson; the chat isn't live yet.
5. If the LLM creates a draft recommendation, the answer will say so:
   "I've queued a draft (#REC-1234)." The recommendation is now with
   your reviewer at Southbrook.
6. To ask a follow-up: type again. Each call is a fresh JWT + fresh
   tool dispatch; the conversation context is in the message history
   that the panel sends with each request (TBD — actual sidecar
   conversation memory implementation not read).

### As an admin going live with chat

The pre-flight checklist:

1. **Rotate the JWT secret.** Settings → Technical → System
   Parameters → `southbrook_hermes.jwt_secret` → set to a fresh
   high-entropy value. The placeholder `PLACEHOLDER_ROTATE_BEFORE_PRODUCTION`
   is actively rejected by the helper.
2. **Set the sidecar URL.** Settings → Technical → System Parameters
   → `southbrook_hermes.sidecar_url` → set to your Vercel project's
   production URL (e.g. `https://hermes-sidecar.vercel.app` or your
   custom domain like `https://hermes.southbrookcabinetry.space`).
3. **Deploy the sidecar.** From the repo root:
   ```bash
   cd sidecar/
   vercel link                              # once
   vercel env add HERMES_JWT_SECRET         # matches Odoo system parameter
   vercel env add OPENAI_API_KEY            # or AI Gateway credentials
   vercel env add TENANT_REGISTRY           # JSON of tenant → odoo URL
   pnpm build:rag southbrook                # builds rag index from /southbrook/os.json
   vercel deploy --prod
   ```
4. **Smoke test.** From the QNAP or your laptop:
   ```bash
   ./scripts/smoke_hermes.sh
   ```
   Exercises every Hermes route end-to-end. Green = ready to flip the
   switch.
5. **Flip the switch.** Settings → Technical → System Parameters →
   `southbrook_hermes.sidecar_enabled` → set to `true`.
6. **Verify with a real chat.** Sign in as a portal user, open an
   order, type "where is my kitchen?" — answer should NOT begin with
   "(Stub answer — sidecar not yet wired.)".

### As a developer redeploying the sidecar

When you add a new tool to `tools/`:
1. Restart the Odoo container so the decorator re-imports.
2. The new tool now appears in `GET /api/hermes/tools` from a fresh
   JWT.
3. The sidecar caches the registry by `tenant::persona::tier` — until
   you redeploy, the LLM doesn't see the new tool.
4. `cd sidecar/ && vercel deploy --prod`. The next sidecar cold start
   re-fetches the registry and the LLM gets the updated tool list.

When you change a tool's behavior (not its signature):
1. Restart Odoo. The tool now behaves differently.
2. No sidecar redeploy needed — the sidecar still calls
   `POST /api/hermes/tools/<slug>` and gets the new behavior.

When you change the RAG corpus (an `southbrook_os` section was
edited):
1. The sidecar's RAG index was built at deploy time from
   `/southbrook/os.json`. It's a snapshot.
2. To pick up new OS sections, `pnpm build:rag southbrook && vercel
   deploy --prod`.

## Common mistakes + how to recover

**"The chat panel doesn't appear at all on the Order Builder page."**

Three causes:
- The OWL bundle didn't load. Check the browser console for asset
  errors. The bundle is registered in `__manifest__.py` under
  `assets.web.assets_frontend`. If the assets bundle didn't build,
  the JS won't run.
- The mount div wasn't injected. The QWeb template
  `hermes_chat_inject_order_builder` inherits
  `southbrook_estimating_website.portal_order_builder`; if that
  parent template's XPath changed (e.g. the `o_southbrook_portal_header`
  CSS class was renamed), the XPath fails and the mount is missing.
  Check the page source for `data-hermes-chat-mount="1"`.
- The user can't see the portal page at all. Verify the partner has
  portal access and is signed in.

**"The chat returns '(Stub answer — sidecar not yet wired.)' but
`sidecar_enabled` is `true`."**

`sidecar_url` is probably empty or malformed. The proxy code:

```python
if not sidecar_enabled or not sidecar_url:
    # ... return stub
```

The `not sidecar_url` catches empty string, None, or any falsy. Check
the parameter is set to a URL with scheme (`https://...`).

**"The chat returns 502 `sidecar_unreachable`."**

The Odoo proxy couldn't reach the sidecar. Diagnose:
- `curl -I <sidecar_url>` from the Odoo container. Should return
  200 from Vercel's root.
- Check Vercel's deployment status. A failed deploy or a paused project
  returns 5xx.
- DNS issue from the container — sometimes the QNAP DNS cache poisons
  the resolution. `docker exec southbrook-odoo nslookup <sidecar_host>`.

**"The chat returns 503 `hermes_not_configured`."**

The JWT secret is either still the placeholder or PyJWT isn't
installed. Lesson 13.3 covers the fix.

**"The chat shows answers but they don't reference my actual order."**

The order_id isn't reaching the sidecar. Check:
- The mount div in the Order Builder page has
  `t-att-data-order-id="order_id or ''"`. If `order_id` is undefined
  in the template scope, the attribute is empty.
- The OWL component's `get orderId()` getter validates the value;
  malformed values become `null`.
- The OWL component sends `{q, order_id}` to `/hermes/v1/ask`. If
  `order_id` is null, the proxy passes it through but the LLM has no
  order context.

**"After a long answer, the last few characters are missing."**

You're on a sidecar build pre-delta-§14.10. The TextDecoder's flush
on stream end was added to recover UTF-8 multi-byte sequences split
across the final chunk. Update the OWL component to the post-delta
version; redeploy.

**"The sidecar timed out and I got a `sidecar_unreachable` error."**

The agent loop ran past 60s. Causes:
- LLM took too long to synthesize.
- Too many tool round-trips.
- A tool itself was slow (an Odoo query that wasn't indexed).

Diagnose by checking Vercel function logs (look for the function
that hit its time limit). Mitigation: cap the number of tool
roundtrips in the sidecar's `streamText` config; index the slow
queries; switch to a faster LLM for that turn.

**"I changed a tool but the LLM still calls the old version."**

Restart Odoo to re-import the decorator → redeploy sidecar so the
registry refreshes. Both steps required. See the "redeploying the
sidecar" daily-flow.

## What the system is doing behind the scenes

### Why the proxy lives inside Odoo, not as a direct browser-to-sidecar call

Because the JWT is minted server-side from the authenticated Odoo
session. If the browser called the sidecar directly, the browser
would need to either:
- Hold a long-lived JWT (security risk; a JWT in localStorage is
  exfiltratable by XSS).
- Mint a JWT in-browser (requires shipping the secret to the
  browser — total non-starter).

The Odoo proxy as middleman lets the browser stay unauthenticated to
the sidecar; the JWT is short-lived (120s) and minted per request from
the trusted Odoo session.

### Why streaming vs JSON content-type branch in the OWL component

The sidecar streams `text/plain` (or `text/event-stream`). The stub
returns `application/json`. Same OWL component handles both: branches
on `resp.headers.get("content-type")`. This means the component can
seamlessly handle "before sidecar deployed" (stub) and "after sidecar
deployed" (stream) without a config change.

### Why `force_send=False` in `send_spec_pdf_email` AND streaming in the chat panel

Both are about not blocking the user's request thread on external I/O.
Email goes to a cron-driven send queue (60s cadence); chat streams
chunks as they arrive. The user sees the panel respond within ~1
second even though the full answer takes 5–8s.

### Why the sidecar caches the tool registry per
`tenant::persona::tier`

A cold start refetches the registry. Subsequent warm-instance calls
reuse the cached list for the same tenant/persona/tier triple. Per
delta § 14.8, the original cache key was `tenant + last-12-chars-of-jwt`
— since each request mints a fresh JWT, the suffix was random and the
cache never warmed. The fix made the key persona+tier-based (which are
stable across requests).

### Why the conversation log carries `order_id`

Per delta § 14.6, the original schema had `project_id` but no
`sale_order_id`. The sidecar's order context was being dropped. The
fix added `sale_order_id` (Many2one) + `order_id` kwarg on
`log_conversation` + controller plumbing.

This matters for two reasons: (a) the auditor can reconstruct "the
partner was looking at order X when they asked Y"; (b) the
recommendation queue can correlate proposals to the order context.

### Why the mimetype is read from the upstream's Content-Type, not hardcoded

The sidecar might emit `text/plain` for plain text, `text/event-stream`
for SSE, or `application/json` for errors. The proxy's
`Response(generate(), mimetype=mimetype, ...)` forwards whatever the
upstream said. The OWL component then branches on the same header.
This lets the sidecar evolve (e.g. switch to SSE) without an Odoo
change.

### Why `Cache-Control: no-store` on the proxy response

The stream contains personalized data. Caching is wrong at every
layer (browser, CDN, intermediate proxy). `no-store` explicitly
prevents any cache from storing the response. Plain `no-cache` would
allow caching with revalidation, which is still wrong here.

### Why the `requests.RequestException` catch is wider than `Timeout`

Network issues come in many flavors: connection refused (sidecar
down), DNS failure, TLS handshake error, mid-stream connection reset.
All inherit from `requests.RequestException`. Catching the parent
gives a uniform `sidecar_unreachable` response for all of them.

## Quiz (5 questions, applied)

**1.** An admin sets `sidecar_url='https://hermes-sidecar.vercel.app'`
but forgets to flip `sidecar_enabled` to `true`. A trade partner
asks a question. What do they see?

> A stub answer prefixed with "(Stub answer — sidecar not yet
> wired.)" because the proxy's `if not sidecar_enabled or not
> sidecar_url:` branch fires. Both must be set + truthy for the live
> path. The JWT was still minted + verified (the response body's
> `jwt_iat_seen` confirms), so the auth path is healthy — but the
> sidecar is never called.

**2.** A developer adds a new tool, restarts Odoo, and tests with
`GET /api/hermes/tools` — the new tool appears. They open the chat
panel and ask a question that should trigger the tool. The LLM
doesn't call it. What's most likely wrong?

> The sidecar's tool registry cache is warm from before the addon
> restart. Until the next sidecar cold start (or a redeploy), the
> LLM gets the old registry. Fix: `vercel deploy --prod`. The cache
> key is `tenant::persona::tier` (delta § 14.8), and a redeploy
> forces a cold start that re-fetches the registry.

**3.** The chat panel returns 502 `sidecar_unreachable`. From the
Odoo container, `curl -I <sidecar_url>` returns 200. The Vercel
dashboard shows the deployment is "Ready." What's the next
debugging step?

> Check the Vercel function logs for the `/api/hermes/ask` route.
> The function might be returning 5xx after the network handshake
> succeeded — e.g. `jwt_config` (HERMES_JWT_SECRET unset) or
> `corpus_missing` (RAG index unbuilt). The Odoo proxy's
> `sidecar_unreachable` is for `requests.RequestException` (network
> level); a logical 5xx from the sidecar would be passed through as
> `sidecar_error`. So the question is whether you're really seeing
> `sidecar_unreachable` (network) or `sidecar_error` (5xx) — verify
> by inspecting the response body of the failure.

**4.** The trade partner sees the assistant message start to stream
("Looking up order S00…") and then the panel just stalls. No error,
no completion. What's happening?

> The streaming connection is open but no more bytes are arriving.
> Causes: (a) the sidecar's LLM call is taking too long and Vercel's
> 60s function timeout hasn't fired yet; (b) a tool call is hanging
> on the Odoo side (e.g. an unindexed query that's running for 40s);
> (c) the network path is silently stalling. Wait until the 65s
> proxy timeout fires — you'll get a `sidecar_unreachable` then.
> Check Vercel function logs and Odoo logs for the offending tool.

**5.** A developer changes the OS canonical section
`07_partner_faq.md` to add a new FAQ entry. They restart Odoo,
verify the section's `body` field is updated, and ask Fabio the new
question through the chat panel. Fabio doesn't know the new
answer. Why?

> The sidecar's RAG corpus was built at deploy time from a snapshot
> of `/southbrook/os.json`. Changing the OS section in Odoo updates
> the published JSON, but the sidecar's RAG index isn't rebuilt
> automatically. The fix is on the sidecar side: `cd sidecar/ &&
> pnpm build:rag southbrook && vercel deploy --prod`. The next
> deployment pulls the fresh corpus and indexes it. The spec § 7
> calls out a webhook-driven rebuild as a future enhancement; in
> v1.0 it's a manual step.

---

## What this lesson does NOT cover

- The recommendation queue and its state machine — lesson 13.2.
- JWT + persona + tier internals — lesson 13.3.
- The tool registry and dispatch ACL — lesson 13.4.
- The 9 read tools and 4 write tools, with their persona allowlists
  — lessons 13.5 + 13.6.
- The reviewer's daily flow (approving recommendations) — lesson 3.2.
- The CS perspective on the queue — lesson 6.3.
- Sysadmin recommendations (separate operator surface at
  hermes.odooiq.com) — lesson 7.3.
- The sidecar's internal TypeScript (`lib/jwt.ts`, `lib/rag.ts`,
  `lib/tools.ts`, `lib/ai.ts`) at file-level depth — those are
  developer-on-the-sidecar topics outside the trainee track. The
  routes consumed by Odoo (POST `/api/hermes/ask`, GET
  `/api/hermes/tools` echo, POST `/api/hermes/conversation/log`) are
  covered above.
