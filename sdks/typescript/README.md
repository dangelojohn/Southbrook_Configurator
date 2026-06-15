# @kitchenforge/sdk (TypeScript)

Typed TypeScript client for the KitchenForge agent API — filesystem + typed
tools + Marathon telemetry — running on the Odoo 19 CE Southbrook stack.

ESM, Node 18+ (uses native `fetch`). Works in modern browsers too.

## Install

```bash
npm install @kitchenforge/sdk
# or:
pnpm add @kitchenforge/sdk
```

## Auth

Generate a per-user API key in Odoo at Settings -> Users & Companies -> API
Keys. Pass it as `apiKey` to the client; sent on every request as
`X-Api-Key`.

## Canonical 6-line "instantiate -> confirm -> release"

```ts
import { KitchenForgeClient } from "@kitchenforge/sdk";

const kf = new KitchenForgeClient({ baseUrl: "https://southbrookcabinetry.space", apiKey: "kfk-..." });
const proj = await kf.tools.instantiate({ template_id: 7, partner_id: 42, dims: { room_width_mm: 4200 } });
await kf.tools.addZone({ project_id: proj.project_id, zone: { product_id: 311, width_mm: 900 } });
await kf.tools.confirmQuote({ project_id: proj.project_id });
await kf.tools.releaseMos({ project_id: proj.project_id });
```

## Filesystem

```ts
const listing = await kf.fsGet("templates");
const quote   = await kf.fsGet(`projects/${proj.project_id}/quote.yaml`);
const etag    = await kf.fsHead(`projects/${proj.project_id}.yaml`);
await kf.fsPut(
  `projects/${proj.project_id}/zones/001-base-30.yaml`,
  { quantity: 2, dimensions_mm: { width: 762 } },
  { ifMatch: etag ?? undefined },
);
```

## Tool catalog (feed into Claude / GPT)

```ts
const catalog = await kf.tools.list();
// catalog.tools[0] = { name, description, input_schema, endpoint }
```

See `sdks/agent_examples/` for copy-pasteable Claude `tool_use` and OpenAI
function-calling bindings.

## Idempotency

Every mutating call accepts `{ idempotencyKey }` in its options. If omitted,
the SDK auto-generates a UUID v4 per call. The server caches the response
under `(api_key_hash, idempotency_key)` so retrying with the same key is safe.

## Errors

All non-2xx responses throw:

- `NotFoundError` (404)
- `PreconditionFailedError` (409 / 412 — ETag mismatch)
- `ApiError` (everything else; has `.status`, `.code`, `.details`)

## Build

```bash
npm install
npm run build  # tsc -> dist/
```
