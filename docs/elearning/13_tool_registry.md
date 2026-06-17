---
course: 13 — Fabio Deep Dive
chapter: 13.4
title: The Tool Registry — Decorator, Dispatch, and ACL Layering
duration: 35 minutes
audience: Developer adding or modifying tools; admin / sysadmin debugging tool-call traces
prereqs: Lesson 13.1 (`13_fabio_architecture.md`) for the four-pillar context; lesson 13.3 (`13_jwt_auth_personas.md`) for JWT + persona; spec § 4 (ACL = tool registry) at `docs/superpowers/specs/2026-06-16-southbrook-os-and-hermes-platform-design.md`
custom_modules: southbrook_hermes
---

# The Tool Registry — Decorator, Dispatch, and ACL Layering

## Who this lesson is for

You're the developer about to add the fourteenth tool. Or you're the
admin investigating why a tool the spec says should be available isn't
showing up in the LLM's function list. Or you're the IT person being
asked "is this tool call safe?" before flipping the sidecar live.

The tool registry is the single most-load-bearing piece of Fabio's
internals. It's small (~65 lines for the decorator, ~130 lines for the
controller) but it's where every ACL decision gets made.

## Where this lives on the site

You don't reach the registry through a menu — it's an HTTP endpoint:

> **`GET /api/hermes/tools`** — public route, JWT-bearer authenticated.
> Returns the tool list filtered by the caller's `(persona, tier)`
> claims. The sidecar calls this once at cold start.

> **`POST /api/hermes/tools/<slug>`** — public route, JWT-bearer
> authenticated. Dispatches the named tool. The sidecar calls this every
> time the LLM emits a function call.

Both controllers are in `addons/southbrook_hermes/controllers/hermes_tools_api.py`.

You can also inspect the registry from a `odoo-bin shell` Python REPL:

```python
>>> from odoo.addons.southbrook_hermes.tools.decorator import TOOL_REGISTRY
>>> [t["slug"] for t in TOOL_REGISTRY]
['list_my_orders', 'get_order_status', 'get_order_line',
 'list_my_kitchen_projects', 'get_kitchen_project',
 'get_install_schedule', 'get_quote_pdf_url',
 'list_my_recommendations', 'get_os_section',
 'post_internal_note', 'send_spec_pdf_email',
 'schedule_followup_activity', 'propose_recommendation']
```

## What your screen shows

Five concrete things make up the registry layer.

### 1. The `@hermes_tool` decorator

`addons/southbrook_hermes/tools/decorator.py`:

```python
TOOL_REGISTRY = []

def hermes_tool(*, personas, tier, scope, description, parameters=None):
    def wrap(fn):
        slug = fn.__name__
        params = parameters or _extract_params_from_signature(fn)
        TOOL_REGISTRY.append({
            "slug": slug,
            "qualified_slug": f"southbrook__{slug}",
            "personas": list(personas),
            "tier": tier,
            "scope": scope,
            "description": description,
            "parameters": params,
            "fn": fn,
        })
        @functools.wraps(fn)
        def call(env, **kwargs):
            return fn(env, **kwargs)
        return call
    return wrap
```

Four required keyword args:

- **`personas`** — list of persona strings allowed to call the tool.
  Drawn from `{trade_partner, sales_rep, mfg_manager}`. If a tool is
  trade-partner-only, list only `["trade_partner"]`. Most v1.0 tools
  list `["trade_partner", "sales_rep"]` because sales reps inherit
  trade-partner capabilities.
- **`tier`** — one of `T0 / T1 / T2`. See lesson 13.6 for the tier
  definitions. Dispatch enforces this against the JWT's tier mask
  claim.
- **`scope`** — a string describing the tool's data-scoping discipline.
  Free-form but conventionally one of: `own`, `own_order`, `global`.
  This is documentation, not enforcement — actual scope is enforced
  by record rules inside the tool. But the registry lists it so the
  sidecar and reviewers can see the intent.
- **`description`** — one-paragraph natural-language description shown
  to the LLM. This is the LLM's only narrative source for "when to use
  this tool"; write it carefully.
- **`parameters`** (optional) — JSON Schema for the tool args. If
  omitted, `_extract_params_from_signature(fn)` introspects the Python
  signature and generates a minimal schema from type hints.

The decorator runs at import time. The `TOOL_REGISTRY` list is
process-level — populated when Odoo starts and the
`southbrook_hermes.tools` package is imported. There's no database
backing; restart Odoo and the registry rebuilds itself from source.

