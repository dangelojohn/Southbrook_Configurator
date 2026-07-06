# Southbrook OS Kernel

The platform's operating-system layer (SBV2 doc 03). A near-leaf module by
design: it depends only on `base` and `mail`, and nothing Southbrook-specific
depends on. Any feature — existing or new — may depend on it.

It provides five building blocks:

- **`southbrook.os.switch`** — a kill-switch registry (master + per-feature).
- **`southbrook.os.ai.request`** — the AI call ledger (one row per kernel
  call: done / error / blocked).
- **`southbrook.os.ai.kernel`** — an `AbstractModel` exposing the single
  `run()` entry point every AI feature should route its chat-completion
  calls through.
- **`southbrook.os.memory`** — a namespaced shared key/value store with
  optional TTL expiry.
- **`southbrook.os.agent`** — an agent registry with daily call/token
  budgets, reset by cron.
- **`southbrook.os.tool`** — a registry of callable HTTP surfaces
  (path, method, auth) for tool-calling consumers.

**Ships dark.** The master switch (`os.ai.enabled`) is seeded **disabled**.
No existing Southbrook feature is refactored onto the kernel by this module
— that migration happens one feature per branch, later.

## The `run()` contract

```python
result = self.env["southbrook.os.ai.kernel"].run(
    feature="quote_summary",
    messages=[{"role": "user", "content": "Summarize this quote."}],
    model=None,            # falls back to os.ai.default_model
    temperature=None,
    max_tokens=512,
    timeout=45,
    source=("sale.order", sale_order.id),  # optional provenance
)
# result == {
#     "ok": bool,
#     "content": str | None,
#     "error": str | None,           # e.g. "blocked:master", "blocked:feature",
#                                     # "blocked:budget", or a transport error
#     "request_id": int | None,      # southbrook.os.ai.request id, always logged
#     "tokens_prompt": int,
#     "tokens_completion": int,
#     "cost_usd": float,
# }
```

`run()` **never raises**. Every path — kill-switch block, budget block,
transport failure, or an unforeseen internal error — returns this same dict
shape, and (best-effort) writes one `southbrook.os.ai.request` row.

## Config parameters (`ir.config_parameter`)

`os.ai.transport` selects one of three transports. **`http`** and
**`anthropic`** each own a private set of endpoint/model params — they are
deliberately NOT shared, so switching transports can never silently misroute
a call at a stale endpoint left over from the other provider.

| Key | Purpose | Default |
|---|---|---|
| `os.ai.transport` | `"mock"` / `"http"` (OpenAI-compatible) / `"anthropic"` (native Claude) | `"http"` |
| `os.ai.api_key` | Auth token — `Authorization: Bearer` for http, `x-api-key` for anthropic | unset |
| `os.ai.price_per_1k_prompt` | USD per 1k prompt tokens (both transports) | `0.0` |
| `os.ai.price_per_1k_completion` | USD per 1k completion tokens (both transports) | `0.0` |

**`http` transport (OpenAI-compatible):**

| Key | Purpose | Default |
|---|---|---|
| `os.ai.endpoint` | Base URL; kernel calls `{endpoint}/chat/completions` | unset |
| `os.ai.default_model` | Model name when `run()`'s `model` arg is falsy | unset |

**`anthropic` transport (native Claude Messages API):**

| Key | Purpose | Default |
|---|---|---|
| `os.ai.anthropic_endpoint` | Full Messages API URL (rarely needs overriding) | `https://api.anthropic.com/v1/messages` |
| `os.ai.anthropic_default_model` | Model name when `run()`'s `model` arg is falsy | `claude-sonnet-5` |

The anthropic transport mirrors the wire format already proven in
`southbrook_room_capture`/`southbrook_room_chat`: `system` is sent as a
top-level field (any `role="system"` messages are extracted, not passed
through), `max_tokens` is always set, `thinking` is disabled (Sonnet 5
otherwise spends part of the budget on adaptive thinking), and no
`temperature`/`top_p` is sent (Sonnet 5 rejects non-default sampling
params). Only plain text content is extracted — this is a thin router, not
a tool-calling agent; a feature needing tool-use should call the Messages
API directly, as `southbrook_room_chat` already does.

## Kill-switch keys

- `os.ai.enabled` — master switch. Off (default) blocks every `run()` call
  with `error="blocked:master"`.
- `os.ai.feature.<feature>` — per-feature switch. **Absent** means allowed;
  an explicit disabled row blocks that one feature with
  `error="blocked:feature"`.

## Migrating an existing feature onto the kernel

1. Replace the feature's direct provider call with
   `self.env["southbrook.os.ai.kernel"].run(feature="<your_feature_key>", ...)`.
2. Seed (or let an admin toggle) `os.ai.feature.<your_feature_key>` if the
   feature needs its own kill switch independent of the master; otherwise
   it inherits master-switch gating for free.
3. Optionally register a `southbrook.os.agent` row with
   `feature_key="<your_feature_key>"` to get a daily call/token budget —
   the kernel checks it automatically once the row exists.

Remember: `os.ai.enabled` ships **off**. A migrated feature stays dark until
an admin flips the master switch (or the feature is explicitly exercised
with `os.ai.transport="mock"` in tests).
