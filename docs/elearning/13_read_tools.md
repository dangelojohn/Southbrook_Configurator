---
course: 13 — Fabio Deep Dive
chapter: 13.5
title: The Nine Read Tools — Source, Scope, and ACL
duration: 45 minutes
audience: Developer working in `tools/read_tools.py`; power-user / admin who needs to know what data Fabio can see for each persona
prereqs: Lesson 13.4 (`13_tool_registry.md`) for the decorator + dispatch picture; lesson 13.3 (`13_jwt_auth_personas.md`) for persona + tier; spec § 6 (tool catalog) at `docs/superpowers/specs/2026-06-16-southbrook-os-and-hermes-platform-design.md`
custom_modules: southbrook_hermes
---

# The Nine Read Tools — Source, Scope, and ACL

## Who this lesson is for

You're the developer about to modify one of the nine read tools, or
add a tenth. You're the admin trying to answer "what can a trade
partner see through Fabio?" with precision. You're the auditor reading
the source and wanting an inline guide to each function.

Every read tool ships in `addons/southbrook_hermes/tools/read_tools.py`.
This lesson walks through each one in registration order, with the
persona allowlist, the data returned, the ACL boundary, an example
invocation, and the common confusions.

## Where this lives on the site

You don't see the read tools on a screen — they're invoked by the LLM
through `POST /api/hermes/tools/<slug>`. But the registry that
declares them is the canonical inventory, browsable two ways:

> **`GET /api/hermes/tools`** — with a fresh JWT (from `scripts/smoke_hermes.sh`),
> returns the list filtered to your persona. The read tools live in
> the first nine entries.

> **`odoo-bin shell` → `from odoo.addons.southbrook_hermes.tools.decorator import TOOL_REGISTRY; [t['slug'] for t in TOOL_REGISTRY if t['tier'] == 'T0' and t['slug'].startswith(('list_', 'get_'))]`**

The source file is the authoritative spec; the registry is the runtime
reflection. They never drift because the runtime is built from the
source at import time.

## What your screen shows

Nine read tools, all `tier="T0"`. By personas + scope:

| # | Slug | Personas | Scope | Returns |
|---|---|---|---|---|
| 1 | `list_my_orders` | trade_partner, sales_rep | `own` | List of orders visible to caller's partner |
| 2 | `get_order_status` | trade_partner, sales_rep | `own_order` | Production status of one order |
| 3 | `get_order_line` | trade_partner, sales_rep | `own_order` | Configured detail of one order line |
| 4 | `list_my_kitchen_projects` | trade_partner, sales_rep | `own` | List of kitchen projects |
| 5 | `get_kitchen_project` | trade_partner, sales_rep | `own_order` | Options + approval status of one project |
| 6 | `get_install_schedule` | trade_partner, sales_rep | `own_order` | Install date + risk flag |
| 7 | `get_quote_pdf_url` | trade_partner, sales_rep | `own_order` | Quote PDF URL + expiry |
| 8 | `list_my_recommendations` | trade_partner, sales_rep | `own` | Open recommendations attached to caller's partner |
| 9 | `get_os_section` | trade_partner, sales_rep, mfg_manager | `global` | One named OS section's body + version |

Read tools 1–8 are partner-scoped (own or own_order). Read tool 9
(`get_os_section`) is global — reading the Southbrook OS doesn't depend
on persona. Sales reps and trade partners both get the same eight
partner-scoped tools; sales reps in v1.0 don't have any extra read tools
yet (v1.1 will add their backend-specific surface).

### Tool 1 — `list_my_orders(partner_id: int)`

Personas: `trade_partner, sales_rep`. Tier: T0. Scope: `own`.

```python
def list_my_orders(env, partner_id: int):
    orders = env["sale.order"].search(
        [("partner_id", "=", partner_id)], order="date_order desc", limit=50)
    return [
        {
            "ref": o.name,
            "stage": o.state,
            "partner_name": o.partner_id.name,
            "install_due": (o.commitment_date.isoformat()
                            if o.commitment_date else None),
        }
        for o in orders
    ]
```

