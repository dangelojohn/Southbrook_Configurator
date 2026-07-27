---
course: 9 — ProductGraph
chapter: 9.5
title: The MCP Sidecar — LLM Access to ProductGraph
duration: 35 minutes
audience: Developer building agents against the catalog + IT admin running the sidecar container
prereqs: Lesson 9.1 (overview), Lesson 9.2 (property templates), Lesson 9.4 (EBOMs)
custom_modules: standalone Python service in ~/product_graph_v19/mcp/; Odoo-side it depends on the 5 product_graph_* addons
---

# The MCP Sidecar — LLM Access to ProductGraph

## Who this lesson is for

You are either (a) a developer wiring Claude (or another MCP-compatible
agent) to query and mutate the engineering catalog, or (b) an IT admin
keeping the `product-graph-mcp` container alive on the QNAP stack.
Either way, this lesson is about a service that runs **next to Odoo,
not inside it** — talks Model Context Protocol (Anthropic's tool-calling
standard) on one end, talks XML-RPC to Odoo on the other, enforces
authentication and authorisation in two layers.

This lesson is entirely on the **standalone ProductGraph platform**
side. The sidecar lives at `~/product_graph_v19/mcp/`. The Southbrook
bridge addon is unaware of the sidecar's existence; the sidecar talks
to Odoo via XML-RPC like any other API client.

## Where this lives on the site

The sidecar is **not** an Odoo menu. It's a container.

- **Code**: `~/product_graph_v19/mcp/src/product_graph_mcp/`
- **Container on the QNAP**: `product-graph-mcp`, joined to the
  `alfacore-caddy` Docker network alongside `southbrook-odoo` and
  `alfacore-caddy`.
- **Endpoint**: SSE (Server-Sent Events) on internal port `9234`,
  fronted by Cloudflared with Zero-Trust on the public hostname.
- **For local development (Claude Desktop)**: stdio transport — the
  agent spawns the sidecar as a subprocess.

What Claude/your agent sees: a list of tools (around 30 across 12
categories) exposed via the MCP `list_tools` RPC and called via
`call_tool`.

## What your screen shows

There are no screens. There are three readable artefacts:

**1. The tool registry (`server.py`).**

```python
TOOL_REGISTRY = [
    *catalog.TOOLS,
    *bom.TOOLS,
    *revision_tools.TOOLS,
    *document.TOOLS,
    *release.TOOLS,
    *vendor.TOOLS,
    *eco.TOOLS,
    *rfq.TOOLS,
    *relationship.TOOLS,
    *cad.TOOLS,
    *procurement.TOOLS,
]
```

Twelve modules under `mcp/src/product_graph_mcp/tools/`, each exposes
a `TOOLS = [...]` list of dicts shaped:

```python
{
    "name": "list_items",
    "description": "List engineering items …",
    "input_schema": {...},   # JSON Schema
    "handler": callable,
    "mutating": bool,        # default False
}
```

A sample of what's there (see `mcp/README.md` for the full list):

| Tool | Mutating | Purpose |
|---|---|---|
| `list_items` | no | List `pg.item` records by state/type/category |
| `get_item` | no | One item by part_number, with revision list |
| `search_catalog` | no | Free-text over `part_number` and `name` |
| `where_used` | no | Parent EBOMs of an item from the materialised closure |
| `bom_explode` | no | Multi-level flat explosion of an EBOM |
| `validate_ebom` | no | Pre-release validation report |
| `simulate_release` | no | Dry-run of a release — errors/warnings, no side effects |
| `get_release` | no | Inspect a `pg.release` record |
| `propose_revision` | **yes** | Create new draft revision against an item |
| `comment_on_revision` | **yes** | Chatter note on a revision |
| `attach_document` | **yes** | Upload binary to a revision |
| `vendor_for_item` | no | AVL — approved sources for a part |

**2. The config (`config.py`).**

A frozen dataclass loaded from environment variables — single source
of truth, no other module reads `os.environ`:

```env
PRODUCTGRAPH_ODOO_URL=https://southbrookcabinetry.space
PRODUCTGRAPH_DB=southbrook
PRODUCTGRAPH_ODOO_USER=mcp-bot@southbrookcabinetry.local
PRODUCTGRAPH_API_KEY=<personal API key>
PRODUCTGRAPH_MCP_TRANSPORT=sse        # or 'stdio' for desktop
PRODUCTGRAPH_MCP_HOST=0.0.0.0
PRODUCTGRAPH_MCP_PORT=9234
PRODUCTGRAPH_DEFAULT_LIMIT=50
PRODUCTGRAPH_MAX_LIMIT=500
PRODUCTGRAPH_LOG_LEVEL=INFO
```

