---
course: 9 — ProductGraph
chapter: 9.1
title: ProductGraph — What It Is, Where It Lives, Why It's Next To Odoo
duration: 30 minutes
audience: Anyone who'll touch ProductGraph — PLM engineer, estimator, dev, IT admin
prereqs: Lesson 4.1 (ECOs) gives helpful context; not required
custom_modules: product_graph_base, product_graph_revision, product_graph_ebom, product_graph_release, product_graph_api, product_graph_relationship, southbrook_plm_productgraph
---

# ProductGraph — What It Is, Where It Lives, Why It's Next To Odoo

## Who this lesson is for

You will hear "ProductGraph" mentioned in three kinds of conversations and
it means slightly different things in each. If you're an engineer about to
author a property template, an estimator wondering why the price catalog
won't show a part, or an IT admin staring at a `product-graph-mcp`
container in the QNAP stack, this is the lesson that gives you the map.
After this you'll know which side of the platform owns what, and which
URL to point at when you need to look something up.

## Where this lives on the site

ProductGraph is **two codebases sitting next to each other**, not one
addon. That's the most important thing to internalise:

| Side | Where it runs | What it is | Repo on disk |
|---|---|---|---|
| Standalone platform | Same Odoo container as Southbrook (currently) | 5 Odoo addons + a Python sidecar — generic, publishable, LGPL-3 | `~/product_graph_v19/` |
| Southbrook bridge | The Southbrook Odoo container | One addon — proprietary, glues Southbrook ECOs to ProductGraph releases | `~/southbrook-v19cr/addons/southbrook_plm_productgraph/` |
| Closure helper | The Southbrook Odoo container | Materialised graph closure for relationship lookups | `~/southbrook-v19cr/addons/product_graph_relationship/` |

In the Odoo backend you'll see ProductGraph menus mixed in with native
Odoo menus:

> **Manufacturing → ProductGraph → Items**
> **Manufacturing → ProductGraph → EBOMs**
> **Manufacturing → ProductGraph → Releases**
> **Manufacturing → ProductGraph → Property Templates**

The MCP sidecar runs in its own container (`product-graph-mcp`) and is
not part of any Odoo menu — that's an HTTP/SSE endpoint Claude and other
LLM agents talk to.

## What your screen shows

When you open **Manufacturing → ProductGraph → Items** (the generic
platform side, served by `product_graph_base`):

- **Part number** (`part_number` on `pg.item`) — system-assigned. Prefix
  depends on item type: `PG-ASM-NNNN` for assemblies, `PG-PRT-NNNN` for
  manufactured parts, `PG-BUY-NNNN` for purchased, `PG-DOC-NNNN` for
  documents, `PG-SFT-NNNN` for software, `PG-SVC-NNNN` for service. The
  prefix is set by per-type sequences (`_ITEM_TYPE_SEQUENCE` map in
  `pg_item.py`).
- **Item type** (`item_type`) — drives the prefix above AND which
  property templates the item can attach.
- **Status** (`state` on `pg.item`) — the 6-state lifecycle:
  `concept → prototype → engineering → released → service → obsolete`.
  Once an item reaches `released`, it is **immutable at the ORM level**
  — only chatter, tags and a handful of admin fields can change.
- **Property Templates** (`property_template_ids`, many2many to
  `pg.property.template`) — zero or more templates attached to this
  item. See lesson 9.2.
- **Revisions** (smart button) — opens `pg.revision` records for this
  item. Revisions carry the property *values*; items carry the
  *templates*.
- **EBOMs** (smart button) — engineering BOMs rooted at this item.
- **MRP BOMs** (smart button) — `mrp.bom` records that came out of a
  `pg.release` for this item. **The only path** to those is through a
  release; nothing else writes `mrp.bom` from ProductGraph.

Compare against native Odoo PLM (`mrp_plm`) and `southbrook_plm`: those
two store **ECOs and cut specs** (the manufacturing decisions);
ProductGraph stores **the engineering catalog** (the design intent that
those decisions are made about).

## Your daily flow

**1. Decide which side you're on.**

If the question is *"what's the canonical engineering structure of this
cabinet assembly"* — that's ProductGraph. Open the `pg.item`, read its
released revision, look at the EBOM lines, check the property values.

If the question is *"who's approving the ECO that swaps this hinge"* —
that's `southbrook_plm`. The ECO record (`southbrook.eco`) lives there.
The bridge addon adds a *pointer* from the ECO to a ProductGraph EBOM,
but the ECO itself stays in `southbrook_plm`.

If the question is *"can an AI agent fetch this BoM and propose a
property change"* — that's the MCP sidecar (lesson 9.5).

**2. Read before you write.**

