# Hermes Trade-Partner v1 — Plan B2 (Vercel sidecar + OWL chat panel)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Stand up the Next.js + Vercel sidecar that closes the loop end-to-end: trade partner asks a question in the Order Builder → Odoo proxy mints a JWT → sidecar pulls the tool registry once at boot, RAG-retrieves over the Southbrook OS corpus, calls OpenAI through the Vercel AI Gateway, dispatches tool calls back to Plan B1's `/api/hermes/tools/<slug>`, streams the answer back via SSE → OWL chat panel renders it. After B2, "where is my kitchen?" works.

**Architecture:** Sidecar lives under `sidecar/` inside this repo for v1 simplicity (can be extracted to a sibling repo `hermes-sidecar` once v1.x multi-tenant work begins — per the spec § 12 open question). Next.js App Router, Node runtime, AI SDK 5 (`ai`, `@ai-sdk/openai`), AI Gateway. RAG corpus is built at deploy time from `https://southbrookcabinetry.space/southbrook/os.json` using `text-embedding-3-small`. JWT verification uses the same HS256 secret as Plan B1 (set via `HERMES_JWT_SECRET` env var on Vercel; must match `southbrook_hermes.jwt_secret` in Odoo). The OWL chat panel is delivered as a new asset bundle inside `southbrook_hermes` that mounts on the Order Builder route — same persona-native surface the spec § 2.2 calls for.