### 2. The `TOOL_REGISTRY` data structure

After all decorators have run, `TOOL_REGISTRY` is a list of dicts:

```python
{
    "slug": "get_order_status",
    "qualified_slug": "southbrook__get_order_status",
    "personas": ["trade_partner", "sales_rep"],
    "tier": "T0",
    "scope": "own_order",
    "description": "Return the production status of a specific order, …",
    "parameters": {
        "type": "object",
        "properties": {"order_id": {"type": "integer"}},
        "required": ["order_id"],
    },
    "fn": <function get_order_status at 0x…>,
}
```

The `qualified_slug` (`southbrook__get_order_status`) is the per-tenant
prefix from spec § 4.4 rule 3 — prevents misrouted cross-tenant calls
when v1.x adds Porterly. The sidecar uses the qualified slug; Odoo
dispatch uses the bare slug because the controller is already
tenant-scoped (an Odoo instance is one tenant).

### 3. `_extract_params_from_signature` — the schema introspection

```python
def _extract_params_from_signature(fn):
    sig = inspect.signature(fn)
    props = {}
    required = []
    for name, param in sig.parameters.items():
        if name == "env":
            continue
        json_type = "string"
        if param.annotation is int:
            json_type = "integer"
        elif param.annotation is bool:
            json_type = "boolean"
        elif param.annotation is float:
            json_type = "number"
        props[name] = {"type": json_type}
        if param.default is inspect.Parameter.empty:
            required.append(name)
    return {"type": "object", "properties": props, "required": required}
```

`env` is dropped (it's the Odoo environment, not a tool arg). Each remaining
arg becomes a JSON Schema property. Type hints map to JSON types:
`int → integer`, `bool → boolean`, `float → number`, anything else
(including `str` and `dict`) defaults to `string`. Args without a default
are marked required.

The minimalism is deliberate. The LLM is given just enough type info to
generate a valid call; it doesn't need to know about Python's `Optional`
or `Union`. If a tool's signature needs richer JSON Schema (enums, nested
objects), pass an explicit `parameters=` to the decorator.

### 4. `registry_for_persona(persona, tier_mask)`

The filter the registry endpoint applies:

```python
def registry_for_persona(persona, tier_mask):
    allowed_tiers = set(tier_mask.split("+"))
    return [
        {k: v for k, v in t.items() if k != "fn"}
        for t in TOOL_REGISTRY
        if persona in t["personas"] and t["tier"] in allowed_tiers
    ]
```

Two filters: persona must be in the tool's allowlist; tool's tier must
be in the JWT's tier mask. Strips the `fn` key (don't send the Python
function object across HTTP). Returns the filtered list to the sidecar.