The 5 generic addons enforce hard rules (`R1` through `R9` in
`~/product_graph_v19/CLAUDE.md`). Two of them you'll bump into often:

- **R1 — Release boundary is sacred.** `mrp.bom` is written ONLY by
  `pg.release.action_execute_release`. If you have code that wants to
  touch `mrp.bom`, it's wrong; route it through a release.
- **R3 — No hard deletes on released or historically significant
  records.** `unlink()` overrides on `pg.item`/`pg.revision`/`pg.ebom`/
  `pg.release` reject deletion outside `(draft, obsolete)`. Don't fight
  this; obsolete instead.

**3. Use the bridge addon when you mean to release.**

The Southbrook flow is: author the change in `southbrook.eco`, set the
ECO's `pg_ebom_id` to the released `pg.ebom` you want to push to
manufacturing, leave `pg_auto_release` on, and apply the ECO. The
bridge runs `pg.release.action_execute_release` for you and links the
resulting `pg.release` back onto the ECO. See lesson 9.6.

**4. Check the audit log when something looks wrong.**

`pg.audit.log` (in `product_graph_base`) is append-only, write-blocked,
unlink-blocked. Every state transition, every blocked write, every
release writes a row. **Manufacturing → ProductGraph → Audit Log** is
the first place to look when you can't explain why an item is in the
state it's in.

## Common mistakes + how to recover

**"I want to add a `southbrook_dealer_id` field to `pg.item` because
the dealer determines pricing."**

Don't. The bridge spec (`bridge_spec/SPEC.md` in
`~/product_graph_v19/`) explicitly forbids Southbrook-specific fields
on `pg.*` models — that's how the generic LGPL-3 codebase stays
publishable. Put the field on a new `southbrook.*` model that references
the `pg.item` by m2o instead.

