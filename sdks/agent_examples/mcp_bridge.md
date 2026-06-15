# KitchenForge x MCP — bridging the agent FS to Claude Desktop

The Model Context Protocol (MCP) is the spec Claude Desktop, Cursor, and other
MCP-aware clients use to talk to external tools. This bridge exposes the
KitchenForge filesystem and tool catalog as an MCP server, so any MCP host can
list/read/write directly.

Two ways to expose KitchenForge over MCP:

1. **Resources** — map `/agent/v1/files/...` to MCP resource URIs.
2. **Tools** — map the five tool endpoints to MCP tool definitions.

The script below does both. It uses the official `mcp` Python SDK.

## Install

```bash
pip install mcp kitchenforge-sdk
export KF_BASE_URL=https://southbrookcabinetry.space
export KF_API_KEY=kfk-...
```

## `kitchenforge_mcp.py`

```python
"""KitchenForge MCP bridge.

Run as:
    python kitchenforge_mcp.py

Then point Claude Desktop at it via ~/.config/claude/claude_desktop_config.json:

    {
      "mcpServers": {
        "kitchenforge": {
          "command": "python",
          "args": ["/abs/path/to/kitchenforge_mcp.py"],
          "env": {
            "KF_BASE_URL": "https://southbrookcabinetry.space",
            "KF_API_KEY":  "kfk-..."
          }
        }
      }
    }
"""
import os
import json
import asyncio
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Resource, Tool, TextContent

from kitchenforge import KitchenForgeClient

KF = KitchenForgeClient(
    base_url=os.environ["KF_BASE_URL"],
    api_key=os.environ["KF_API_KEY"],
)

app = Server("kitchenforge")


# --------------------------------------------------------------------
# Resources: every FS path is reachable as kitchenforge://...
# --------------------------------------------------------------------
@app.list_resources()
async def list_resources() -> list[Resource]:
    root = KF.fs_get()
    return [
        Resource(
            uri=f"kitchenforge://{e['path'].lstrip('/')}",
            name=e["name"],
            description=e.get("desc", ""),
            mimeType="application/yaml" if e["kind"] == "file"
                     else "inode/directory",
        )
        for e in root["entries"]
    ]


@app.read_resource()
async def read_resource(uri: str) -> str:
    path = uri.replace("kitchenforge://", "", 1)
    data = KF.fs_get(path)
    return json.dumps(data, indent=2)


# --------------------------------------------------------------------
# Tools: pull the catalog from the live server, turn each into an MCP tool
# --------------------------------------------------------------------
_TOOL_CATALOG_CACHE: list[dict] | None = None


def _catalog() -> list[dict]:
    global _TOOL_CATALOG_CACHE
    if _TOOL_CATALOG_CACHE is None:
        _TOOL_CATALOG_CACHE = KF.tools.list()["tools"]
    return _TOOL_CATALOG_CACHE


@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name=t["name"],
            description=t["description"],
            inputSchema=t["input_schema"],
        )
        for t in _catalog()
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    HANDLERS = {
        "instantiate":   lambda kw: KF.tools.instantiate(**kw).raw,
        "add_zone":      lambda kw: KF.tools.add_zone(**kw).raw,
        "confirm_quote": lambda kw: KF.tools.confirm_quote(**kw).raw,
        "release_mos":   lambda kw: KF.tools.release_mos(**kw).raw,
        "raise_eco":     lambda kw: KF.tools.raise_eco(**kw).raw,
    }
    if name not in HANDLERS:
        return [TextContent(type="text",
                            text=f"unknown tool: {name}")]
    try:
        result = HANDLERS[name](arguments)
        return [TextContent(type="text",
                            text=json.dumps(result, indent=2))]
    except Exception as exc:
        return [TextContent(type="text",
                            text=f"error: {exc}")]


# --------------------------------------------------------------------
# stdio entrypoint
# --------------------------------------------------------------------
async def main():
    async with stdio_server() as (read, write):
        await app.run(read, write, app.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
```

## What you get in Claude Desktop

Once configured, Claude Desktop will:

1. **List the FS root** as MCP resources — `kitchenforge://templates`,
   `kitchenforge://projects`, `kitchenforge://catalog`, `kitchenforge://shop`.
   Drill-down works because Claude can call `read_resource` on any URI it
   discovers in a listing.
2. **Surface the five tools** in the tool picker: `instantiate`, `add_zone`,
   `confirm_quote`, `release_mos`, `raise_eco`. The JSON Schema is enforced
   at the client side — bad inputs never hit the wire.
3. **Stay safe under retry** — the SDK auto-generates an `Idempotency-Key`
   per call, so Claude Desktop's "retry" button doesn't duplicate sale orders.

## Notes

- The script reads the tool catalog at startup. For long-running servers,
  add a periodic refresh (`_TOOL_CATALOG_CACHE = None`) to pick up new tools
  without a restart.
- For multi-tenant deploys, accept `KF_BASE_URL` and `KF_API_KEY` per
  request (MCP supports per-resource auth headers in newer protocol
  versions) instead of from env.
- If you need **listing** to be deep (templates expanded under
  `kitchenforge://templates/`), implement `resources/templates` MCP method
  — the static `list_resources` above only surfaces the root namespaces and
  lets Claude recursively walk via `read_resource`.

## Wire-only fallback (no SDK)

If you want to ship the bridge as a single file with no `kitchenforge-sdk`
dependency, replace the `KitchenForgeClient` calls with `requests`:

```python
import requests
def kf(method, path, **kw):
    r = requests.request(method, f"{os.environ['KF_BASE_URL']}{path}",
                         headers={"X-Api-Key": os.environ["KF_API_KEY"],
                                  "Content-Type": "application/json"},
                         **kw)
    r.raise_for_status()
    return r.json()
# fs_get:   kf("GET", f"/agent/v1/files/{path}")
# tool:     kf("POST", f"/agent/v1/tools/{name}", data=json.dumps(arguments))
```

Functionally equivalent; the SDK just buys you typed returns + idempotency
key generation.