Per spec § 4.3: **forbidden tools don't exist** in the LLM's function
definitions. The LLM is shown only the tools the caller can use. There's
no "you tried to call a forbidden tool" path; the LLM literally doesn't
know forbidden tools exist for this caller. This is by design — it
removes a class of prompt-injection attacks (you can't trick the model
into calling a tool it can't see).

### 5. The dispatch controller (`POST /api/hermes/tools/<slug>`)

Full flow in `controllers/hermes_tools_api.py:HermesToolsApiController.dispatch`:

```python
@http.route("/api/hermes/tools/<slug>", type="http", auth="public",
            methods=["POST"], csrf=False)
def dispatch(self, slug, **kw):
    claims = self._verify()                    # 1. JWT verify
    if isinstance(claims, http.Response):
        return claims                          # 401 / 503 short-circuit
    fn = decorator.get_tool_function(slug)
    if fn is None:
        return self._json({"error": "unknown_tool", ...}, status=404)
    meta = next(
        (t for t in decorator.TOOL_REGISTRY if t["slug"] == slug), None)
    if claims["persona"] not in meta["personas"]:
        return self._json({"error": "not_allowed_for_persona", ...},
                          status=403)          # 2. persona check
    allowed_tiers = set(claims["tier"].split("+"))
    if meta["tier"] not in allowed_tiers:
        return self._json({"error": "tier_required", ...}, status=403)
                                               # 3. tier check
    try:
        args = json.loads(request.httprequest.data or b"{}")
    except json.JSONDecodeError:
        return self._json({"error": "invalid_json"}, status=400)
    partner = request.env["res.partner"].sudo().browse(claims["partner_id"])
    if not partner.exists():
        return self._json({"error": "unknown_partner", ...}, status=403)
                                               # 4. partner exists
    user = partner.user_ids[:1]
    if not user:
        return self._json({"error": "partner_has_no_user", ...},
                          status=403)          # 5. partner has user
    env_with_user = request.env(user=user.id)
    # 6. Claim-bound args
    sig_params = inspect.signature(fn).parameters
    for arg_name in _CLAIM_BOUND_ARGS:
        if arg_name in sig_params:
            args[arg_name] = claims[arg_name]
    try:
        result = fn(env_with_user, **args)     # 7. Tool runs
    except Exception as e:
        return self._json({"error": "tool_exception", ...}, status=500)
    return self._json(result)
```

Six layered checks before the tool runs:

1. **JWT verification** — `_verify()` returns 401 if no bearer, 503 if
   not configured, 401 if invalid.
2. **Persona allowlist** — tool's `personas` list must include the
   JWT's `persona` claim.
3. **Tier mask** — tool's `tier` must be in the JWT's `tier` claim
   (`T0+T1+T2`).
4. **Partner exists** — `claims["partner_id"]` must resolve to a real
   `res.partner` (delta § 14.3).
5. **Partner has user** — the partner must have a linked `res.users`
   (delta § 14.3).
6. **Claim-bound args** — `persona`, `partner_id`, `tenant` are
   overridden from claims (delta § 14.2).

THEN the tool runs in `env(user=portal_user)` — so record rules in the
ORM see the right user identity, and Odoo's standard ACL applies inside
every `search()` / `browse()` / `write()` the tool performs.

### 6. The signature-binding mechanic

`inspect.signature(fn).parameters` walks the function's declared args.
The dispatch checks each of the three claim-bound names against the
signature:

```python
sig_params = inspect.signature(fn).parameters
for arg_name in _CLAIM_BOUND_ARGS:
    if arg_name in sig_params:
        if arg_name == "persona":
            args["persona"] = claims["persona"]
        elif arg_name == "partner_id":
            args["partner_id"] = claims["partner_id"]
        elif arg_name == "tenant":
            args["tenant"] = claims["tenant"]
```

So:
- A tool that declares `persona: str` in its signature gets `persona`
  overridden from the JWT, no matter what the LLM sent.
- A tool that doesn't declare `persona` doesn't get it injected — and
  if the LLM sent `persona="foo"` in the body, that ends up in
  `**kwargs` if the tool accepts arbitrary kwargs, or raises a
  `TypeError` if not.

Tools that don't need persona scoping just don't declare the arg. Tools
that do (like `propose_recommendation`) declare it and use it for guard
logic.

## Your daily flow

### Adding a new tool

1. Pick a clear, kebab-case Python function name (becomes the slug).
   It will be visible to the LLM as `southbrook__<slug>`.
2. Pick the file. Read tools live in `tools/read_tools.py`, write tools
   in `tools/write_tools.py`. There's no enforcement; convention only.
3. Write the function:

```python
@hermes_tool(
    personas=["trade_partner", "sales_rep"],
    tier="T0",
    scope="own_order",
    description="Return the latest CAD drawings URL for an order.",
)
def get_drawings_url(env, order_id: int):
    order = env["sale.order"].browse(order_id)
    order.check_access_rights("read")
    order.check_access_rule("read")
    return {"drawings_url": order.drawings_url, "as_of": str(fields.Datetime.now())}
```

4. Always include both `check_access_rights` and `check_access_rule` —
   the latter applies record rules (delta § 14.5 added this where it
   was missing). Don't use `sudo()` unless you have a documented
   reason (spec § 4.4 rule 2).
5. Add to `tools/__init__.py` so the decorator runs at import.
6. Restart Odoo. Verify with `python3 -c "from odoo.addons.southbrook_hermes.tools.decorator import TOOL_REGISTRY; print([t['slug'] for t in TOOL_REGISTRY])"` in a shell, or by hitting `GET /api/hermes/tools` with a fresh JWT.
7. Redeploy the sidecar (`vercel deploy --prod`) so its cached registry
   refreshes.

### Debugging "the LLM didn't call my tool"

Three likeliest causes:

- **Registry cache.** The sidecar caches the registry per tenant ×
  persona × tier. Until the next sidecar cold start (or you redeploy),
  the LLM sees the old list. Force a cold start: `vercel deploy --prod`.
- **Persona / tier filter.** Verify your tool's `personas` includes the
  caller's persona, and `tier` is in the caller's mask. Hit
  `GET /api/hermes/tools` with the actual caller's JWT and check if
  your tool is in the response.
- **Description.** The LLM decides which tool to call based on the
  `description`. A vague description (`"do stuff"`) won't trigger calls
  even if the tool is in the registry. Rewrite to be specific about
  inputs, outputs, and the situation that warrants calling.

### Debugging "the tool got called but the result is empty"

This is almost always record-rule scope. Tools run in
`env(user=portal_user)`; if the partner's record rules don't grant
read access to the queried records, the search returns an empty
recordset. The classic case: a tool reads `mrp.production` records, and
trade partners have no record rule giving them access to
`mrp.production`. The tool returns `[]` — no error, no warning, just
silence. Fix: either widen the record rule, or scope the tool through
a partner-visible model (e.g. via `sale.order` → `order_line.move_ids` →
production).

### Debugging "503 hermes_not_configured" on /api/hermes/tools

The JWT secret is unset (or still the placeholder). See lesson 13.3.

## Common mistakes + how to recover

**"I added a tool but `GET /api/hermes/tools` doesn't show it."**

The `tools/__init__.py` import didn't pick up your file. The decorator
runs when the module is imported, which happens at Odoo startup. If
your file is `tools/my_tool.py` and `tools/__init__.py` doesn't import
it, the decorator never runs. Add an import statement (or `from . import
*`).

**"The dispatch returns 403 `tier_required` for my T0 tool."**

The JWT's `tier` claim isn't `T0+T1+T2`. Either persona resolution is
wrong (lesson 13.3) or someone has overridden the default tier mask.
Decode the JWT (jwt.io with the secret) and inspect.

**"My tool function uses `partner_id` from the args, but the LLM keeps
sending the wrong one."**

You're hitting the right pattern but trusting the wrong source. Even
though dispatch overrides `partner_id` from the JWT (delta § 14.2 +
§ 14.4), it's safer to ignore the arg and read
`env.user.partner_id.id` directly — that's *always* the verified
caller. `list_my_kitchen_projects` and `list_my_recommendations` show
this pattern (delta § 14.4 rewrote them to ignore the arg).

**"I want to return rich data structures (datetimes, recordsets) from a
tool."**

The dispatch JSON-encodes the return value with `json.dumps(result,
default=str)`. Datetimes serialize to ISO strings via `default=str`.
Recordsets serialize to their `__repr__` (not what you want). For
recordsets, convert to a list of dicts inside the tool. For complex
types, build a plain dict.

**"My tool raises `UserError` because the partner can't access the
record. The LLM gets a 500."**

Yes — dispatch's outer `try/except` catches all exceptions and returns
500 `tool_exception` with the exception message. That's the spec's
"graceful surrender" path — the LLM sees the error result and either
recovers (calls a different tool) or surrenders ("I can't reach that
data right now"). If you want a cleaner result, catch the exception
inside the tool and return `{"error": "...", "code": "..."}` instead
of raising. Compare `list_my_kitchen_projects` (returns `[]` if the
model doesn't exist) vs `get_kitchen_project` (raises `MissingError`).

## What the system is doing behind the scenes

### Why a process-level list, not a database table

The registry is rebuilt from source on every Odoo restart. There's no
state to lose. Putting it in a database table would require migrations
on every tool change and would add a query for every registry lookup.
A Python list is simpler, faster, and the source of truth is the
decorated function — exactly where a developer expects.

### Why the function arg `parameters=None` exists

For most tools, the auto-extracted schema from `inspect.signature` is
sufficient. For tools with enums (e.g. `recommendation_type` ∈
{task/risk/note/followup}) or nested objects (e.g. `payload: dict`
with required keys), you want richer JSON Schema. The decorator
accepts an explicit override:

```python
@hermes_tool(
    personas=["trade_partner"],
    tier="T2",
    scope="own",
    description="...",
    parameters={
        "type": "object",
        "properties": {
            "intent": {
                "type": "string",
                "enum": ["request_revision", "request_install_reschedule",
                         "request_clarification"]
            },
            "payload": {"type": "object"},
            "summary": {"type": "string"},
        },
        "required": ["intent", "payload", "summary"],
    },
)
def propose_recommendation(env, intent, payload, summary, ...):
    ...
```

Currently `propose_recommendation` ships with auto-extracted schema —
the explicit override would be a future polish (would help the LLM
emit a valid `intent` without trial-and-error).

### Why the dispatch returns the result raw, not wrapped

```python
return self._json(result)
```

Where `result` is whatever the tool returned. The sidecar gets the raw
dict (or list) as the tool result and passes it to the LLM as the
function-call result. There's no `{"ok": true, "result": ...}` envelope.
Errors ARE wrapped (`{"error": ..., "code": ..., "detail": ...}`) so the
sidecar can distinguish — but successful results are raw, matching the
sidecar's `dispatch(slug, args, jwt)` contract.

### The qualified slug — why prefix with tenant

`qualified_slug = f"southbrook__{slug}"` is the per-tenant prefix from
spec § 4.4 rule 3. When v1.x adds a second tenant (Porterly), each
tenant's tools register as `porterly__list_my_orders`,
`southbrook__list_my_orders`. The sidecar uses the qualified name in
the LLM's function definitions so a tool call routed to the wrong
tenant would mismatch and 404. Today, with one tenant, the prefix is
inert — but it's wired in so v1.x doesn't need a migration.

## Quiz (5 questions, applied)

**1.** You add a tool decorated `@hermes_tool(personas=["sales_rep"],
tier="T1", scope="own_order", description="…")`. A trade partner
chats with Fabio and asks something only this new tool can answer.
Why doesn't the LLM call it?

> Because the LLM doesn't know it exists. Trade partners hitting
> `GET /api/hermes/tools` get a filtered list that includes only tools
> whose `personas` includes `"trade_partner"`. Your tool's `personas`
> is `["sales_rep"]` only, so the trade partner sees no tool with this
> capability and the LLM doesn't generate a call for it. To fix: add
> `"trade_partner"` to the personas list — assuming the tool's scope
> actually permits trade-partner use.

**2.** You add a tool and verify it shows up in `TOOL_REGISTRY` via
the Odoo shell, but `GET /api/hermes/tools` returns the OLD list. The
JWT is fresh. What's the most likely cause?

> The Odoo container has the new code; the sidecar has cached the
> registry from an earlier call. The sidecar caches per
> `tenant::persona::tier` (delta § 14.8); cache survives cold-start
> warmups but not actual cold starts. Force a sidecar redeploy:
> `vercel deploy --prod`. Alternatively, the Odoo container hasn't
> actually reloaded the addon — `docker restart southbrook-odoo` or
> `-u southbrook_hermes` would also be required.

**3.** A tool function is declared `def my_tool(env, order_id: int,
persona: str)`. Dispatch is called with body `{"order_id": 42,
"persona": "mfg_manager"}`. What value does the function see for
`persona`?

> The JWT's verified persona claim, NOT `"mfg_manager"`. Dispatch
> inspects the function signature, sees that `persona` is declared,
> and overrides the request-body value with `claims["persona"]` before
> calling. This is delta § 14.2 — closes the prompt-injection
> self-attribution hole.

**4.** A new developer writes a read tool that uses `.sudo()` to fetch
records "because the test wasn't working otherwise." Code review
flags this. Why is `.sudo()` banned in tools by default?

> Spec § 4.4 rule 2. Record rules are how Odoo enforces who can read
> what; `.sudo()` bypasses them. If a tool uses `.sudo()`, a trade
> partner could read data belonging to other partners, violating the
> persona ACL boundary. The only allowed exception is "explicitly
> tier-gated T2 tools with a documented reason" — for example,
> `propose_recommendation` uses `.sudo()` to create the recommendation
> because draft recs are owned by the Fabio partner, not the
> requester, and reviewers need to see them regardless of who proposed.

**5.** You're debugging a 403 `partner_has_no_user` response from
dispatch. What does this mean, and how do you fix it?

> The JWT's `partner_id` claim resolved to a real `res.partner`, but
> that partner has no linked `res.users` record. Dispatch refuses to
> fall back to `request.env.user` (the public user on this
> `auth='public'` route) because that would run every tool with the
> least-privileged identity (delta § 14.3). Fix: open the partner
> record in Odoo → click "Grant portal access" → confirm. The newly
> created portal user gets linked via `res.partner.user_ids` and the
> next tool call dispatches cleanly.

---

## What this lesson does NOT cover

- The 9 read tools individually, with their scoping detail —
  lesson 13.5.
- The 4 write tools and the T0/T1/T2 tier model — lesson 13.6.
- JWT mint / verify / persona resolution internals — lesson 13.3.
- The OWL chat panel and sidecar streaming wire — lesson 13.7.
- The recommendation queue side effects (what happens after
  `propose_recommendation` succeeds) — lesson 13.2.
- The Fabio recommendation approval flow — lesson 3.2.
