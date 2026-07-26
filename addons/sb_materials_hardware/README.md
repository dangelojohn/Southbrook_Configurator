# Southbrook Materials — Hardware Catalog (`sb_materials_hardware`)

## What this is

This addon is a **catalog layer**, not a data owner. It ships a single Odoo
backend client action — an internal, faceted, spec-first table of hardware,
tooling and shop consumables — but it holds no taxonomy, no spec fields, and
no stock or consumption logic of its own. Everything it displays is read
from `southbrook_mrp_kitchen_tools`, which defines the 101-category tool
tree (`southbrook.tool.category`) and roughly 61 typed spec fields
(`x_southbrook_*`) living directly on `product.template`. If you uninstall
`southbrook_mrp_kitchen_tools`, this module has nothing left to show; if you
edit `sb_materials_hardware`, you are never editing anyone's stock levels,
BOMs, or tool-crib records.

The frontend is one OWL component (`static/src/catalog/catalog.js` +
`catalog.xml` + `catalog.scss`) that renders whatever a provider hands it —
a category rail, a set of facet chips, a results table, and a detail panel
for the selected row. It has no idea what a "confirmat screw" or an
"abrasive disc" is; it only knows the shape of the payload.

## Why there are two provider files

`models/catalog_provider.py` defines `materials.catalog.provider`, an
abstract model that is the entire contract between frontend and backend: two
methods (`get_catalog`, `get_detail`), a scope dispatcher (`SCOPES`), and a
couple of domain-agnostic helpers (the "degrade instead of crash" logic, and
`_numeric_prefix`, used for sorting facet chips like grit sizes). Nothing in
this file may reference `x_southbrook_*` fields or `southbrook.tool.category`
by name.

`models/tools_catalog_provider.py` defines `tools.catalog.provider`, which
inherits that contract and is the **only** file in the module allowed to
know about the tools/consumables domain. It is registered under the
`"tools"` scope key. The reason for the split is that a second data domain —
say, a future sheet-goods or fastener-hardware provider sourced from a
different model — becomes a new sibling file implementing the same
contract and registered under a new scope key, not a rewrite of this one.
If you ever find yourself adding an `if scope == "tools":` branch anywhere
outside `tools_catalog_provider.py`, that is the sign the boundary is being
violated.

## The declaration model

Which spec fields show up as table columns or facet chips for a given
category is not hard-coded — it is data, expressed as
`materials.catalog.column` and `materials.catalog.facet` records
(`models/catalog_declaration.py`), each pointing at a `category_id` and a
`field_name` on `product.template`. Adding a facet or column of an existing
type (say, another `enum_distinct` chip group, or another right-aligned
numeric column) is purely a data change: create a record, no code touched.

Declarations cascade down the category tree. A declaration made on a parent
category applies to every descendant category too, and when the same
`field_name` is declared at more than one level, the **nearest** declaration
wins — a child category's label or facet type for that field overrides
whatever an ancestor declared. This is implemented once, identically, for
both columns and facets (`_columns()` and `_facets()` in
`tools_catalog_provider.py`), by walking `parent_path` and letting a
`{field_name: declaration}` dict get overwritten in nearest-first order.

Be honest about where that flexibility ends, though: adding a **new facet
type** (something beyond the existing `enum`, `enum_distinct`, `range`,
`m2m`, `flag`) is not a data change. It requires editing three places in
lockstep:

1. `FACET_TYPES` in `catalog_declaration.py`, so the new type can even be
   selected on a `materials.catalog.facet` record.
2. The corresponding branch in `_facets()` in `tools_catalog_provider.py`,
   which decides how that facet's `values` (or `min`/`max`) get built.
3. The branching in `catalog.xml` (and, if the interaction needs it,
   `catalog.js`) that decides how that facet type renders — chips, a range
   pair of inputs, or something new entirely.

Skipping any one of the three leaves either a facet type nothing can select,
a declaration that builds no values, or a chip type the frontend silently
fails to render. There is no shortcut here; treat it as three edits, not
one.

## Access

A plain internal user (`base.group_user` alone) cannot open this catalog.
`southbrook_mrp_kitchen_tools` grants read access on `southbrook.tool.category`
only to `group_tool_operator` (and groups that imply it); every catalog
call ultimately touches that model — `get_catalog` always calls
`_categories()`, and `get_detail` enforces the same check explicitly before
assembling any data (see the comment on `_build_detail` for why that check
had to be made unconditional rather than incidental). This module
deliberately does not elevate past that boundary: there is no `sudo()`
anywhere in `catalog_provider.py` or `tools_catalog_provider.py` — a
compliance test (`tests/test_access.py::test_provider_source_contains_no_sudo`)
greps the source for it — so if a user cannot see the tool category tree in
the rest of Odoo, they cannot see it here either.

## The payload contract