Note: `partner_id` is passed in but the actual ACL is the record-rule
scope on `sale.order` running as `env.user` (the portal user resolved by
dispatch). A trade partner whose `partner_id.id == 42` calling with
`partner_id=42` gets their own orders. Calling with `partner_id=99` gets
**nothing** because the record rule denies access — even though the
search domain says `("partner_id", "=", 99)`, the underlying query is
ANDed with the record rule. This is the spec § 4.3 pattern: ACL is the
tool registry + record rules. Note `list_my_kitchen_projects` and
`list_my_recommendations` go one step further (delta § 14.4) and ignore
the `partner_id` arg entirely, keying off `env.user.partner_id.id`. For
`list_my_orders`, the record-rule defense is sufficient.

Example invocation (sidecar perspective):

```http
POST /api/hermes/tools/list_my_orders HTTP/1.1
Authorization: Bearer <JWT with partner_id=42, persona=trade_partner>
Content-Type: application/json

{"partner_id": 42}
```

Returns:

```json
[
  {"ref": "S00235", "stage": "sale", "partner_name": "Smith Cabinetry",
   "install_due": "2026-07-15"},
  ...
]
```

Common confusions:
- "Why does the tool need `partner_id` if the ACL doesn't use it?"
  Because the dispatch's claim-binding (delta § 14.2) writes
  `partner_id` from the JWT, so the tool is *guaranteed* to see the
  verified caller's partner. The record rule then filters. Belt and
  braces.
- "Why a `limit=50`?" Soft cap so the result fits in the LLM's context.
  An LLM seeing 200 orders is going to summarize unhelpfully. 50 is
  the v1.0 ceiling.

### Tool 2 — `get_order_status(order_id: int)`

Personas: `trade_partner, sales_rep`. Tier: T0. Scope: `own_order`.

