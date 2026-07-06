# Southbrook OS Kernel — Build Spec (v1)
**Module:** `southbrook_os_kernel` 19.0.1.0.0 · LGPL-3 · depends: `base`, `mail` ONLY (near-leaf by design — anything may depend on it; it depends on nothing Southbrook).
**Purpose:** the platform's operating-system layer per SBV2 doc 03: one AI Kernel every AI feature routes through, a kill-switch registry, shared memory, an agent registry with budgets, and a tool registry. Ships dark: existing features are NOT refactored in this PR; they migrate one-per-branch later.

House conventions (MANDATORY): `# SPDX-License-Identifier: LGPL-3.0-only` first line of every .py; 4-space indent; one model per file named after the model; explicit ACL rows for every model; tests as `TransactionCase` tagged `@tagged("post_install", "-at_install", "southbrook_os_kernel")`; `<list>` never `<tree>`; xml_ids prefixed by feature area. Odoo 19: use `models.Constraint` (NEVER `_sql_constraints`); ir.cron inherits ir.actions.server (fields: name, model_id, state="code", code, interval_number, interval_type, active — NO numbercall/doall); top-level menus need web_icon; no `expand=` on search-view `<group>`; double-check every `@api.depends` field name (a typo silently breaks the registry).

## Models

### 1. `southbrook.os.switch` — kill-switch registry (models/os_switch.py)
Inherits mail.thread. Fields: `key` Char required indexed (unique via `models.Constraint("unique(key)", ...)`); `name` Char required; `enabled` Boolean default False tracking=True; `category` Selection [("ai","AI"),("agent","Agent"),("integration","Integration"),("other","Other")] default "other"; `note` Text.
API (all `@api.model`):
- `is_on(key, default=False)` → bool. Missing key → `default`. Must NOT raise, ever.
- `set_switch(key, enabled, name=None)` → upsert helper (used by seeds/tests).
`_rec_name = "key"` is wrong — keep `name` as rec_name but show key in views.

### 2. `southbrook.os.ai.request` — the AI ledger (models/os_ai_request.py)
Plain model (no chatter — high volume). Fields: `feature` Char required indexed; `provider` Char; `model_name` Char; `state` Selection [("done","Done"),("error","Error"),("blocked","Blocked")] required indexed; `user_id` Many2one res.users default current; `source_model` Char; `source_res_id` Integer; `tokens_prompt` Integer; `tokens_completion` Integer; `cost_usd` Float(digits=(12,6)); `duration_ms` Integer; `error` Text; `prompt_preview` Text (truncate to 2000 chars); `response_preview` Text (truncate 2000); `company_id` Many2one res.company default current.
`name` computed stored: `"AI-%05d · %s" % (id-ish, feature)` — compute from `feature` + create; simplest: override `create` to fill a `name` Char. Ordering: `create_date desc`.

### 3. `southbrook.os.ai.kernel` — the kernel API (models/os_ai_kernel.py)
`AbstractModel`, `_name = "southbrook.os.ai.kernel"`, `_description = "Southbrook OS AI Kernel"`.
Public API:
```python
@api.model
def run(self, feature, messages, model=None, temperature=None, max_tokens=None,
        timeout=45, source=None):
    """Route one chat-completion call. NEVER raises — always returns:
    {"ok": bool, "content": str|None, "error": str|None, "request_id": int|None,
     "tokens_prompt": int, "tokens_completion": int, "cost_usd": float}
    source: optional (model_name, res_id) tuple for provenance."""
```
Flow (each step wrapped so no exception escapes; on internal failure log state="error"):
1. Master switch: `southbrook.os.switch.is_on("os.ai.enabled", default=False)` — off → log state="blocked", return ok=False, error="blocked:master".
2. Feature switch `f"os.ai.feature.{feature}"` with `default=True` (absent = allowed; presence of a disabled row blocks) → blocked as above ("blocked:feature").
3. Budget: find `southbrook.os.agent` with `feature_key == feature`; if found call `check_and_consume(est_tokens=max_tokens or 1024)`; refusal → "blocked:budget".
4. Transport from `ir.config_parameter` `os.ai.transport` (default `"http"`):
   - `"mock"` → return canned success `content="MOCK:" + feature`, tokens 1/1, no network (tests + safe fresh-DB default is still "http"; seeds do not set transport).
   - `"http"` → OpenAI-compatible chat-completions POST via `requests` (import guarded at module top with try/except; missing lib → state="error"). Config params: `os.ai.endpoint` (base URL, call `{endpoint}/chat/completions`), `os.ai.api_key` (Bearer), `os.ai.default_model` (used when model arg falsy). Payload: model, messages, optional temperature/max_tokens. Parse `choices[0].message.content` and `usage`.