The frontend calls exactly two methods on `materials.catalog.provider`:

- `get_catalog(scope, category_id, facets, search, offset, limit)` returns
  `{ok, reason, scope, categories, facets, columns, rows, total, provenance,
  detail}`. `categories` is the flat rail tree (id, name, parent_id, count,
  has_children); `facets` and `columns` are what the declaration models
  resolved for the selected category; `rows` is the current page of results;
  `total` is the count *before* pagination is applied.
- `get_detail(product_id, scope)` returns `{ok, title, subtitle, specs,
  engineering, badges}` for one variant — the spec grid (mirroring the
  table's declared columns), the engineering rail (vendor, UoM, stock
  thresholds, lifecycle), and any safety badges (hazardous, flammable, MSDS
  required, and so on).

**Rows are keyed on `product_id`.** The frontend selects and highlights rows
by that key; if it is ever renamed, rows silently stop being selectable
without throwing anything. Both methods degrade to `{"ok": False, "reason":
...}` (with every other contract key still present as an empty value) on
any exception — the catalog is designed to never hand the client action a
500.

## Two pieces of code that must not be "simplified"

Both live in `tools_catalog_provider.py`, and both exist because Odoo's ORM
genuinely cannot express what they need to express — they look like they
could be shortened, and shortening them reintroduces a real bug.

**The `Domain.custom(to_sql=...)` range filter**, in `_facet_domain()`. A
numeric spec field (Float/Integer/Monetary) has `falsy_value = 0`, so any
plain domain leaf that would normally exclude an unset value (`!=`, or a
one-sided `>=`/`<=` whose bound straddles zero) gets rewritten by the ORM in
a way that also excludes rows where the value is a genuine, deliberately
recorded `0`. There is no combination of ordinary tuple leaves that means
"the column is NOT NULL, but if it holds an honest zero, count it" — every
leaf goes through that same falsy-value rewrite. `Domain.custom` bypasses
the rewrite entirely and emits the SQL condition directly (`IS NOT NULL AND
>= ... AND <= ...`), nested under a `product_tmpl_id` "any" relation so it
still composes with the rest of an ordinary domain list. This mirrors a
pattern Odoo core itself uses for the same class of problem (see
`purchase.order._search_is_late`). Replacing it with a "simpler" plain
domain leaf will pass most manual testing and then quietly drop every
product whose spec is a real `0` as soon as the filter's bound happens to
include zero.

**The SQL-level NULL detection (`_null_mask()`)**, used by both `_rows()`
and `_build_detail()`. `read()` cannot tell you whether a Float/Integer/
Monetary column was never set or was set to `0` — both come back as `0`/
`0.0` through the ORM, because Python has no NULL for those types the way
Postgres does. `_null_mask()` runs one extra batched SQL query per page
(never per row) asking Postgres directly which of those columns are
actually `NULL`, and that answer — not the ORM's read — is what decides
whether a cell renders as `—` (absent) or `0` (a genuine recorded zero).
`VALUE_IS_NEVER_ABSENT` and `NUMERIC_AMBIGUOUS_TYPES` exist specifically to
scope this: Boolean is excluded from the ambiguous set because a Boolean
column really does round-trip `False` honestly through `read()`, so it never
needs the SQL mask to mean what it says. Dropping this query and trusting
`read()` alone for numeric absence will make every real `0` indistinguishable
from "never entered."

## Frontend notes (pagination, search)

`get_catalog` supports `offset`/`limit` server-side (default `limit=80`, and
the frontend's default page size matches it exactly). The client action
tracks `offset` in component state and resets it to `0` whenever the
category, a facet, or the search text changes — otherwise a narrower result
set could leave you stranded on a page that no longer exists. The results
bar reports "Showing X–Y of Z" from that state, and Prev/Next controls are
hidden entirely when everything fits on one page.

Search input is debounced (~280ms) so a burst of typing sends one request,
not one per keystroke; the pending timer is cancelled on component teardown.
Every `load()` call is stamped with a monotonically increasing request id,
so if a slow in-flight request is superseded by a newer one (a fast category
click while a debounced search response is still in flight, for instance),
the stale response is discarded on arrival instead of overwriting a newer,
correct one.

## Running the tests

The module's own test suite runs under the `sbk_mathw` tag against the
`southbrook` database inside the running `sami-odoo` container:

```bash
docker exec sami-odoo bash -lc 'odoo -d southbrook -u sb_materials_hardware --stop-after-init --test-enable --test-tags=sbk_mathw --db_host="$HOST" --db_user="$USER" --db_password="$PASSWORD"'
```

Any code-only change to `static/src/catalog/*` needs a container **restart**
(not just `-u`) before it shows up in the browser — Odoo's asset bundle is
keyed by a hash computed at boot, and `-u` alone can leave the old bundle
being served even though the source on disk is correct:

```bash
docker restart sami-odoo
```