The richest of the read tools. Returns:
- `stage` (the order's `state`)
- `mos` (count of `mrp.production` records linked via order_line)
- `bottleneck` (current bottleneck work center name, if a
  `sb.kitchen.project` task exists for the order)
- `blocker` (top blocker text from the kitchen project task)
- `next_action` (next-best-action text)
- `install_due` (the kitchen project's `date_deadline`)
- `readiness_score` (the readiness score from the project task)
- `version` (the order's `southbrook_version`, defaulting to 1)

Full implementation:

```python
def get_order_status(env, order_id: int):
    order = env["sale.order"].browse(order_id)
    try:
        order.check_access_rights("read")
        order.check_access_rule("read")
    except Exception:
        raise MissingError("Order not visible to this user.")
    kj = env["project.task"].search(
        [("sale_order_id", "=", order.id)], limit=1)
    return {
        "stage": order.state,
        "mos": _count_mos_for_order(env, order),
        "bottleneck": (kj.southbrook_current_bottleneck_wc.name
                       if kj and getattr(kj, "southbrook_current_bottleneck_wc", False)
                       else None),
        "blocker": (kj.southbrook_top_blocker if kj else None),
        "next_action": (kj.southbrook_next_best_action if kj else None),
        "install_due": (kj.date_deadline.isoformat()
                        if kj and kj.date_deadline else None),
        "readiness_score": (kj.southbrook_readiness_score if kj else None),
        "version": getattr(order, "southbrook_version", 1),
    }
```

ACL boundary:
- `order.check_access_rights("read")` + `order.check_access_rule("read")`
  raise if the partner can't see this order.
- `project.task` + `mrp.production` are searched **without sudo**, so
  the partner's record rules apply. If a record rule hides them (e.g.
  MOs are internal-only by default), the calls degrade to empty results
  and the return dict surfaces `None` — exactly what spec § 4.4
  ACL rule wants.

Example invocation:

```json
{"order_id": 235}
```

Returns:

```json
{
  "stage": "sale",
  "mos": 3,
  "bottleneck": "SB-EDGE",
  "blocker": "Door vendor lead time slipped 2 weeks.",
  "next_action": "Confirm replacement door SKU with planner.",
  "install_due": "2026-07-15",
  "readiness_score": 0.62,
  "version": 1
}
```

Common confusions:
- "Why does `mos` use `sale_order_line_id`, not `sale_id`?" Because
  Odoo's `mrp.production.sale_order_line_id` is the canonical link to a
  sale line (one MO per line); `sale_id` is a denormalized convenience.
- "Why `getattr(kj, 'southbrook_current_bottleneck_wc', False)`?"
  Defensive — the kitchen-ops fields are added by
  `southbrook_kitchen_workspace`. If that addon is uninstalled, the
  tool degrades to None rather than crashing.

### Tool 3 — `get_order_line(order_id: int, line_id: int)`

Personas: `trade_partner, sales_rep`. Tier: T0. Scope: `own_order`.

Returns the configured detail of a single sale order line: SKU,
variant name, qty, attribute key-value dict, retail price, channel
price, flags list.

```python
def get_order_line(env, order_id: int, line_id: int):
    order = env["sale.order"].browse(order_id)
    try:
        order.check_access_rights("read")
        order.check_access_rule("read")
    except Exception:
        raise MissingError("Order not visible to this user.")
    line = order.order_line.filtered(lambda l: l.id == line_id)
    if not line:
        raise UserError(
            f"Line {line_id} does not belong to order {order.name} "
            f"or is not visible to this user.")
    return {
        "sku": line.product_id.default_code or "",
        "variant_name": line.product_id.name,
        "qty": line.product_uom_qty,
        "attributes": {
            v.attribute_id.name: v.name
            for v in line.product_id.product_template_attribute_value_ids
        },
        "retail": line.price_unit,
        "channel": line.price_subtotal,
        "flags": [],
    }

```

ACL boundary: order-level access check, then the `.filtered()` on
`order.order_line` is implicit record-rule (you can only see lines on
orders you can see). If `line_id` doesn't belong to the order or isn't
visible, raises `UserError` — distinguishable from "order not visible"
which raises `MissingError`.

Example invocation:

```json
{"order_id": 235, "line_id": 5891}
```

Returns:

```json
{
  "sku": "WALL-2DR-600-WHT",
  "variant_name": "Wall Cabinet 2-Door 600mm White Shaker",
  "qty": 4.0,
  "attributes": {
    "Family": "Wall Cabinet",
    "Width": "600mm",
    "Series": "Contemporary",
    "Door Style": "Shaker",
    ...
  },
  "retail": 487.50,
  "channel": 1267.50
}
```

Common confusions:
- The `attributes` dict is built from `product_template_attribute_value_ids`
  — the values that distinguish this *variant*. Not from
  `product.config.session` (the configurator's transient state).
- The `flags` list is always empty in v1.0. Reserved for "out of stock,"
  "discontinued," "stale price" warnings; never populated yet.
- "Retail" is `price_unit` (per-unit list price); "channel" is
  `price_subtotal` (qty × unit price with channel discount applied).
  The names are confusing on purpose — they mirror the Estimating brief's
  "retail vs channel" framing.

### Tool 4 — `list_my_kitchen_projects(partner_id: int = None)`

Personas: `trade_partner, sales_rep`. Tier: T0. Scope: `own`.

```python
def list_my_kitchen_projects(env, partner_id: int = None):
    # partner_id is informational only — the authoritative scope comes from
    # the caller's env.user (set by the dispatch controller from JWT claims),
    # so an LLM arg can NOT widen the result set to another partner.
    Project = env["sb.kitchen.project"] if "sb.kitchen.project" in env else None
    if Project is None:
        return []
    projects = Project.search(
        [("partner_id", "=", env.user.partner_id.id)], order="create_date desc")
    return [
        {
            "ref": p.name,
            "stage": getattr(p, "state", None),
            "option_count": len(p.option_ids) if hasattr(p, "option_ids") else 0,
            "selected": next(
                (o.name for o in getattr(p, "option_ids", [])
                 if getattr(o, "is_selected", False)), None),
        }
        for p in projects
    ]
```

This is one of the two tools rewritten in delta § 14.4 to ignore the
`partner_id` arg and key off `env.user.partner_id.id` directly. The arg
is preserved in the signature for backward compatibility and so the
JSON Schema declares it (and so claim-binding still hits it — see lesson
13.4), but the body of the function never reads it.

Returns a list of kitchen projects with stage, option count, and the
name of the currently selected option (if any).

Common confusions:
- "Why `if 'sb.kitchen.project' in env`?" Defensive — if
  `southbrook_kitchen_workspace` isn't installed, the model doesn't
  exist. The tool degrades to `[]` instead of crashing.
- "Why is `state` accessed with `getattr`?" Same — the kitchen project
  model might not have the field in every install state.
- "Why don't we use `check_access_rights` here?" Because the search is
  already scoped to `env.user.partner_id` — a partner querying their
  own projects. Record rules then filter further if needed. The
  pattern is "explicit scope + record rules" not "explicit access
  check."

### Tool 5 — `get_kitchen_project(project_id: int)`

Personas: `trade_partner, sales_rep`. Tier: T0. Scope: `own_order`.

Returns one project's options list (each with `name` + `is_selected`),
the project's `approval_status`, and a `drawings_url`. Full access
check pattern:

```python
project.check_access_rights("read")
project.check_access_rule("read")
```

Both checks present; raises `MissingError("Project not visible to this
user.")` on either failure. The two failure modes are model-level ACL
(can the user read the *model*?) and record-rule (can this user read
*this record*?). Production-side wisdom: prod users almost always have
model-level read; the record-rule check is the one that actually fires
when a trade partner asks about a kitchen project belonging to a
different partner.

Common confusions:
- The returned `options` list comes from `getattr(project,
  "option_ids", [])` — defensive against the field not existing.
- `approval_status` and `drawings_url` are read with `getattr` and
  default to None — these may not exist in every install.

### Tool 6 — `get_install_schedule(order_id: int)`

Personas: `trade_partner, sales_rep`. Tier: T0. Scope: `own_order`.

Returns the order's `commitment_date`, `delivery_status` (Odoo native
field), and risk flag + reason. As of v1.0, `risk_flag` is always
`"unknown"` and `risk_reason` is `None`:

```python
return {
    "date": (order.commitment_date.isoformat()
             if order.commitment_date else None),
    "dispatch": getattr(order, "delivery_status", None),
    "risk_flag": "unknown",
    "risk_reason": None,
}
```

The risk fields are reserved for v1.1 — the manufacturing intelligence
side hasn't been wired into the read path yet. The tool answers the
schedule question; "is it at risk?" gets a placeholder.

Delta § 14.5 added `check_access_rule` here. Originally only
`check_access_rights` was called.

Common confusions:
- "Why doesn't this tool read the kitchen project task's
  `date_deadline` like `get_order_status` does?" Because the spec
  groups install date with sale order's `commitment_date`. If the
  customer-facing date differs from the planned production date, we
  show the commitment date (what the partner was promised).

### Tool 7 — `get_quote_pdf_url(order_id: int)`

Personas: `trade_partner, sales_rep`. Tier: T0. Scope: `own_order`.

```python
def get_quote_pdf_url(env, order_id: int):
    order = env["sale.order"].browse(order_id)
    try:
        order.check_access_rights("read")
        order.check_access_rule("read")
    except Exception:
        raise MissingError("Order not visible to this user.")
    base_url = env["ir.config_parameter"].sudo().get_param("web.base.url", "")
    return {
        "pdf_url": (f"{base_url}/my/orders/{order.id}?report_type=pdf"
                    if base_url else None),
        "valid_until": (order.validity_date.isoformat()
                        if order.validity_date else None),
    }
```

Builds the URL from the Odoo native portal report path. Returns
`valid_until` from `order.validity_date`. Note the `.sudo()` on
`ir.config_parameter` — this is reading a global system parameter
(`web.base.url`), not partner data, so it's allowed under spec § 4.4
rule 2.

Common confusions:
- The URL is the *portal* report path, not the backend report path —
  so a trade partner clicking it gets the customer-facing PDF, not the
  internal "Order Builder" PDF.
- `valid_until` may be None for confirmed orders (`validity_date`
  applies to quotations, not sales orders).

### Tool 8 — `list_my_recommendations(partner_id: int = None)`

Personas: `trade_partner, sales_rep`. Tier: T0. Scope: `own`.

```python
def list_my_recommendations(env, partner_id: int = None):
    Rec = env["southbrook.hermes.recommendation"] if (
        "southbrook.hermes.recommendation" in env) else None
    if Rec is None:
        return []
    recs = Rec.search([
        ("source_model", "=", "res.partner"),
        ("source_res_id", "=", env.user.partner_id.id),
        ("state", "in", ("draft", "ready")),
    ], order="create_date desc")
    return [
        {
            "rec_id": r.id,
            "type": r.recommendation_type,
            "summary": r.summary or "",
            "state": r.state,
        }
        for r in recs
    ]
```

The other delta § 14.4 tool. Like `list_my_kitchen_projects`, ignores
`partner_id` arg, keys off `env.user.partner_id.id`. Filters to
`source_model='res.partner'` (i.e. partner-scoped recommendations) AND
`source_res_id=<caller>` AND `state in ('draft', 'ready')` (only what's
still in the open queue).

Note this doesn't include `approved` or `applied` recommendations.
Trade-partner-facing view is "what's pending review on my behalf" —
once approved or rejected, it falls off the partner's radar (but
remains visible to reviewers in the Fabio menu — different surface,
same database).

### Tool 9 — `get_os_section(slug: str)`

Personas: `trade_partner, sales_rep, mfg_manager`. Tier: T0. Scope:
`global`.

```python
def get_os_section(env, slug: str):
    Section = env["southbrook.os.section"].sudo()
    section = Section.search([("slug", "=", slug)], limit=1)
    if not section:
        raise MissingError(f"OS section '{slug}' not found.")
    return {
        "slug": section.slug,
        "name": section.name,
        "version": section.version,
        "source": section.source,
        "body": section.body,
    }
```

The only read tool available to all three personas — every persona can
read the Southbrook OS. The only read tool that uses `.sudo()` — this
is the explicit § 4.4 carve-out for "global, partner-independent
reads." There's no record rule on `southbrook.os.section` that varies
by user; the OS is the same for everyone.

Example invocation:

```json
{"slug": "07_partner_faq"}
```

Returns:

```json
{
  "slug": "07_partner_faq",
  "name": "Partner FAQ",
  "version": 3,
  "source": "canonical",
  "body": "# Partner FAQ\n\n## 1. Where is my kitchen?\n..."
}
```

Common confusions:
- "Why is `slug` a Char rather than a Selection?" Because the LLM
  picks the slug from RAG context — having a fixed list constrains
  the LLM but adds rigidity. The trade-off was: free-form slug,
  raise `MissingError` if not found, and the LLM recovers.
- "Why `.sudo()`?" The section model has no partner scope; the OS is
  global. The sudo is a deliberate § 4.4 exemption with a documented
  reason. Don't replicate this pattern in partner-scoped tools.
- "Why doesn't the OS section model have a `published` flag?" It
  effectively does via `southbrook.os.publication` (lesson 13.1) — but
  `get_os_section` returns the current (latest) section, not a
  publication snapshot. v1.0 trade-off: the partner sees what's true
  now, not what was true at order time. v1.1 may add a publication-
  scoped read.

## Your daily flow

### As a developer adding a tenth read tool

1. Decide what data your tool returns. Make sure it's something a
   trade partner is allowed to see (spec § 6 "Explicit non-tools" lists
   v1.0 exclusions — no billing, no payments, no cross-partner data).
2. Decide the scope honestly. `own` if the returned data is
   partner-wide (a list); `own_order` if it's order-specific; `global`
   if it's Southbrook-wide.
3. Write the function with `partner_id: int` (or `order_id: int`,
   etc.) as the leading arg. Type hints become the JSON Schema.
4. Add **both** `check_access_rights` and `check_access_rule` for the
   record-bounded reads. Delta § 14.5 fixed three tools that missed
   `check_access_rule`; new tools start with both.
5. Don't use `.sudo()` unless you're reading global config. Document
   any `.sudo()` use case in the comment.
6. Return a JSON-serializable dict (or list of dicts). Datetimes:
   call `.isoformat()`. Recordsets: convert to id lists or name
   dicts.
7. Add an OS section that documents the concept the tool exercises
   (the spec § 5.6 coverage test enforces this in CI).

### As an admin tracing "what can Fabio see?"

For a given trade partner X:
1. Find their `res.partner` id.
2. Run a smoke test as that partner (or impersonate via a fresh JWT
   from the Odoo shell).
3. Hit `GET /api/hermes/tools` — you'll see 9 tools.
4. For each tool, invoke with a representative payload. The empty
   responses are the answer to "what can't they see."

This is the answer to compliance questions: "show me what data this
trade partner can access through chat" — it's exactly the 9 tools'
outputs.

### As a power user understanding why an answer is incomplete

If Fabio gives you a thin answer to "where is my kitchen?", it's
almost always because one of the read tools returned `None` for an
expected field. Common causes:

- The kitchen project doesn't have a task yet (no `sb.kitchen.project`
  → `project.task` mapping). `get_order_status` returns
  `bottleneck=None`, `blocker=None`, etc.
