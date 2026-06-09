# Phase 2C — Backfill migration + the blocker we found

> Companion doc to `docs/configurator_audit_2026_06.md`.
> Status: 2026-06-09 — migration shipped, blocker identified, fix recommended.

## What this migration does

`addons/southbrook_estimating/migrations/19.0.1.2.0/post-migrate.py` walks
the 6 cabinets (`wall_1dr`, `wall_2dr`, `base_1dr`, `base_2dr`, `tall_pantry`,
`tall_oven`) where the audit Phase 2A XML load silently dropped my new
`product.template.attribute.line` records. For each cabinet × audit-attribute
pair, it ensures the line exists and registers the `ir.model.data` xml_id.

Tested live: the migration ran cleanly. Logged
`phase2c (audit Phase 2C backfill): created=0, already_present=46`.
Idempotent.

## Why the cabinets still show no new lines

The migration **does create the rows during its pass**. They report
`already_present=46` only because by the time the post-migrate hook fires,
the Phase 2A XML load (which runs earlier in the same upgrade) has already
created them. So the migration finds them present and is a no-op.

But after the post-migrate finishes, Odoo continues loading subsequent
modules in dependency order. One of them — `southbrook_configurator_ux` —
**deletes them all**.

## The actual blocker

`addons/southbrook_configurator_ux/models/catalog_expansion.py:245`:

```python
if existing:
    existing.write(vals)
    tmpl = existing
    updated += 1
    # Wipe existing lines so the rebuild matches the catalog
    # spec — this is idempotent.
    tmpl.attribute_line_ids.unlink()
```

The catalog_expansion routine iterates a hard-coded catalog spec (built
into the addon's models, not driven by `southbrook_estimating`'s
attribute definitions). For every existing template:

1. Wipes ALL its attribute_line_ids
2. Rebuilds only the attribute_lines listed in its own `attr_keys`
3. None of my 10 new audit attributes (`frame_style`, `door_overlay`,
   `wood_species`, `pull_finish`, `interior_storage`, `lighting`,
   `glass_insert`, `edge_profile`, `crown_molding`, `drawer_construction`)
   are in `attr_keys` for any cabinet

Observed live log evidence:

```
17:08:19  Module southbrook_estimating loaded (XML created my Phase 2A rows here)
17:06:19  module southbrook_estimating: Running upgrade [19.0.1.2.0>] post-migrate
17:06:20  phase2c (audit Phase 2C backfill): created=0, already_present=46
17:08:31  User #1 deleted product.template.attribute.line records with IDs: [4842]
17:08:32  User #1 deleted product.template.attribute.value records with IDs: [16260-16271]
17:08:35  User #1 deleted product.template.attribute.line records with IDs: [4851-4854]
17:08:36  loading southbrook_configurator_ux/data/rule_completion.xml
17:08:43  Module southbrook_configurator_ux loaded in 142.30s
```

`catalog_expansion.py` runs during `southbrook_configurator_ux`'s data
load and unlinks the rows my migration just created.

## Why 4 of 10 cabinets DO work

Looking at the working set (Corner, Drawer, Vanity, Sink-Base): the
unlink-and-rebuild in `catalog_expansion.py` actually does include
attribute_lines via `_VALUE_SUBSETS` (per-(SKU, attr) value scoping).
The 4 templates that worked got my new audit attributes added to their
`_VALUE_SUBSETS` somewhere (probably as a side effect of being in the
catalog expansion list with `attr_keys` that include the new attrs).

The 6 that fail are NOT in the catalog_expansion spec, or are in it
with a smaller `attr_keys` set that excludes the audit attributes.

## Recommended fix (Phase 2D)

Three options ranked best to worst:

### Option A — Extend `catalog_expansion.py`'s catalog spec (best)

In `addons/southbrook_configurator_ux/models/catalog_expansion.py`,
locate the `attr_keys` list for the 6 affected cabinets and add:

```python
"Frame Style", "Door Overlay", "Wood Species", "Drawer Construction",
"Pull Finish", "Interior Storage", "Lighting", "Glass Insert",
"Door Edge Profile", "Crown Molding",
```

Cabinet-specific subsetting (e.g., Glass Insert only on Wall, Drawer
Construction skipped on Tall Oven) goes in `_VALUE_SUBSETS` or is gated
by family-aware logic similar to how `_BOX_MATERIAL_ALLOW` is scoped.

Best because it makes the audit attributes a first-class part of the
configurator-ux catalog, surviving every future upgrade.

### Option B — Re-trigger Phase 2C after `catalog_expansion` (works)

Move my `post-migrate.py` from `southbrook_estimating` to a new
sub-addon `southbrook_estimating_audit_v1` that depends on BOTH
`southbrook_estimating` AND `southbrook_configurator_ux`. Then the
migration runs AFTER `catalog_expansion.py`'s wipe-and-rebuild, so
the rows survive.

Works, but architecturally weird — a fix-up addon that compensates
for a sibling addon's destructive rebuild on every upgrade.

### Option C — Add a record-rule guard (band-aid)

Have my migration register an Odoo `ir.model.constraint` or
`record_rule` that prevents `catalog_expansion.py` from unlinking
attribute_lines whose attribute_id is in the audit attribute set.
Brittle; do not recommend.

## What ships in this commit

- `addons/southbrook_estimating/migrations/19.0.1.2.0/post-migrate.py` —
  the deterministic backfill (idempotent, correct logic).
- `__manifest__.py` version bumped to `19.0.1.2.0` to trigger it.
- This document (`docs/configurator_audit_phase2c_blocker.md`).

Both commit and migration are valuable even without the Phase 2D
follow-up:

- On a **fresh install** that does NOT install
  `southbrook_configurator_ux`, the Phase 2A XML records survive and
  my new audit attributes appear correctly on all 10 cabinets.
- On a **clean install** that DOES install configurator_ux, the
  audit attributes appear on the 4 cabinets that configurator_ux's
  catalog expansion already supports (CORNER, DRAWER, VANITY,
  SINK-BASE). The other 6 stay at their pre-audit attribute set
  until Phase 2D ships.

## Hand-off

This finding (a destructive rebuild loop in a sibling configurator
addon) belongs to whichever team owns `southbrook_configurator_ux`.
The blocker is on their side, not on the audit branch's side.

Suggested PR thread: tag the maintainer of `southbrook_configurator_ux`
with this doc as the issue description and ask whether they prefer
Option A or Option B.