**Tech Stack:** Next.js 15 App Router, TypeScript, Node.js 20+ runtime, `ai` SDK 5, `@ai-sdk/openai`, Vercel AI Gateway, jose (for JWT verify in Node), pnpm. OWL 2 (Odoo's reactive framework), SCSS.

**Reference:** Spec `docs/superpowers/specs/2026-06-16-southbrook-os-and-hermes-platform-design.md` §2.3, §3, §4, §6, §7. Plan B1 `docs/superpowers/plans/2026-06-16-hermes-trade-partner-b1-odoo.md`.

**Operational prerequisites** (one-time setup the human runs before any of this is live):
- Install PyJWT in `southbrook-odoo` container (`docker exec ... pip install PyJWT`)
- Rotate `southbrook_hermes.jwt_secret` from `PLACEHOLDER_ROTATE_BEFORE_PRODUCTION` to a real 32+ hex secret
- Mirror that same secret to Vercel as `HERMES_JWT_SECRET`
- Provision OpenAI API access via Vercel AI Gateway (key in `AI_GATEWAY_KEY` or use Vercel project's built-in auth)

---

## File structure

```
sidecar/                                     NEW — sibling-extractable later
├── package.json                             pnpm; ai + @ai-sdk/openai + jose
├── tsconfig.json
├── next.config.ts
├── vercel.json                              Node runtime + AI Gateway config
├── .env.example                             HERMES_JWT_SECRET, AI_GATEWAY_KEY, OPENAI_API_KEY, TENANT_REGISTRY
├── app/
│   └── api/hermes/
│       ├── ask/route.ts                     POST /api/hermes/ask — SSE
│       └── conversation/log/route.ts        POST /api/hermes/conversation/log — outbound to Odoo
├── lib/
│   ├── jwt.ts                               verifyJwt(token, secret) → claims | null
│   ├── tenants.ts                           tenantRegistry: tenant → odoo base URL
│   ├── rag.ts                               retrieveTopK(query, tenant, k) — cosine over index.json
│   ├── tools.ts                             fetchToolRegistry(tenant), callTool(tenant, slug, args, jwt)
│   ├── prompts.ts                           system + persona-voice + RAG injection prompt
│   ├── ai.ts                                AI Gateway client (gpt-4o default, fallback gemini-2.5-flash)
│   └── log.ts                               structured logging wrapper
├── scripts/
│   ├── build-rag.ts                         pnpm build:rag <tenant> — fetches OS doc, embeds, writes index
│   └── verify-config.ts                     pnpm verify — sanity-check env vars before deploy
├── data/
│   ├── grounding/                           per-tenant raw corpus (markdown)
│   │   └── southbrook/                      copied from /southbrook/os.json
│   └── index/                               per-tenant vector index (JSON)
│       └── southbrook/index.json
└── README.md                                ops runbook

addons/southbrook_hermes/                    EXTEND
├── __manifest__.py                          bump to 19.0.3.0.0, add asset bundle
├── static/src/components/hermes_chat/       NEW
│   ├── hermes_chat.esm.js                   OWL component, SSE consumer
│   ├── hermes_chat.xml                      QWeb template
│   └── hermes_chat.scss                     SCSS tokens
└── views/order_builder_chat_inject.xml      NEW — adds chat container to Order Builder route
```

---

## Tasks

### Task 1: Scaffold the Next.js sidecar

**Files:**
- Create: `sidecar/package.json`, `tsconfig.json`, `next.config.ts`, `vercel.json`, `.env.example`, `README.md`
- Create: `sidecar/app/api/hermes/ask/route.ts` (placeholder)
- Create: `sidecar/.gitignore`

- [ ] **Step 1: Scaffold via pnpm.**

```bash
mkdir -p sidecar && cd sidecar
cat > package.json <<'EOF'
{
  "name": "hermes-sidecar",
  "version": "0.1.0",
  "private": true,
  "scripts": {
    "dev": "next dev -p 3001",
    "build": "next build",
    "start": "next start",
    "build:rag": "tsx scripts/build-rag.ts",
    "verify": "tsx scripts/verify-config.ts",
    "typecheck": "tsc --noEmit"
  },
  "dependencies": {
    "ai": "^5.0.0",
    "@ai-sdk/openai": "^2.0.0",
    "@ai-sdk/google": "^2.0.0",
    "jose": "^5.9.0",
    "next": "^15.0.0",
    "react": "^19.0.0",
    "react-dom": "^19.0.0",
    "zod": "^3.23.0"
  },
  "devDependencies": {
    "@types/node": "^22.0.0",
    "@types/react": "^19.0.0",
    "tsx": "^4.0.0",
    "typescript": "^5.6.0"
  }
}
EOF
```

- [ ] **Step 2: TypeScript + Next.js + Vercel config.**

```typescript
// sidecar/tsconfig.json
{
  "compilerOptions": {
    "target": "ES2022",
    "lib": ["dom", "dom.iterable", "ES2022"],
    "module": "esnext",
    "moduleResolution": "bundler",
    "strict": true,
    "skipLibCheck": true,
    "jsx": "preserve",
    "incremental": true,
    "esModuleInterop": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "plugins": [{"name": "next"}],
    "paths": {"@/*": ["./*"]}
  },
  "include": ["next-env.d.ts", "**/*.ts", "**/*.tsx"],
  "exclude": ["node_modules"]
}
```

```typescript
// sidecar/next.config.ts
import type { NextConfig } from "next";
const config: NextConfig = {
  experimental: { serverActions: { allowedOrigins: ["southbrookcabinetry.space"] } },
};
export default config;
```

```json
// sidecar/vercel.json
{
  "functions": {
    "app/api/hermes/ask/route.ts": { "runtime": "nodejs20.x", "maxDuration": 60 },
    "app/api/hermes/conversation/log/route.ts": { "runtime": "nodejs20.x", "maxDuration": 10 }
  }
}
```

- [ ] **Step 3: .env.example with every var documented inline.**

```bash
# sidecar/.env.example
# Must match Odoo's southbrook_hermes.jwt_secret config_parameter
HERMES_JWT_SECRET=

# Vercel AI Gateway — provisioned per Vercel project
AI_GATEWAY_KEY=

# Direct OpenAI fallback (used if Gateway is misconfigured)
OPENAI_API_KEY=

# Per-tenant Odoo base URL — JSON-encoded
# Example: {"southbrook":"https://southbrookcabinetry.space"}
TENANT_REGISTRY={"southbrook":"https://southbrookcabinetry.space"}

# Defaults to gpt-4o for the main agent loop. Override per request.
DEFAULT_MODEL=openai/gpt-4o
LONG_CONTEXT_MODEL=google/gemini-2.5-flash
```

- [ ] **Step 4: .gitignore.**

```
node_modules/
.next/
.vercel/
*.log
.env.local
data/index/*/index.json
```

- [ ] **Step 5: Placeholder route + README ops runbook.**

```typescript
// sidecar/app/api/hermes/ask/route.ts
export async function POST(): Promise<Response> {
  return Response.json({ stub: true, message: "Sidecar scaffolded; not wired yet." });
}
```

```markdown
<!-- sidecar/README.md -->
# Hermes Sidecar

Stateless inference for the Hermes trade-partner agent. Runs on Vercel.

## Deploy
1. `vercel link` (one time, picks/creates a project)
2. `vercel env add HERMES_JWT_SECRET` (must match Odoo's config_parameter)
3. `vercel env add OPENAI_API_KEY`
4. `pnpm build:rag southbrook` (builds the RAG index)
5. `vercel deploy` (preview) or `vercel deploy --prod`

See `docs/superpowers/plans/2026-06-16-hermes-trade-partner-b2-sidecar.md` for full context.
```

- [ ] **Step 6: Commit.**

```bash
git add sidecar/
git commit -m "feat(sidecar): scaffold Next.js + Vercel sidecar skeleton"
```

---

### Task 2: JWT verify + tenant registry libs

**Files:**
- Create: `sidecar/lib/jwt.ts`
- Create: `sidecar/lib/tenants.ts`
- Create: `sidecar/lib/types.ts`

- [ ] Implement `verifyJwt(token, secret) → claims | null` using `jose.jwtVerify` with HS256. Return shape `{ tenant, persona, partner_id, tier, order_id?, iat, exp }`.

- [ ] Implement `loadTenantRegistry()` reading `TENANT_REGISTRY` env JSON. Export `getOdooUrl(tenant)` and `isKnownTenant(tenant)`.

- [ ] Shared types — `Claims`, `ToolDef`, `ToolResult`, `OsSection`, `RagHit`.

- [ ] Commit: `feat(sidecar): JWT verify + tenant registry libs + shared types`

---

### Task 3: RAG indexer (`scripts/build-rag.ts`)

**Files:**
- Create: `sidecar/scripts/build-rag.ts`
- Create: `sidecar/data/grounding/.gitkeep`
- Create: `sidecar/data/index/.gitkeep`

- [ ] Fetch the OS bundle from each tenant's Odoo (`GET /southbrook/os.json`).

- [ ] Chunk each section's body (rough 600-token windows with 100-token overlap; keep section slug + name as metadata on every chunk).

- [ ] Embed each chunk with `openai.embedding('text-embedding-3-small')` (1536 dims). Use the AI SDK's `embed` function from `ai`.

- [ ] Write `data/index/<tenant>/index.json` with shape: `{tenant, build_hash, built_at, chunks: [{slug, name, ord, text, embedding}]}`.

- [ ] Sanity assertion: every chunk has 1536-dim vector + non-empty text.

- [ ] Commit: `feat(sidecar): build-rag CLI — fetch OS, chunk, embed, persist index`

---

### Task 4: RAG retrieval lib

**Files:**
- Create: `sidecar/lib/rag.ts`

- [ ] Cache the index per tenant in module-level memory at first use (reloaded on each cold start; that's fine for v1).

- [ ] `retrieveTopK(tenant, query, k=5)` — embeds the query with the same embedding model, cosine-similarity over chunk vectors, returns top K with their text + section metadata.

- [ ] Commit: `feat(sidecar): RAG retrieval over flat per-tenant index`

---

### Task 5: Tools lib (Odoo callbacks)

**Files:**
- Create: `sidecar/lib/tools.ts`

- [ ] `fetchToolRegistry(tenant, jwt)` — `GET ${getOdooUrl(tenant)}/api/hermes/tools` with Bearer JWT. Cache in memory keyed by tenant for the lifetime of the cold start.

- [ ] `callTool(tenant, slug, args, jwt)` — `POST ${getOdooUrl(tenant)}/api/hermes/tools/${slug}` with body `JSON.stringify(args)`. Handle 401/403/404/500/503 — return `{ok: false, error}` to the LLM rather than throwing.

- [ ] Convert each `ToolDef` from the Odoo registry into the AI SDK tool shape: `{description, inputSchema (zod-derived from JSON schema), execute}`.

- [ ] Commit: `feat(sidecar): tool registry pull + dispatch over JWT`

---

### Task 6: Prompts lib

**Files:**
- Create: `sidecar/lib/prompts.ts`

- [ ] `buildSystemPrompt(persona, tenant)` — persona-specific voice (trade partner = warm, terse, never promises pricing). Includes the citation rule: "If you don't have a tool result or RAG hit for a claim, say you don't know."

- [ ] `injectRagHits(messages, hits)` — prepends a system message listing the top-K snippets verbatim with their slug + section name as citations.

- [ ] Commit: `feat(sidecar): persona-voice system prompts + RAG injection helper`

---

### Task 7: AI Gateway client + main `/api/hermes/ask` route

**Files:**
- Create: `sidecar/lib/ai.ts`
- Modify: `sidecar/app/api/hermes/ask/route.ts`

- [ ] `lib/ai.ts` — exports `getModel(intent: "default" | "long_context")` returning a model via the AI Gateway. Defaults to `openai/gpt-4o`. Override via env `DEFAULT_MODEL` / `LONG_CONTEXT_MODEL`.

- [ ] `app/api/hermes/ask/route.ts`:
  - Verify JWT from `Authorization: Bearer`.
  - Parse `{q, order_id?}` from body.
  - Retrieve top-5 RAG hits for the question.
  - Fetch tool registry filtered by persona+tier (cached per tenant).
  - Build system prompt + RAG injection + user message.
  - Call `streamText({ model: getModel("default"), messages, tools, maxToolRoundtrips: 5 })` from the AI SDK.
  - Stream the result back to the client as SSE.
  - On final answer, POST to `/api/hermes/conversation/log` (fire-and-forget) so Odoo persists Q+A.

- [ ] Commit: `feat(sidecar): /api/hermes/ask — RAG + tools + streamed answer via AI Gateway`

---

### Task 8: `/api/hermes/conversation/log` outbound

**Files:**
- Create: `sidecar/app/api/hermes/conversation/log/route.ts`

- [ ] Receives the same JWT, forwards `{question, answer, scope, project_id?}` to Odoo's `/api/hermes/conversation/log`. Return Odoo's response verbatim.

- [ ] Commit: `feat(sidecar): /api/hermes/conversation/log proxy back to Odoo`

---

### Task 9: OWL chat panel — component

**Files:**
- Create: `addons/southbrook_hermes/static/src/components/hermes_chat/hermes_chat.esm.js`
- Create: `addons/southbrook_hermes/static/src/components/hermes_chat/hermes_chat.xml`
- Create: `addons/southbrook_hermes/static/src/components/hermes_chat/hermes_chat.scss`

- [ ] OWL 2 component with props `orderId?: number`. Internal state: `messages` array of `{role: "user" | "assistant", content: string, streaming: boolean}`. Method `submit(q)` POSTs to `/hermes/v1/ask` with `{q, order_id}` and consumes the SSE stream.

- [ ] QWeb template: minimal — chat-list scrollable area, textarea, "Ask Hermes" submit button. Styling token-matches the existing Southbrook design tokens.

- [ ] Commit: `feat(hermes): OWL chat panel component`

---

### Task 10: OWL chat panel — wire into Order Builder

**Files:**
- Modify: `addons/southbrook_hermes/__manifest__.py` (add asset bundle entry)
- Create: `addons/southbrook_hermes/views/order_builder_chat_inject.xml`

- [ ] Add asset bundle `web.assets_frontend` entry registering the OWL JS+XML+SCSS.

- [ ] XPath inject a `<div t-att-data-order-id="…"/>` mount point into the Order Builder portal template that already exists in `southbrook_estimating_website`. The OWL component reads the mount's `data-order-id` and renders into it.

- [ ] Commit: `feat(hermes): wire HermesChat into Order Builder portal page`

---

### Task 11: Local end-to-end smoke

**Files:** none.

- [ ] `pnpm verify` — confirms env vars are all set locally.
- [ ] `pnpm build:rag southbrook` — builds the index from prod's `/southbrook/os.json`.
- [ ] `pnpm dev` — start sidecar on :3001.
- [ ] Mint a JWT via `odoo shell` (per Plan B1 Task 10 procedure) and curl `POST http://localhost:3001/api/hermes/ask` with `{"q": "where is my kitchen?"}`. Expect a streamed answer that cites at least one tool result + at least one RAG snippet.

- [ ] If anything's broken, fix it. If it's working, commit.

- [ ] Commit: `chore(sidecar): local smoke test passes against prod Odoo`

---

### Task 12: Deploy sidecar to Vercel + production smoke

**Files:** none (deploys are CLI invocations).

- [ ] `vercel link` — pick/create a project (suggested name: `hermes-sidecar`).
- [ ] `vercel env add HERMES_JWT_SECRET` (must match Odoo's `southbrook_hermes.jwt_secret`).
- [ ] `vercel env add OPENAI_API_KEY` (or use Vercel project AI Gateway billing).
- [ ] `vercel env add TENANT_REGISTRY` (paste JSON: `{"southbrook":"https://southbrookcabinetry.space"}`).
- [ ] `vercel deploy --prod`.

- [ ] In Odoo, set `southbrook_hermes.sidecar_url` config param to the new production sidecar URL.

- [ ] Replace Plan B1's stub in `controllers/hermes_proxy.py` to actually POST to the sidecar (this is a small follow-up — the proxy currently returns the stub answer locally). Implementer rewires it:
  - Read `southbrook_hermes.sidecar_url` from config.
  - POST `{q, order_id}` + the minted JWT as `Authorization: Bearer`.
  - Stream the upstream SSE response straight back to the browser.

- [ ] Smoke test the full chain: log in as `Demo Tradesperson (Tier 3)`, open the Order Builder, click Hermes panel, ask "where is my kitchen?" — expect a grounded answer back inside 10s.

- [ ] Commit: `feat(sidecar): wire Odoo proxy to live sidecar, smoke test passing`

---

## Self-review

**Spec coverage:**
- §2.3 sidecar: Tasks 1–8 cover scaffold, JWT, RAG, tools, prompts, AI Gateway, `/ask`, `/conversation/log`.
- §3 data flow: Task 7's main loop implements the 10-step diagram (verify JWT → load RAG → retrieve → fetch registry → call LLM → tool calls back through Plan B1 → stream → log).
- §6 tool catalog: consumed via Task 5's registry pull; no new tools defined.
- §7 RAG corpus: Task 3 builds it from Plan A's public endpoint — exactly the boundary §7 specifies.
- §4 personas + tiers: enforced server-side by Plan B1's tools-API (Task 8 in B1); B2 just trusts the JWT's claims.

**Out of scope for B2:**
- Vector DB — flat per-tenant `index.json` on Vercel disk; revisit at 10× corpus growth.
- Image / file uploads in chat (spec § 11 non-goal).
- Multi-language (English only).
- Sales-rep + mfg-manager surfaces (v1.1, v1.2 — separate plans).

**Operational gates** (must be done by a human; sidecar code can't):
- PyJWT in container or PyJWT in Dockerfile.
- Rotate `southbrook_hermes.jwt_secret` from placeholder.
- Mirror that secret to Vercel as `HERMES_JWT_SECRET`.
- Provision OpenAI / AI Gateway access for the Vercel project.

**Multi-tenant readiness:** all tenant-specific data (Odoo URL, RAG index, grounding corpus) keys off the JWT's `tenant` claim. Adding Porterly = `pnpm build:rag porterly` + env var update + deploy. No code change.