- The record rule on `mrp.production` denies trade-partner reads.
  `mos=0` even though the order has MOs.
- The order's `commitment_date` isn't set. `install_due=None`.

The tools are reading honestly. The answer reflects the data.

## Common mistakes + how to recover

**"`list_my_orders` returns an empty list but the partner clearly has
orders."**

Most likely: the partner's user doesn't have a record rule granting
access to `sale.order` records where `partner_id == self.partner_id`.
Check **Settings → Technical → Security → Record Rules** → filter by
`Model = sale.order`. The portal user (`base.group_portal`) should
have a rule like `("partner_id", "=", user.partner_id.id)`. If it's
missing, the search returns nothing.

**"`get_order_status` returns `bottleneck=null` but I know the order
has a bottleneck."**

`bottleneck` comes from `project.task.southbrook_current_bottleneck_wc`,
which is set by the kitchen-workspace addon. Two failure modes:
- No `project.task` exists for the order (no `sale_order_id` link).
- The task exists but `southbrook_current_bottleneck_wc` isn't computed
  yet (the orchestration cron hasn't run).

Check the actual project.task record manually.

**"`get_quote_pdf_url` returns a URL but the partner gets 404."**

The URL is `<base_url>/my/orders/<id>?report_type=pdf` — the partner
needs to be logged in to the portal. The URL works for the logged-in
partner only. If you're sharing the URL out-of-band (email, chat), the
recipient must already have a portal session.

**"`list_my_recommendations` returns `[]` but I see drafts in **Fabio →
Recommendations**."**

The drafts in the menu are filtered by
`source_model='res.partner'` AND `source_res_id=<caller's partner id>`
AND `state in ('draft', 'ready')`. If the drafts visible in the menu
have a different `source_model` (e.g. `sale.order`), or the partner
ID doesn't match, the tool won't return them. Also: applied and
rejected recommendations are NOT in the tool's filter — that's
intentional.

**"I added a `Optional[int]` arg with a default and the JSON Schema
doesn't reflect it."**

`_extract_params_from_signature` only checks for `int`, `bool`,
`float`, defaults to `string`. `Optional[int]` becomes `"string"` in
the auto-extracted schema. If you want richer schema, pass
`parameters=` explicitly to the decorator.

## What the system is doing behind the scenes

### Why read tools are uniformly T0

The spec § 4.2 tier matrix puts all read operations at T0. The
distinction T0 vs T1 vs T2 is about *write impact*, not read
sensitivity. Reading data is universally T0; only writes split by
tier.

### Why so many `getattr(..., default)` calls

Two reasons:
- **Defensive against partial installs.** If `southbrook_kitchen_workspace`
  or `southbrook_premium_orchestration` is installed without all its
  fields, the tools should degrade gracefully rather than crash.
- **Defensive against future field renames.** If a downstream addon
  renames `southbrook_top_blocker` to `southbrook_blocker_text`, the
  `getattr` fallback returns None instead of crashing. The tools then
  show "no blocker info" — degraded but functional.

The pattern is repeated extensively across `get_order_status` and
`get_kitchen_project` because those tools read fields from addons
that ship separately.

### Why `_count_mos_for_order` is a separate function

Trivially reusable. Could be inlined. Kept separate because the count
might evolve (e.g. "count only MOs in 'progress' state for this order")
and a separate function is easier to test and modify.

### The shape of "what a tool returns"

Every read tool returns either:
- A dict (one record) with stringy keys and JSON-serializable values.
- A list of dicts (collection).
- An empty list/empty dict (no data visible) — never None.

Errors are raised as `MissingError` (caught by dispatch as 500) or
`UserError` (also caught as 500). Both result in
`{"error": "tool_exception", "detail": "...", "tool": <slug>}` to the
sidecar, which surfaces it as a tool-error result to the LLM, which
recovers gracefully ("I can't reach that data right now.").

The reason for never returning None: the LLM treats None as "I don't
know" rather than "the data isn't here." Returning `[]` or
`{}` or a dict with explicit None values is clearer.

### Why `get_os_section` is the only tool available to mfg_manager

Sales reps and mfg managers will get their own read tools in v1.1 and
v1.2 respectively. v1.0 only ships the trade-partner / sales-rep
overlapping eight, plus the universal OS-section reader. A mfg manager
asking "where is order S00235?" today gets nothing back from any of
the 8 tools, because none include `mfg_manager` in their
personas list. The OS section is the only useful answer they can get
through the chat panel.

### Why dispatch catches all tool exceptions

`hermes_tools_api.dispatch`:

```python
try:
    result = fn(env_with_user, **args)
except Exception as e:
    _logger.exception("Tool %s raised", slug)
    return self._json(
        {"error": "tool_exception", "detail": str(e), "tool": slug},
        status=500)
```

Bare `Exception` catch is deliberate. The dispatch is the boundary
between the LLM (which expects a JSON result, success or error) and the
Odoo ORM (which raises a zoo of exception types). Catching `Exception`
+ logging + returning a 500 with the exception's `str()` lets the LLM
recover and the developer debug. Without the catch, an unhandled
`AttributeError` deep inside a tool would propagate to the sidecar as
HTML, breaking the JSON parsing on the sidecar side.

## Quiz (5 questions, applied)

**1.** A trade partner asks Fabio "where is my kitchen?" and the LLM
calls `get_order_status(order_id=235)`. The order belongs to a
*different* partner. What does the tool return?

> `MissingError("Order not visible to this user.")` from
> `check_access_rule`. Dispatch catches the exception and returns
> 500 `tool_exception` to the sidecar. The LLM sees the error result
> and surrenders gracefully ("I don't have access to that order.").
> The data is protected at the record-rule layer; the tool just
> surfaces the denial as a clean error.

**2.** A sales rep tries calling `get_kitchen_project(project_id=42)`
where project 42 belongs to a partner they don't manage. What
happens?

> Depends on the sales rep's record rules. Native Odoo gives
> salesmen access to records they're assigned to (`user_id ==
> self.id`), but kitchen projects' record-rule scope was set by
> `southbrook_kitchen_workspace`. If the sales rep can't see project
> 42, `check_access_rule` raises and dispatch returns
> `tool_exception`. The data is protected the same way for sales rep
> as for trade partner — record rules are the single source of truth.

**3.** You add a tool `get_order_invoices(order_id: int)` that returns
the order's invoices. A trade partner asks about an invoice. The
tool returns `[]`. Why?

> Almost certainly because the partner has no read access to
> `account.move` records. Trade partner record rules typically scope
> `account.move` by `partner_id == user.partner_id`, but the join from
> sale.order to its invoices may fail under that rule. Test the
> record rule explicitly. The empty list isn't a tool bug; it's a
> deliberate ACL outcome. To verify, run the search as the partner
> user in the Odoo shell.

**4.** A trade partner sees a recommendation in the **Fabio → My
Recommendations** view of the portal but `list_my_recommendations`
returns `[]`. What's the mismatch?

> The tool filters `state in ('draft', 'ready')`. The portal view
> probably also includes `approved` or `applied` recommendations.
> Once a draft is approved (by a reviewer in the backend), it falls
> out of the tool's filter but remains in the portal view. The
> mismatch is intentional — the tool surfaces "what still needs your
> input" rather than "your full history."

**5.** A developer adds a `risk_flag` computation to
`get_install_schedule` that reads `order.commitment_date - today` and
compares to the order's MO lead times. The computation calls
`mrp.production.search([...])`. A trade partner gets a thin answer
where `risk_flag` is always "unknown." Why?

> The trade partner can't read `mrp.production` records via record
> rule. The search returns empty; the computation degrades to
> "unknown." Two paths: (a) add a record rule granting trade
> partners read access to MOs linked to their orders (data exposure
> decision), or (b) route the computation through a partner-visible
> model (e.g. a denormalized `sale.order.x_lead_time_max` field
> computed nightly).

---

## What this lesson does NOT cover

- The 4 write tools and the T0/T1/T2 tier model — lesson 13.6.
- The tool registry mechanics (decorator, dispatch, ACL layering) —
  lesson 13.4.
- JWT mint + verify + persona resolution — lesson 13.3.
- The recommendation queue side — lesson 13.2.
- The chat panel + sidecar streaming — lesson 13.7.
- Adding new record rules to widen trade-partner data access — that's
  a separate Odoo skill, not Fabio-specific.
