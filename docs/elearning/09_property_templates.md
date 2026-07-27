---
course: 9 — ProductGraph
chapter: 9.2
title: Property Templates — Authoring Engineering Specs
duration: 35 minutes
audience: PLM engineer authoring product specs (cabinet mechanical, vendor components, drawings)
prereqs: Lesson 9.1 (ProductGraph overview)
custom_modules: product_graph_base (templates + fields), product_graph_revision (values)
---

# Property Templates — Authoring Engineering Specs

## Who this lesson is for

You are the PLM engineer who defines *what gets measured* on every item
in the catalog. The 36" base cabinet has a width, height, depth, box
material — but those aren't free-form text on the cabinet record. They're
typed fields on a **property template** that lots of cabinets share.
When the sourcing team adds a new vendor component, it goes on a
different template — one for `mpn`, `datasheet_url`, `lead_time_days`.
This lesson is the practical reality of authoring templates, attaching
them to items, and entering the values that downstream tools (BoM
generator, MCP sidecar, REST API) consume.

This lesson is entirely on the **standalone ProductGraph platform**
side. Templates live in `product_graph_base`; values live in
`product_graph_revision`. The Southbrook bridge addon does not touch
templates at all — it just reads finished items.

## Where this lives on the site

Sign in at **southbrookcabinetry.space/odoo** as an Engineer or
Approver, then:

> **Manufacturing → ProductGraph → Property Templates**

You'll see a list of every `pg.property.template` in the system, grouped
by `item_type`. To enter a value for an item:

> **Manufacturing → ProductGraph → Items → [pick item] → Revisions →
> [pick draft revision] → Properties tab**

The split is deliberate: **templates** are catalog-level definitions
(rarely changed, often shared); **values** are revision-scoped (often
changed, immutable once the revision releases).

## What your screen shows

Open a property template (e.g. "Cabinet Mechanical"). The form shows:

- **Template Name** (`name` on `pg.property.template`) — human label.
- **Code** (`code`) — short stable identifier; `_code_unique` constraint.
- **Sequence** (`sequence`, default 10) — list ordering.
- **Applies To Item Type** (`item_type`) — one of the 6 item types:
  `assembly / part / purchased / document / software / service`. Mirrors
  the `item_type` selection on `pg.item`. A template can only be
  attached to items whose `item_type` matches.
- **Description** (`description`) — free text. Show your work — future
  engineers will need to know why this template exists.
- **Fields** (`field_ids`, one2many to `pg.property.field`) — the typed
  fields. Each row shows:
  - **Key** (`key`) — machine-readable, snake_case. The API and the
    MCP sidecar use this. Examples: `width_mm`, `mpn`, `lead_time_days`.
    `(template_id, key)` is unique. Validation rejects digits-at-start
    and non-alphanumeric (excepting underscore).
  - **Label** (`label`) — human-readable, shown in forms and reports.
    Translatable.
  - **Type** (`field_type`) — one of `char / integer / float / boolean
    / date / selection`. To add a new type, you'd have to extend BOTH
    this selection AND `pg.property.value`'s typed columns — that's a
    Phase 2 expansion, locked in Phase 1.
  - **Required** (`is_required`) — whether the value must be set on a
    revision before the revision can move out of `draft`. Phase 1 does
    not enforce this at the ORM level; soft hint only.
  - **Help** (`help_text`) — tooltip, translatable.
  - **Default Value** (`default_value`) — pre-fills new
    `pg.property.value` rows.
  - **Selection Options** (`selection_options`) — comma-separated, only
    meaningful when `field_type='selection'`. A constraint enforces
    this is populated when the type is selection. Example: `"S,M,L,XL"`.
  - **Unit of Measure** (`uom_id`) — display-only in Phase 1. Useful
    hint for numeric fields.

Open a draft revision and switch to the **Properties tab**. Each row
is a `pg.property.value` and shows:

- **Field Label** (related to `field_id.label`)
- **Field Key** (related to `field_id.key`)
- **Field Type** (related; drives which input control appears)
- **Value** — actually stored in one of `value_char` / `value_integer`
  / `value_float` / `value_boolean` / `value_date` / `value_selection`
  depending on the field type. The `display_value` compute reads back
  from the right slot.

## Your daily flow

**1. Define the template (once).**

You're standing up a new cabinet line and need a "Cabinet Mechanical"
template that didn't exist before:

- **Manufacturing → ProductGraph → Property Templates → Create.**
- Set `name = "Cabinet Mechanical"`, `code = "CAB_MECH"`,
  `item_type = "Manufactured Part"`, sequence = 10.