If any required var is missing the process exits with `SystemExit`
rather than running with bad config.

**3. The XML-RPC client (`odoo_client.py`).**

A thread-local connection-per-thread wrapper around
`xmlrpc.client.ServerProxy`. Authenticates once via `common.authenticate`
with `(db, user, api_key)`, caches the resulting `uid`, executes every
subsequent call via `object.execute_kw` with the same `(db, uid,
api_key)` tuple.

Two public methods that the per-tool group check goes through:

- `has_group(xml_id)` — returns whether `mcp-bot` is in the named group.
- `require_group(xml_id)` — raises `PermissionError` if not. Called by
  the dispatcher (see below) for every `mutating=True` tool.

## Your daily flow

**1. Add a new tool (developer).**

- Open `mcp/src/product_graph_mcp/tools/<category>.py`.
- Write a handler function: `def my_tool(odoo: OdooClient, config:
  Config, args: dict) -> dict`. Use `odoo.search_read`,
  `odoo.call_method` etc. Never call `os.environ` or import outside
  the module.
- Append a dict to that file's `TOOLS = [...]` list with
  `name / description / input_schema / handler / mutating`.
- If mutating, also re-check the group inside the handler (defense in
  depth — `odoo.require_group("product_graph_base.group_pg_engineer")`).
- Restart the container. Claude (or whoever) will see the new tool on
  the next `list_tools` call.

**2. Run locally for development.**

```bash
cd ~/product_graph_v19/mcp/
pip install -e .
PRODUCTGRAPH_MCP_TRANSPORT=stdio product-graph-mcp
```

For Claude Desktop, wire it into
`~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "product-graph": {
      "command": "product-graph-mcp",
      "env": {
        "PRODUCTGRAPH_ODOO_URL": "https://southbrookcabinetry.space",
        "PRODUCTGRAPH_DB": "southbrook",
        "PRODUCTGRAPH_ODOO_USER": "mcp-bot@southbrookcabinetry.local",
        "PRODUCTGRAPH_API_KEY": "..."
      }
    }
  }
}
```

**3. Deploy to the QNAP (admin).**

```bash
cd ~/product_graph_v19/mcp/
docker build -t product-graph-mcp:0.1.0 .
docker compose up -d
```

The container joins `alfacore-caddy` external network. SSE listens on
9234, exposed internally only. Public ingress is via cloudflared with
Zero-Trust on a hostname like
`mcp.productgraph.southbrook.example.com`.

**4. Rotate the API key (admin, every ~5 years).**

- Log into Odoo as the `mcp-bot` service user.
- **My Profile → Account Security → New API Key.** Set the
  duration close to 5 years (1825 days) — that's the cap raised by the
  bridge's install data (`southbrook_plm_productgraph/data/api_key_policy.xml`).
- Copy the key, put it into the container's `.env`, restart the
  container: `docker compose restart product-graph-mcp`.
- The cached `uid` re-authenticates on the next call.

## The auth model (Decision D6)

Three layers, defense in depth:

**Layer 1 — Cloudflared Zero-Trust on the public route.** Before the
request even reaches the container, Cloudflared enforces the Zero-Trust
policy you defined (typically: Google Workspace identity, restricted to
`@southbrookcabinetry.com` domain). OAuth2 device flow is explicitly
out of scope for Phase 1; Zero-Trust is the gate.

**Layer 2 — Odoo personal API key.** The XML-RPC client authenticates
with `(db, mcp-bot user, api_key)`. The key is a personal API key on
the `mcp-bot@southbrookcabinetry.local` user. The user has the
`group_pg_engineer` membership at minimum.

**Layer 3 — Per-tool group check at the call site.** Every tool with
`mutating=True` triggers `odoo.require_group(
"product_graph_base.group_pg_engineer")` before the handler runs:

```python
if spec.get("mutating"):
    odoo.require_group("product_graph_base.group_pg_engineer")
result = spec["handler"](odoo, config, arguments)
```

This is the boundary check, called at the dispatcher level. If the
operating user's groups change (e.g. demotion) the change takes effect
on the very next call without restarting the sidecar — because
`has_group` is a fresh XML-RPC call to `res.users.has_group` each time.

Why three layers? Because layer 1 protects the route, layer 2 protects
the database, and layer 3 protects the *intent*: a misconfigured user
who somehow has API access but no engineer role still can't mutate
records through the sidecar. The boundary is at the tool, not at the
network.

## Rate limiting

Phase 1 does **not** include a per-user rate limiter inside the
sidecar. The pacing constraints come from three places:

- **Cloudflared.** You can set Zero-Trust rate limits at the route
  level. Recommended: 60 req/min for an interactive agent, 600 req/min
  for a batch agent — tune per use case.
- **Odoo's own session.** Odoo throttles at the worker level. A flood
  from one agent will manifest as `502` / `504` from Odoo before it
  saturates the sidecar.
- **MCP tool limits.** Read tools accept `limit` and `offset`
  parameters; `limit` is clamped against `PRODUCTGRAPH_MAX_LIMIT`
  (default 500). An agent asking for `limit=99999` gets 500.

If you need true sidecar-level rate limiting, that's a Phase 2 ask.
File a ticket with the expected per-token-per-minute envelope.

## Audit logging

There are three audit trails relevant to the sidecar:

**1. Sidecar stdout/stderr (the container log).** Every tool call logs
`Tool <name> failed` on exception with full traceback. Routine success
calls don't log unless `PRODUCTGRAPH_LOG_LEVEL=DEBUG`.

**2. Odoo `pg.audit.log`.** Every mutation that lands as a state
transition on `pg.item`/`pg.revision`/`pg.ebom`/`pg.release`/`pg.vendor`
writes a row, with `user_id = mcp-bot`. This is the same audit table
human users write to — there is no special "MCP" tag. If you want to
trace what an agent did vs what John did, filter on
`user_id = mcp-bot.id`.

**3. Cloudflared logs.** Per-request, per-identity. Connects the
`pg.audit.log` row (`mcp-bot` did it) to the upstream identity (who
was driving the agent at the time).

The triangle: Cloudflared knows the human, Odoo knows the service
account, sidecar logs connect the tool call to the response. There is
no single dashboard combining the three in Phase 1 — that's another
Phase 2 ask.

## Common mistakes + how to recover

**"The container won't start — `Required environment variable
PRODUCTGRAPH_API_KEY is missing`."**

`Config.from_env` exits if any of `ODOO_URL`, `DB`, `ODOO_USER`,
`API_KEY` are missing. Check `.env` is loaded by docker-compose
(`env_file: ./.env` in `docker-compose.yml`).

**"All my mutating tools return `{error: 'permission_denied',
message: 'User mcp-bot lacks required group …'}`."**

The `mcp-bot` user is not in `product_graph_base.group_pg_engineer`.
Add them via Settings → Users → mcp-bot → Groups → tick "ProductGraph
/ Engineer". Or grant the engineer-or-above bundle via the access
groups XML.

**"My `propose_revision` call returns `{error: 'change_summary
required (min 10 chars)'}` but I passed 9 chars."**

The validation is sidecar-side, in the handler. 10-char minimum is
the contract — pad your change summary or expand it.

**"The list-tools response is empty after I added a new tool."**

You restarted the container, right? `TOOL_REGISTRY` is built at module
load. A live process won't pick up changes to `TOOLS = [...]` without
reload.

**"An MCP call hangs for 30 seconds then times out."**

The sidecar's XML-RPC call is synchronous; if Odoo is slow (worker
saturation, slow query, contended row lock) the sidecar blocks. Check
the Odoo worker logs first. The sidecar itself has no SLA budget;
Phase 1 trusts Odoo's own response time.

**"I rotated the API key but `docker compose restart` left the old key
cached somewhere."**

The cached `uid` is in-process — restart clears it. But check whether
the OLD key is still valid in Odoo (it might be — Odoo doesn't
auto-revoke keys, you have to delete the row from My Profile → Account
Security explicitly). If both old and new are valid, the sidecar will
keep using the env-var key (the new one); the old one is dead weight,
delete it from Odoo.

## What the system is doing behind the scenes

The dispatcher (`_call_tool` in `server.py`) is the single chokepoint
for every MCP call:

```python
@server.call_tool()
async def _call_tool(name: str, arguments: dict | None) -> list[TextContent]:
    arguments = arguments or {}
    spec = next((t for t in TOOL_REGISTRY if t["name"] == name), None)
    if spec is None:
        return [TextContent(type="text", text=json.dumps({
            "error": f"Unknown tool: {name}",
        }))]
    try:
        if spec.get("mutating"):
            odoo.require_group("product_graph_base.group_pg_engineer")
        result = spec["handler"](odoo, config, arguments)
        payload = json.dumps(result, default=str, indent=2)
        return [TextContent(type="text", text=payload)]
    except PermissionError as e:
        return [TextContent(type="text", text=json.dumps({
            "error": "permission_denied",
            "message": str(e),
        }))]
    except Exception as e:
        log.exception("Tool %s failed", name)
        return [TextContent(type="text", text=json.dumps({
            "error": "tool_error",
            "tool": name,
            "message": str(e),
        }))]
```