**"I edited a released item's name and got a `UserError: Item X is
Released and immutable`."**

Working as designed. Released items are immutable by ORM override.
Create a new revision and propose the change there. See lesson 9.2 for
the workflow; see lesson 4.1 (ECOs) for who has to approve it.

**"The ProductGraph release ran but no `mrp.bom` appeared. Did it
silently fail?"**

Check `pg.release.state`. If it's `failed`, the release rolled itself
back inside a savepoint (Manufacturing Governance MG-8). Read
`failure_reason` on the release record. Common causes: a child item
isn't `released` (cross-model gate, EBOM Bible §10), or the linked
revision has `incompatible_with_previous=True` and a warehouse
notification is pending acknowledgement (MG-3).

**"My MCP-bot service account's API key expired."**

Odoo 19's default `api_key_duration` for `base.group_user` is 90 days.
The bridge addon's install data raises this to 1825 days (5 years) via
`data/api_key_policy.xml` — but that's the *cap*; the key itself still
has the expiration the operator set when minting it. Re-mint via the
MCP-bot user's My Profile → Account Security, then update the
`PRODUCTGRAPH_API_KEY` env var on the sidecar container.

**"I see `product_graph_relationship` in the Southbrook addons but
nowhere in `~/product_graph_v19/`. Which one is real?"**

Both. `product_graph_relationship` (Phase 2) lives in BOTH repos —
the generic one defines the closure model, the Southbrook copy is
running on the deployed stack. The closure is materialised per
relationship kind (`substitutes`, `alternates`, `supersedes`,
`references`, `related`) — see lesson 4.x and the
`pg.relationship.closure` model. The Southbrook codebase needs only the
closure model because that's what the deployed instance queries.

## What the system is doing behind the scenes

ProductGraph is the **OpenBOM mirror** — same data model, same
governance discipline, but living inside Odoo rather than as a separate
SaaS. Three things make it different from Odoo's native PLM:

**1. Property templates (`pg.property.template` →
`pg.property.field` → `pg.property.value`).** Native Odoo product
attributes are flat selections. Property templates are
schema-defined typed fields (char/integer/float/boolean/date/selection)
grouped by item type. A template for "Cabinet Mechanical" defines
`width_mm`, `height_mm`, `depth_mm`, `material`. Every cabinet
revision binds to that template and records its specific values.
Lesson 9.2 is the full tour.

**2. Vendor stubs (`pg.vendor`, `pg.vendor.part`).** In
`product_graph_base` these are model-only stubs (Decision D3) —
reserves the schema path without UI. The Phase 2 `product_graph_vendor`
addon turns them into a full Approved Vendor List with a 5-state
qualification lifecycle (`unqualified → probationary → qualified →
suspended → disqualified`). Lesson 9.3.

**3. Deep graph relationships (`pg.relationship`,
`pg.relationship.closure`).** Substitute, alternate, supersession,
references, and related — five kinds of edges across the catalog.
The closure is materialised so multi-hop queries are O(rows-returned)
instead of O(graph-walk). This is what powers "find all the parts
that could replace this if the vendor goes EOL."

**Five addons, plus the sidecar and the bridge:**

| Addon | What it owns |
|---|---|
| `product_graph_base` | `pg.item`, `pg.category`, `pg.property.*`, `pg.audit.log`, vendor stubs, 6 security groups, per-type sequences |
| `product_graph_revision` | `pg.revision`, `pg.document` (versioned attachments), `pg.property.value` |
| `product_graph_ebom` | `pg.ebom`, `pg.ebom.line`, `pg.ebom.closure` (materialised where-used) |
| `product_graph_release` | `pg.release`, the only writer of `mrp.bom`; MO-freeze logic; QWeb release reports |
| `product_graph_api` | REST `/api/v1/productgraph/*` for headless integration |
| `mcp/` sidecar | Python container, MCP protocol over stdio or SSE, ~30 tools |
| `southbrook_plm_productgraph` | Bridge — wraps `southbrook.eco.action_apply` to fire `pg.release` |

The 6 security groups (Bible R7) are layered:
`group_pg_viewer < group_pg_user < group_pg_engineer < group_pg_approver
< group_pg_mfg < group_pg_admin`. Approver is required to release an
EBOM; Engineer is required to call mutating MCP tools (re-checked at
the tool boundary per Decision D6).

## Quiz (5 questions, applied)

**1.** A designer wants to know "what's the canonical width of the
36-inch base cabinet, and where does that get changed?" Where do you
look?

> ProductGraph side. Open the `pg.item` for the 36-inch base cabinet,
> click its released `pg.revision`, look at the `pg.property.value`
> rows for the "Cabinet Mechanical" template. The width is stored as
> `value_integer` on the row where `field_id.key = 'width_mm'`. To
> change it, you'd create a new revision (not edit the released one —
> it's immutable) and release that through the EBOM flow.

**2.** You write an Odoo migration script that does
`self.env['mrp.bom'].create({...})` to add a BoM line for a new
cabinet. It works. Should it?

> No. Bible Rule R1: `mrp.bom` and `mrp.bom.line` are written **only**
> inside `pg.release.action_execute_release`. Every other path is
> forbidden. The fact that the ORM doesn't physically stop you doesn't
> make it allowed — your script is a Bible violation that will break
> reconciliation with the ProductGraph audit trail. Refactor to create
> a `pg.release` against a released `pg.ebom` and let the release flow
> mint the BOM.

**3.** A PLM engineer asks "can I install ProductGraph without
installing the Southbrook bridge?" What's the answer and why?

> Yes — the 5 generic addons (`product_graph_base/revision/ebom/
> release/api`) plus the MCP sidecar are deliberately publishable
> LGPL-3 with **no** reference to `southbrook_plm`. The bridge
> (`southbrook_plm_productgraph`) is a one-way glue that imports
> `pg.release` but `pg.release` does not know it exists. If you
> install ProductGraph on a non-Southbrook Odoo instance, you skip the
> bridge entirely.

**4.** The MCP sidecar's container has been failing to start for two
days. The Slack alert says "authentication failed". You re-mint a
fresh API key for `mcp-bot@...` and update the env var, but it still
fails. What else do you check?

> Two things. (a) Is `mcp-bot`'s `api_key_duration` cap actually 1825
> days? If `data/api_key_policy.xml` from the bridge install didn't
> run (or someone reverted it), the cap might be back to 90 days and
> your fresh key may have a shorter-than-intended expiration. Settings
> → General → API Keys shows the cap. (b) Does `mcp-bot` actually have
> `group_pg_engineer`? Without it, list-tools works but every mutating
> tool errors `permission_denied`. Check the user's groups via Settings
> → Users.

**5.** The Production Manager says "I want to delete this obsolete
prototype item — it's cluttering the search." Can you?

> Probably not without losing history. `pg.item.unlink()` rejects
> deletion outside `state in ('concept',)` (Bible R3 — no hard deletes
> on historically significant records). If the item is `prototype`,
> `engineering`, `released`, `service` or `obsolete`, it stays. The
> right move is to *obsolete it* (`state='obsolete'`), then set
> `active=False` so it falls out of default search views. The audit
> trail is preserved.

---

## What this lesson does NOT cover

- The detail of property templates / fields / values — lesson 9.2.
- Vendor stubs and the AVL workflow — lesson 9.3.
- Authoring an EBOM in the native editor — lesson 9.4.
- The MCP sidecar tooling and auth model — lesson 9.5.
- How the Southbrook bridge wires ECOs to releases — lesson 9.6.
- ECO lifecycle inside `southbrook_plm` — lesson 4.1.
- Cut spec authoring against released items — lesson 4.2.
