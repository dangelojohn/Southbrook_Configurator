# kitchenforge-sdk (Python)

Typed Python client for the KitchenForge agent API — filesystem + typed tools +
Marathon telemetry — running on the Odoo 19 CE Southbrook stack.

## Install

```bash
pip install kitchenforge-sdk
# or from this repo:
pip install -e sdks/python
```

Depends on `requests`. Python 3.10+.

## Auth

Generate a per-user API key in Odoo at Settings -> Users & Companies -> API
Keys. Pass it as `api_key=` to the client; sent on every request as
`X-Api-Key`.

## Canonical 6-line "instantiate -> confirm -> release"

```python
from kitchenforge import KitchenForgeClient

kf = KitchenForgeClient("https://southbrookcabinetry.space", api_key="kfk-...")
proj = kf.tools.instantiate(template_id=7, partner_id=42, dims={"room_width_mm": 4200})
kf.tools.add_zone(project_id=proj.project_id, zone={"product_id": 311, "width_mm": 900})
kf.tools.confirm_quote(project_id=proj.project_id)
kf.tools.release_mos(project_id=proj.project_id)
```

## Filesystem

```python
listing = kf.fs_get("templates")               # GET  /agent/v1/files/templates
quote   = kf.fs_get(f"projects/{proj.project_id}/quote.yaml")
etag    = kf.fs_head(f"projects/{proj.project_id}.yaml")
kf.fs_put(f"projects/{proj.project_id}/zones/001-base-30.yaml",
          {"quantity": 2, "dimensions_mm": {"width": 762}},
          if_match=etag)
```

## Tool catalog (feed into Claude / GPT)

```python
catalog = kf.tools.list()  # {"schema": "kitchenforge.agent.tools.v1", "tools": [...]}
```

See `sdks/agent_examples/` for copy-pasteable Claude `tool_use` and OpenAI
function-calling bindings.

## Idempotency

Every mutating call accepts an optional `idempotency_key=`. If omitted, the SDK
generates a `uuid4()` per call. The server caches the response under
`(api_key_hash, idempotency_key)` so retrying with the same key is safe.

## Errors

All non-2xx responses raise:

- `NotFoundError` (404)
- `PreconditionFailedError` (409/412 — ETag mismatch)
- `ApiError` (everything else; has `.status`, `.code`, `.message`)

## Tests

```bash
pip install -e ".[dev]"
pytest
```
