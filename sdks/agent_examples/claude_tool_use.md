# KitchenForge x Claude — `tool_use` end-to-end

`GET /agent/v1/tools` returns a JSON-Schema'd catalog ready to feed straight
into Claude's `tools` parameter. The shape (`name`, `description`,
`input_schema`) is already Claude-compatible — no transformation needed.

## 1) Fetch the catalog

```python
import os, json, requests
from anthropic import Anthropic

KF_BASE = "https://southbrookcabinetry.space"
KF_KEY  = os.environ["KITCHENFORGE_API_KEY"]
client  = Anthropic()  # ANTHROPIC_API_KEY from env

catalog = requests.get(
    f"{KF_BASE}/agent/v1/tools",
    headers={"X-Api-Key": KF_KEY},
).json()
# catalog["tools"] = [{name, description, input_schema, endpoint}, ...]

tools_for_claude = [
    {
        "name": t["name"],
        "description": t["description"],
        "input_schema": t["input_schema"],
    }
    for t in catalog["tools"]
]
```

## 2) Run a turn with `tool_use`

```python
resp = client.messages.create(
    model="claude-opus-4-7",
    max_tokens=2048,
    tools=tools_for_claude,
    system=(
        "You are a kitchen-design assistant with access to KitchenForge tools. "
        "When the user asks to start a kitchen, call `instantiate` with the "
        "Full Kitchen template (id=7) and their partner id."
    ),
    messages=[{
        "role": "user",
        "content": "Start a kitchen for customer 42 — room 4200 x 3600 mm.",
    }],
)
```

## 3) Dispatch tool calls back to the KitchenForge API

```python
def dispatch(tool_name: str, tool_input: dict) -> dict:
    """Map a Claude tool_use block to a KitchenForge HTTP call."""
    endpoint_by_name = {t["name"]: t["endpoint"] for t in catalog["tools"]}
    method, path = endpoint_by_name[tool_name].split(" ", 1)
    r = requests.request(
        method, f"{KF_BASE}{path}",
        headers={
            "X-Api-Key": KF_KEY,
            "Content-Type": "application/json",
            # Idempotency: stable per (tool_use.id, day). Replay-safe.
            "Idempotency-Key": tool_input.pop("_idempotency_key", None) or "",
        },
        data=json.dumps(tool_input),
    )
    r.raise_for_status()
    return r.json()

tool_results = []
for block in resp.content:
    if block.type == "tool_use":
        result = dispatch(block.name, dict(block.input))
        tool_results.append({
            "type": "tool_result",
            "tool_use_id": block.id,
            "content": json.dumps(result),
        })
```

## 4) Loop until Claude stops calling tools

```python
messages = [
    {"role": "user", "content": "Start a kitchen for customer 42 — 4200 x 3600 mm."},
    {"role": "assistant", "content": resp.content},
    {"role": "user", "content": tool_results},
]
while True:
    next_resp = client.messages.create(
        model="claude-opus-4-7",
        max_tokens=2048,
        tools=tools_for_claude,
        messages=messages,
    )
    if next_resp.stop_reason != "tool_use":
        print(next_resp.content[0].text)
        break
    # repeat dispatch -> tool_result -> next call
    ...
```

## 5) Why the SDK helps

The above is the "wire" version. If you'd rather not hand-roll the dispatch
table, use the Python SDK and call `kf.tools.<name>(...)` from your tool
handler — the SDK already maps each `tool_use` name to the right endpoint,
generates the idempotency key, and decodes the response into a typed
dataclass.

```python
from kitchenforge import KitchenForgeClient

kf = KitchenForgeClient(KF_BASE, KF_KEY)

HANDLERS = {
    "instantiate":    lambda **kw: kf.tools.instantiate(**kw),
    "add_zone":       lambda **kw: kf.tools.add_zone(**kw),
    "confirm_quote":  lambda **kw: kf.tools.confirm_quote(**kw),
    "release_mos":    lambda **kw: kf.tools.release_mos(**kw),
    "raise_eco":      lambda **kw: kf.tools.raise_eco(**kw),
}

def dispatch(tool_name, tool_input):
    return HANDLERS[tool_name](**tool_input).raw
```

## 6) Filesystem as agent memory

For free-form navigation between tool calls, fold in `fs_get` / `fs_put`:

```python
# Browse what's available before committing to a template.
templates = kf.fs_get("templates")
# Read a project's current quote.
quote = kf.fs_get(f"projects/{project_id}/quote.yaml")
# Patch a zone (with ETag concurrency).
kf.fs_put(
    f"projects/{project_id}/zones/001-base-30.yaml",
    {"quantity": 2, "dimensions_mm": {"width": 762}},
    if_match=quote["etag"],
)
```

Claude can be told the FS exists ("Use /agent/v1/files/... GET to navigate
projects, /agent/v1/tools/... POST to mutate") and it will spontaneously
explore — the manifest at `/.well-known/ai-agent.json` is designed exactly
for that.