- In **Fields**, add lines:
  - `width_mm` / Integer / required / uom = mm
  - `height_mm` / Integer / required / uom = mm
  - `depth_mm` / Integer / required / uom = mm
  - `material` / Selection / required / options = `"melamine,MDF,particleboard,plywood"`
  - `door_count` / Integer / not required / default = `"1"`
- Save. The template is now available to attach.

**2. Attach to an item (once per item).**

- Open the `pg.item` for the cabinet.
- **Property Templates** field is a many2many to `pg.property.template`
  with `domain="[('item_type','=',item_type),('active','=',True)]"` —
  only matching-type templates appear in the dropdown.
- Add "Cabinet Mechanical." Save.

**3. Enter values (once per revision).**

- Open the item's draft revision.
- Switch to the **Properties tab**.
- One row per `pg.property.field` of every attached template will be
  there (the defaults from `default_value` pre-fill).
- Fill in the values: width = 914, height = 762, depth = 610, material
  = melamine, door_count = 2.
- Save. The cross-model constraint
  (`_check_template_belongs_to_item`) verifies the field's template is
  actually attached to the parent item before accepting the value.

**4. Submit, review, release.**

- Submit the revision for review → release. Once released, the
  `pg.property.value` rows become immutable (write/unlink blocked by
  `_check_revision_writable` unless the `_pg_release_bypass` context
  flag is set, which only `pg.release.action_execute_release` uses).
- This is when downstream consumers — the REST API, the MCP sidecar,
  the bridge's release — start trusting the values.

**5. Override on the next revision.**

If a vendor change means the depth is now 600mm (not 610):

- Create a new draft revision against the item.
- The Properties tab pre-fills from the template defaults, NOT from the
  previous released revision's values. **In Phase 1 you re-enter what
  changed.**
- Fill `depth_mm = 600`, leave everything else as it was.
- Submit, release. The old revision is auto-superseded; both revisions
  retain their own `pg.property.value` rows for historical record.

## Common mistakes + how to recover

**"I tried to attach a `Document` template to an Assembly item and it
won't show in the dropdown."**

Working as designed. The `property_template_ids` field on `pg.item` is
domained:
`[('item_type','=',item_type),('active','=',True)]`. Templates whose
`item_type` doesn't match the item's `item_type` are filtered out. If
you really need this, you've found a modelling problem — file a ticket.

**"I added a field to a template after several items already had
values for the other fields. Nothing populated."**

Adding a field to a template does NOT retroactively create
`pg.property.value` rows on existing revisions. The new field will
appear empty on draft revisions; users have to enter the value. For
already-released revisions, the field will appear absent — released
revisions are immutable.

**"I tried to delete a field from a template and got a foreign key
error."**

`pg.property.field` has `ondelete='cascade'` from template, but
`pg.property.value` references the field with `ondelete='restrict'`.
The DB blocks deletion if any value row references it. Either obsolete
the field (set `active=False`) or delete the dependent values from
draft revisions first.

**"I changed the `key` of a field after some revisions had values for
it. Did anything break?"**

Quietly, yes. The MCP sidecar's `propose_revision` tool and the REST
API both reference fields by `key`, not by id. Any client code that
referenced the old key now silently misses the field. The system does
not warn about this — keys are stable identifiers by convention, not by
constraint. Don't rename keys after release.

**"My values aren't saving. I get `Property template X is not attached
to item Y`."**

Constraint `_check_template_belongs_to_item` fires when the revision's
parent item doesn't have the field's template in its
`property_template_ids`. Two fixes: either attach the template to the
item, or move the value to a revision of a different item that does
have the template. Likely you set the wrong `revision_id`.

**"The release ran but the resulting `mrp.bom` doesn't have the
property values."**

Property values live on `pg.property.value` (on the revision), not on
`mrp.bom`. The release stamps the `pg.release.line` rows with the
revision they came from; if you need a property at the BoM level (e.g.
to drive a cut spec) you read it through
`release.line_ids.revision_id.property_value_ids` or through the
`pg.item.product_id` link. There is **no** direct field-to-field push
into `mrp.bom`.

## What the system is doing behind the scenes

Three models, three jobs:

| Model | Module | Job |
|---|---|---|
| `pg.property.template` | `product_graph_base` | Defines a named, item-type-scoped collection of fields. Catalog-level. |
| `pg.property.field` | `product_graph_base` | One typed field within a template. `(template_id, key)` unique. |
| `pg.property.value` | `product_graph_revision` | One typed value bound to one revision + one field. `(revision_id, field_id)` unique. |

The typed-slot pattern on `pg.property.value` keeps storage normalised.
Instead of one polymorphic `value` column that's always a string and
gets cast at read time, each row has six columns — `value_char`,
`value_integer`, `value_float`, `value_boolean`, `value_date`,
`value_selection` — and the `_compute_display_value` method reads from
the slot that matches the field's `field_type`. Queries like "all
items with `width_mm > 800`" are real integer comparisons against
`value_integer`, not string-coerced.

The selection constraint
(`_check_selection_in_options`) re-parses
`field_id.selection_options` at write time to ensure the value is in
the allowed set. The class method `get_selection_choices` on
`pg.property.field` returns `[(value, label), ...]` for that parse so
both the constraint and the form view stay in sync.

The immutability is enforced in `pg.property.value`'s `write` and
`unlink` overrides:

```python
def _check_revision_writable(self):
    for rec in self:
        if rec.revision_id.state in ('released', 'superseded', 'obsolete') \
                and not self.env.context.get('_pg_release_bypass'):
            raise UserError(_("Cannot edit property values on revision …"))