Three error shapes, exactly:

- Unknown tool → `{error: "Unknown tool: …"}`.
- Permission denied (group missing) → `{error: "permission_denied",
  message: …}`.
- Any other exception → `{error: "tool_error", tool: …, message: …}`.

Tool handlers return plain Python dicts; the dispatcher JSON-encodes
them with `default=str` (so dates and IDs serialise). The agent
receives one `TextContent` block per tool call.

**Why XML-RPC and not REST?** Decision: the sidecar can talk to an
Odoo deployment that has only `base/revision/ebom/release` installed,
WITHOUT `product_graph_api` (the REST module). This keeps the REST
addon an *optional* extra.

**Why stdio and SSE both?** stdio is for Claude Desktop and other
local agents (the client spawns the sidecar as a subprocess). SSE is
for remote agents going through Cloudflared. Same `TOOL_REGISTRY`, same
handlers — `Config.transport` switches the binding.

**Why `mutating=True` is a contract, not just a flag.** A tool marked
mutating tells the dispatcher to do the group check AND tells the agent
(via the JSON Schema descriptions) that this is a write operation —
LLM safety policies typically require user confirmation before
invoking write tools. If your tool changes state, mark it mutating.
Forgetting to mark mutates as mutating is a bug; the test suite
(`tests/test_tool_metadata.py` in the sidecar) flags it.

## Quiz (5 questions, applied)

**1.** An agent calls `propose_revision` with
`{item_id: 42, change_summary: "fix"}`. What's the response?

> `{error: "change_summary required (min 10 chars)"}`. The handler
> validates length before any XML-RPC call. No revision is created; no
> audit row written. The agent should retry with a longer summary
> (≥10 chars), e.g. "Fix the hinge spec — minor rework."

**2.** You rotate the API key but forget to restart the container.
Subsequent calls fail. Why might calls still succeed for the first
30 seconds?

> The cached `uid` from the previous authentication is still in
> memory. Odoo's `object.execute_kw` accepts `(db, uid, api_key)` —
> as long as the **api_key** is valid, the call succeeds. If you
> deleted the old key from Odoo's My Profile → Account Security, the
> very next call fails. If you only minted a new one and didn't
> delete the old, calls keep succeeding with the old key until you
> restart the container and the new env-var key takes effect.

**3.** The sidecar returns
`{error: "permission_denied", message: "User mcp-bot lacks required
group product_graph_base.group_pg_engineer."}`. The IT admin checks
the user record and sees they ARE in the engineer group. What changed?

> Two possibilities. (a) The XML-RPC user is not actually `mcp-bot` —
> the env var `PRODUCTGRAPH_ODOO_USER` might point at a different
> login (e.g. an old `mcp-service@…` account that was demoted). Check
> the running container's env. (b) The `has_group` call hits a
> permissions-cache invalidation issue — restart the Odoo worker
> serving the request, or wait for the cache to age out. The sidecar
> itself caches nothing per-call; the answer comes fresh from Odoo.

**4.** You want to add a `bulk_propose_revisions` tool that takes a
list of `{item_id, change_summary}` and creates revisions for all of
them. What two design rules apply?

> (a) Mark it `mutating=True` so the dispatcher enforces
> `group_pg_engineer`. (b) Decide on per-item atomicity — either each
> revision is its own XML-RPC call (some succeed, some fail), or you
> batch them server-side via a custom Odoo method that runs in one
> transaction. Phase 1 sidecar tools are individual XML-RPC calls; if
> you need true atomicity, write the server method first in
> `product_graph_revision` and call it from the tool.

**5.** A junior dev adds a new tool `delete_item` that calls
`pg.item.unlink()`. Tests pass locally. What's wrong?

> Two things. (a) `pg.item.unlink` rejects deletion outside `concept`
> state (Bible R3 — no hard deletes on historically significant
> records). The tool will work on concept items only; everything else
> will error. (b) Even on concept items, deleting an engineering item
> via an LLM tool is dangerous — the audit trail is lost. The right
> design is `obsolete_item` (a tool that transitions to `obsolete`),
> NOT `delete_item`. Mark mutating; the dispatcher does the rest.

---

## What this lesson does NOT cover

- The detail of the REST API (`product_graph_api`) — different surface,
  similar auth model, separately addressed.
- The internals of MCP protocol itself — see the Anthropic spec.
- Cloudflared Zero-Trust policy configuration — IT admin domain;
  separate runbook on the QNAP.
- Per-tool implementation of `where_used` / `bom_explode` closure
  queries — covered in lesson 9.4.
- How the agent decides to call which tool — that's prompt
  engineering, not platform work.
