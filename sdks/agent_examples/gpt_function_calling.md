# KitchenForge x OpenAI — function calling end-to-end

OpenAI's function-calling format is a thin remap of the KitchenForge tool
catalog: wrap each entry in `{ "type": "function", "function": { name,
description, parameters } }` (where `parameters` is our `input_schema`).

## 1) Fetch + transform the catalog

```python
import os, json, requests
from openai import OpenAI

KF_BASE = "https://southbrookcabinetry.space"
KF_KEY  = os.environ["KITCHENFORGE_API_KEY"]
client  = OpenAI()  # OPENAI_API_KEY from env

catalog = requests.get(
    f"{KF_BASE}/agent/v1/tools",
    headers={"X-Api-Key": KF_KEY},
).json()

tools_for_openai = [
    {
        "type": "function",
        "function": {
            "name": t["name"],
            "description": t["description"],
            "parameters": t["input_schema"],
        },
    }
    for t in catalog["tools"]
]
```

## 2) Run a turn

```python
SYSTEM = (
    "You are a kitchen-design assistant with access to KitchenForge tools. "
    "Always confirm a quote before releasing manufacturing orders."
)

messages = [
    {"role": "system", "content": SYSTEM},
    {"role": "user",   "content": "Start a Full Kitchen for partner 42, "
                                    "then confirm and release."},
]

resp = client.chat.completions.create(
    model="gpt-4o",
    messages=messages,
    tools=tools_for_openai,
    tool_choice="auto",
)
```

## 3) Dispatch tool calls

```python
import uuid

def dispatch(name: str, args_json: str) -> dict:
    args = json.loads(args_json)
    endpoint_by_name = {t["name"]: t["endpoint"] for t in catalog["tools"]}
    method, path = endpoint_by_name[name].split(" ", 1)
    r = requests.request(
        method, f"{KF_BASE}{path}",
        headers={
            "X-Api-Key": KF_KEY,
            "Content-Type": "application/json",
            "Idempotency-Key": str(uuid.uuid4()),
        },
        data=json.dumps(args),
    )
    r.raise_for_status()
    return r.json()

msg = resp.choices[0].message
if msg.tool_calls:
    messages.append(msg)  # echo the assistant's tool_calls
    for call in msg.tool_calls:
        result = dispatch(call.function.name, call.function.arguments)
        messages.append({
            "role": "tool",
            "tool_call_id": call.id,
            "content": json.dumps(result),
        })
    # Then re-prompt the model for the next turn.
    resp = client.chat.completions.create(
        model="gpt-4o",
        messages=messages,
        tools=tools_for_openai,
    )
```

## 4) Loop pattern

```python
while True:
    msg = resp.choices[0].message
    messages.append(msg)
    if not msg.tool_calls:
        print(msg.content)
        break
    for call in msg.tool_calls:
        result = dispatch(call.function.name, call.function.arguments)
        messages.append({
            "role": "tool",
            "tool_call_id": call.id,
            "content": json.dumps(result),
        })
    resp = client.chat.completions.create(
        model="gpt-4o",
        messages=messages,
        tools=tools_for_openai,
    )
```

## 5) Using the Python SDK instead

The SDK handles auth, idempotency, and response decoding. Same dispatch
table, less HTTP boilerplate:

```python
from kitchenforge import KitchenForgeClient

kf = KitchenForgeClient(KF_BASE, KF_KEY)

HANDLERS = {
    "instantiate":    lambda **kw: kf.tools.instantiate(**kw).raw,
    "add_zone":       lambda **kw: kf.tools.add_zone(**kw).raw,
    "confirm_quote":  lambda **kw: kf.tools.confirm_quote(**kw).raw,
    "release_mos":    lambda **kw: kf.tools.release_mos(**kw).raw,
    "raise_eco":      lambda **kw: kf.tools.raise_eco(**kw).raw,
}

def dispatch(name, args_json):
    return HANDLERS[name](**json.loads(args_json))
```

## 6) Strict mode (optional)

OpenAI supports `"strict": True` on function definitions. The
KitchenForge `input_schema` is plain JSON Schema — turning on strict is a
one-liner:

```python
tools_for_openai = [
    {
        "type": "function",
        "function": {
            "name": t["name"],
            "description": t["description"],
            "parameters": t["input_schema"],
            "strict": True,
        },
    }
    for t in catalog["tools"]
]
```

Strict mode will refuse to call a tool whose inputs don't match the schema,
which saves a round-trip and is recommended for the `instantiate` /
`confirm_quote` calls where bad input wastes a transaction.