```

The `_pg_release_bypass` context flag is the same one used across all
of `pg.*` — it's set only inside `pg.release.action_execute_release`.
This is the rule called "context-flag bypass instead of raw SQL"
(Decision D7, ProductGraph CLAUDE.md): no `env.cr.execute("UPDATE
pg_property_value SET ...")` is ever required to release. The Bible
treats raw SQL on `pg.*` tables as a violation.

Phase 1 deliberately stops here. The OpenBOM-mirror spec calls for
formula evaluation, cross-item rollup ("if any child width > 800, mark
parent as oversize"), and conditional visibility — these are Phase 2.
Decision D2 locks "schema + UI for definition and value entry only" as
the Phase 1 cap.

## Quiz (5 questions, applied)

**1.** You're authoring a property template for purchased components.
You add a `selection` field called `package_type` and save. The save
errors with `Selection field 'Package Type' requires
selection_options`. What did you miss?

> The `_check_selection_has_options` constraint fires when
> `field_type='selection'` and `selection_options` is blank. Add the
> comma-separated allowed values (e.g. `"SOIC,TSSOP,QFN,BGA"`) before
> saving. Selection fields without options would be unusable
> downstream anyway — the MCP sidecar's `propose_revision` and the
> form view both call `get_selection_choices()` which returns empty
> for an unconfigured field.

**2.** A designer asks "I changed the depth on the 36" base cabinet
revision from 610 to 600 last week but the manufacturing BOM still
shows 610. Why?"

> Two likely causes. (a) The revision is still in `draft` — the
> release flow hasn't run yet, so no `mrp.bom` exists tied to the new
> values. Check `pg.revision.state`. (b) The revision released but
> downstream code is reading the value off the *previous* released
> revision (the now-superseded one). Property values are
> revision-scoped, so a stale revision reference returns stale
> values. Find the consumer and have it read off the item's current
> released revision.

**3.** Your template has 12 fields. An engineer attaches it to an item
and creates a draft revision. On the Properties tab they see 0 rows,
not 12. What happened?

> Phase 1 does NOT auto-create `pg.property.value` rows when a
> template is attached. The tab shows whatever values exist; if none
> have been entered, it's empty. The engineer needs to add the rows
> manually (one per field they want to set a value for). Defaults
> from `default_value` only apply when a row is being created. If you
> want auto-population, that's a Phase 2 ergonomics improvement; file
> a ticket.

**4.** The MCP sidecar's `propose_revision` tool is being asked to
set `lead_time_days = "fourteen"` on a purchased item. What happens?

> The Odoo write hits `pg.property.value.write` with
> `value_integer = "fourteen"`. ORM type coercion will fail with a
> `ValueError` (cannot cast "fourteen" to integer). The MCP server's
> top-level handler catches `Exception` and returns a JSON error
> blob with `error: "tool_error"` and the exception message. The
> revision is not modified; no audit log row written. The agent
> should re-call with `lead_time_days = 14` (numeric).

**5.** A regulatory audit asks "what was the width of the 36" base
cabinet on 2026-03-15?" You're standing in front of the item. Where do
you look?

> Find the `pg.revision` that was the released revision for that
> item on that date — check `release_timestamp` and `effective_date`
> on each revision; the one that bracketed 2026-03-15 is the answer.
> Open its `pg.property.value` rows, find the row where
> `field_id.key='width_mm'`, read `value_integer`. The audit trail
> (`pg.audit.log`) confirms when that revision was released and by
> whom — that's the regulatory artifact.

---

## What this lesson does NOT cover

- The 5 item-state machine (`concept → … → obsolete`) — lesson 9.1.
- Authoring an EBOM that consumes these property values — lesson 9.4.
- How the MCP sidecar's `get_item` returns the values to an LLM agent
  — lesson 9.5.
- ECO workflow that approves a value change — lesson 4.1.
- Cut spec authoring that reads `width_mm` etc — lesson 4.2 / 1.7.