5. Cost: params `os.ai.price_per_1k_prompt` / `os.ai.price_per_1k_completion` (float, default 0.0) → cost_usd.
6. ALWAYS create one `southbrook.os.ai.request` row (done/error/blocked) with duration_ms, previews (json-dump messages, truncated), provider="openai_compat", source fields if given. Row creation itself in try/except (ledger failure must not break the caller's answer).
7. After a "done" call, post actual tokens to the agent row (`record_usage(tokens_total)`) if one matched.

### 4. `southbrook.os.memory` — shared memory (models/os_memory.py)
Fields: `namespace` Char required indexed default "global"; `key` Char required indexed; `value_json` Text; `source` Char (who wrote it); `user_id` M2O res.users; `expires_at` Datetime; `active` Boolean default True. Unique `models.Constraint("unique(namespace, key)", ...)`.
API (`@api.model`): `remember(namespace, key, value, source=None, ttl_hours=None)` (value json-dumped; upsert; ttl → expires_at); `recall(namespace, key, default=None)` (expired or missing → default; never raises); `vacuum_expired()` → unlink expired (called by cron).

### 5. `southbrook.os.agent` — agent registry + budgets (models/os_agent.py)
Inherits mail.thread. Fields: `name` Char required; `code` Char required (unique Constraint); `purpose` Text; `feature_key` Char indexed (links kernel calls); `cron_id` M2O ir.cron ondelete="set null"; `enabled` Boolean default True tracking=True; `daily_call_budget` Integer default 0 (0 = unlimited); `daily_token_budget` Integer default 0; `calls_today` Integer readonly; `tokens_today` Integer readonly; `budget_date` Date readonly; `last_run_at` Datetime; `last_status` Char.
Methods: `check_and_consume(est_tokens=0)` → bool (rolls counters; resets when budget_date != today; disabled agent → False; over either non-zero budget → False; else increment calls_today and return True); `record_usage(tokens)` (adds actual tokens); `reset_daily()` `@api.model` for cron.

### 6. `southbrook.os.tool` — tool registry (models/os_tool.py)
Fields: `name` Char required; `code` Char required (unique Constraint); `http_method` Selection [("GET","GET"),("POST","POST")] default "GET"; `path` Char required; `module_name` Char; `auth` Selection [("public","Public"),("api_key","API key"),("session","Session")] default "session"; `description` Text; `active` Boolean default True.
API: `@api.model manifest()` → list of dicts (code, method, path, auth, description) for active tools ordered by code.

## Views / menus (views/*.xml — one file per model + menu.xml)
List+form for all; ai.request also search (filters: state, feature groupby, My requests) + pivot + graph (cost_usd, tokens by feature/day). Root menu "Southbrook OS" `web_icon="southbrook_os_kernel,static/description/icon.png"`, children: AI Requests, Kill Switches, Shared Memory, Agents, Tools (sequence 10..50). NO OWL/JS anywhere in this module — pure backend views.

## Security (security/groups.xml + ir.model.access.csv)
Groups: `group_os_viewer` (implied_ids base.group_user) read-everything; `group_os_admin` (implied viewer) full CRUD. ACLs: viewer r=1 on all 5 stored models; admin rwcu on all. ai.request: nobody needs unlink except admin (keep u=1 admin only). Menus visible to viewer.

## Data (data/*.xml)
- `os_switch_seed.xml` (noupdate="1"): switches `os.ai.enabled` (name "AI Kernel — master", category ai, enabled **False** — ships dark) and `os.ai.feature.smoke_test` (enabled True, category ai).
- `ir_cron.xml` (v19 schema): "OS Kernel: vacuum expired memory" daily → `model._name == southbrook.os.memory`, code `model.vacuum_expired()`; "OS Kernel: reset agent daily budgets" daily → `model.reset_daily()`.
- `os_tool_seed.xml` (noupdate="1"): rows for known surfaces: sb_api_orders (POST /southbrook/api/order/<id>, session), agent_quote (POST /agent/api/v1/quote, api_key, module southbrook_agent_gateway), agent_openapi (GET /agent/api/v1/openapi.json, public), llms_txt (GET /llms.txt, public), command_center_bootstrap (POST /command_center/bootstrap, session).

## Tests (tests/*.py; NO network — set config param os.ai.transport="mock" in setUp)
- test_switch.py: is_on default when absent; set_switch upsert; disabled blocks.
- test_kernel.py: master off → ok False error blocked:master + ledger row state blocked; master+feature on + mock transport → ok True, content startswith "MOCK:", ledger done row with tokens; feature row disabled → blocked:feature; run() with a raising internal (e.g., transport "http" + no requests endpoint param) still returns dict (never raises) and logs error/blocked.
- test_memory.py: remember/recall roundtrip (dict value); missing → default; ttl expiry (freeze by writing expires_at in past) → default + vacuum_expired removes.
- test_agent_budget.py: unlimited passes; call budget 1 → second check False; token budget exceeded → False; disabled → False; reset_daily zeroes.
- test_tool.py: manifest shape + only active.

## README.md
Short: what it is, the run() contract with example, config params table, switch keys, how a feature migrates onto the kernel (3 steps), ships-dark note.

## Icon
`static/description/icon.png` — copy from southbrook_command_center's icon (placeholder; replaced later).
