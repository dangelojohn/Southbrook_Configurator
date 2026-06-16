# Hermes Sidecar

Stateless inference for the Hermes trade-partner agent. Next.js on Vercel.

## What it does

1. Receives `POST /api/hermes/ask` from the Odoo proxy (`/hermes/v1/ask`).
2. Verifies the JWT signed by Odoo.
3. Retrieves top-K RAG hits from the per-tenant grounding corpus (built
   from `/southbrook/os.json` at deploy time).
4. Fetches the tool registry from Plan B1's `/api/hermes/tools`
   (cached per tenant for the lifetime of the cold start).
5. Calls OpenAI through the Vercel AI Gateway with the question, system
   prompt, RAG hits, and the tools list.
6. Dispatches each tool call back to Plan B1's
   `/api/hermes/tools/<slug>` using the same JWT.
7. Streams the synthesized answer back as SSE.
8. Logs the completed Q+A back to Odoo via
   `/api/hermes/conversation/log`.

## Deploy

```bash
vercel link                            # one time
vercel env add HERMES_JWT_SECRET       # must match Odoo's config_parameter
vercel env add OPENAI_API_KEY          # or use Vercel AI Gateway billing
vercel env add TENANT_REGISTRY         # JSON of tenant → odoo URL
pnpm build:rag southbrook              # builds data/index/southbrook/index.json
vercel deploy --prod
```

See `docs/superpowers/plans/2026-06-16-hermes-trade-partner-b2-sidecar.md`
for the full plan and `docs/superpowers/specs/2026-06-16-southbrook-os-and-hermes-platform-design.md`
for the platform design.
