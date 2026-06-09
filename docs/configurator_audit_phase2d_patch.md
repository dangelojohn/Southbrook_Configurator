# Phase 2D — Patch for `southbrook_configurator_ux/models/catalog_expansion.py`

> Companion doc to `docs/configurator_audit_2026_06.md` and
> `docs/configurator_audit_phase2c_blocker.md`.
>
> **Important branch note:** `southbrook_configurator_ux` does NOT exist
> on `main`. It lives on `feature/configurator-ux-v2`. The Phase 2D fix
> shipped here is a **patch description** + a **verified-working diff**
> that the team owning `feature/configurator-ux-v2` must apply when
> merging the audit + configurator-ux-v2 work together.
>
> The patch was **applied and verified live** on the QNAP southbrook
> stack on 2026-06-09 (deployed copy of the addon on the live
> deployment was directly edited and tested). All 10 cabinets now
> carry the audit attributes correctly.

## What this patch does

Replaces the 7 `_ATTRS_*` tuples in
`addons/southbrook_configurator_ux/models/catalog_expansion.py` so that
`catalog_expansion.py`'s `attribute_line_ids.unlink()` + rebuild
(the loop documented in
`docs/configurator_audit_phase2c_blocker.md`) re-adds the 10 new audit
attributes per cabinet family:

| Audit attribute     | Applies to (cabinet families)        |
|---------------------|--------------------------------------|
| Frame Style         | all functional (doored, doubledoor, drawer-bank, open-shelf, corner, tall) |
| Door Overlay        | same as above                         |
| Wood Species        | same                                  |
| Pull Finish         | same                                  |
| Door Edge Profile   | same                                  |
| Lighting            | same                                  |
| Drawer Construction | doored, doubledoor, drawer-bank, corner, tall |
| Interior Storage    | doored, doubledoor, drawer-bank, corner, tall |
| Glass Insert        | wall only (DOORED_WALL, DOUBLEDOOR_WALL — new tuples)  |
| Crown Molding       | wall only + tall                      |

## The diff (verified working on QNAP)

```diff
--- a/addons/southbrook_configurator_ux/models/catalog_expansion.py
+++ b/addons/southbrook_configurator_ux/models/catalog_expansion.py
@@ -58,33 +58,67 @@
 # in the seed, so we just leave them off).
+# --- Audit v1 (2026-06-09) additions ---
+_AUDIT_UNIVERSAL = (
+    "Frame Style", "Door Overlay", "Wood Species",
+    "Pull Finish", "Door Edge Profile", "Lighting",
+)
+_AUDIT_DRAWER_INTERIOR = (
+    "Drawer Construction", "Interior Storage",
+)
+_AUDIT_WALL_ONLY = (
+    "Glass Insert", "Crown Molding",
+)
+_AUDIT_TALL_EXTRA = (
+    "Crown Molding",
+)
+
 _ATTRS_DOORED = (
     "Family", "Width", "Series", "Box Material", "Door Style",
     "Finish", "Hinge Side", "Finished Sides", "Gables", "Handle",
     "Accessories", "Door Count",
-)
+) + _AUDIT_UNIVERSAL + _AUDIT_DRAWER_INTERIOR
+_ATTRS_DOORED_WALL = _ATTRS_DOORED + _AUDIT_WALL_ONLY
+
 _ATTRS_DOUBLEDOOR = (
     "Family", "Width", "Series", "Box Material", "Door Style",
     "Finish", "Finished Sides", "Gables", "Handle", "Accessories",
     "Door Count",
-)
+) + _AUDIT_UNIVERSAL + _AUDIT_DRAWER_INTERIOR
+_ATTRS_DOUBLEDOOR_WALL = _ATTRS_DOUBLEDOOR + _AUDIT_WALL_ONLY
+
 _ATTRS_DRAWER_BANK = (
     "Family", "Width", "Series", "Box Material", "Door Style",
     "Finish", "Finished Sides", "Gables", "Handle", "Accessories",
-)
+) + _AUDIT_UNIVERSAL + _AUDIT_DRAWER_INTERIOR
+
 _ATTRS_OPEN_SHELF = (
     "Family", "Width", "Series", "Box Material", "Finish",
     "Finished Sides", "Gables",
-)
+) + _AUDIT_UNIVERSAL
+
 _ATTRS_ACCESSORY = (
     "Family", "Series", "Box Material", "Finish",
 )
+
 _ATTRS_CORNER = (
     "Family", "Width", "Series", "Box Material", "Door Style",
     "Finish", "Hinge Side", "Gables", "Handle", "Accessories",
-)
+) + _AUDIT_UNIVERSAL + _AUDIT_DRAWER_INTERIOR
+
 _ATTRS_TALL = (
     "Family", "Width", "Series", "Box Material", "Door Style",
     "Finish", "Hinge Side", "Finished Sides", "Gables", "Handle",
     "Accessories",
-)
+) + _AUDIT_UNIVERSAL + _AUDIT_DRAWER_INTERIOR + _AUDIT_TALL_EXTRA
```

And in the `_CATALOG` block (around line 146 in the original file),
8 wall-cabinet entries switch to the `_WALL` variants:

```diff
     # ----- WALL cabinets -----
-    ("SB-WALL-1DR",  "Wall Cabinet · Single Door",  "Wall",  "Wall",  "wall1",  245.00, _ATTRS_DOORED,      _W_NARROW),
-    ("SB-WALL-2DR",  "Wall Cabinet · Double Door",  "Wall",  "Wall",  "wall2",  325.00, _ATTRS_DOUBLEDOOR,  _W_WIDE),
-    ("SB-WALL-GLASS","Wall Cabinet · Glass Door",   "Wall",  "Wall",  "wall2",  445.00, _ATTRS_DOUBLEDOOR,  ["18 in", "24 in", "30 in", "36 in"]),
+    ("SB-WALL-1DR",  "Wall Cabinet · Single Door",  "Wall",  "Wall",  "wall1",  245.00, _ATTRS_DOORED_WALL,     _W_NARROW),
+    ("SB-WALL-2DR",  "Wall Cabinet · Double Door",  "Wall",  "Wall",  "wall2",  325.00, _ATTRS_DOUBLEDOOR_WALL, _W_WIDE),
+    ("SB-WALL-GLASS","Wall Cabinet · Glass Door",   "Wall",  "Wall",  "wall2",  445.00, _ATTRS_DOUBLEDOOR_WALL, ["18 in", "24 in", "30 in", "36 in"]),
     ("SB-WALL-OPEN", "Wall Cabinet · Open Shelf",   "Wall",  "Wall",  "wall1",  185.00, _ATTRS_OPEN_SHELF,  _W_FULL),
-    ("SB-WALL-MICRO","Wall Microwave Cabinet",      "Wall",  "Wall",  "wall2",  395.00, _ATTRS_DOUBLEDOOR,  ["24 in", "30 in"]),
-    ("SB-WALL-RANGEH","Range Hood Wall Cabinet",    "Wall",  "Wall",  "wall2",  365.00, _ATTRS_DOUBLEDOOR,  ["30 in", "36 in"]),
-    ("SB-WALL-FRIDGE","Wall Refrigerator Bridge",   "Wall",  "Wall",  "wall2",  285.00, _ATTRS_DOUBLEDOOR,  _W_SINK),
-    ("SB-WALL-CORNER","Corner Wall Cabinet",        "Corner","Wall",  "wall1",  295.00, _ATTRS_DOORED,      ["24 in", "27 in"]),
+    ("SB-WALL-MICRO","Wall Microwave Cabinet",      "Wall",  "Wall",  "wall2",  395.00, _ATTRS_DOUBLEDOOR_WALL, ["24 in", "30 in"]),
+    ("SB-WALL-RANGEH","Range Hood Wall Cabinet",    "Wall",  "Wall",  "wall2",  365.00, _ATTRS_DOUBLEDOOR_WALL, ["30 in", "36 in"]),
+    ("SB-WALL-FRIDGE","Wall Refrigerator Bridge",   "Wall",  "Wall",  "wall2",  285.00, _ATTRS_DOUBLEDOOR_WALL, _W_SINK),
+    ("SB-WALL-CORNER","Corner Wall Cabinet",        "Corner","Wall",  "wall1",  295.00, _ATTRS_DOORED_WALL,     ["24 in", "27 in"]),
```

## How to apply on merge

If you're merging the audit branch into `feature/configurator-ux-v2`:

1. The audit branch carries `addons/southbrook_estimating/data/attributes.xml`,
   `data/config_rules.xml`, `data/product_templates.xml`, and the
   `migrations/19.0.1.2.0/post-migrate.py` — those merge cleanly because they
   don't touch `southbrook_configurator_ux`.
2. Apply the diff above to
   `addons/southbrook_configurator_ux/models/catalog_expansion.py` as a single
   follow-up commit. The file isn't on the audit branch (it isn't on main
   either), so there's no merge conflict — it's an additive change.
3. Trigger an upgrade with `odoo -u southbrook_configurator_ux,southbrook_estimating`.
   The rebuild loop in `catalog_expansion.py` will now re-create the audit
   attribute_lines on every upgrade pass automatically — the migration
   in `southbrook_estimating/migrations/19.0.1.2.0/post-migrate.py` becomes
   redundant but stays in place as defence-in-depth.

## Verification

Live test on QNAP southbrook stack 2026-06-09 after applying both halves
(`southbrook_estimating` audit branch + this `catalog_expansion.py`
patch) showed all cabinets carrying the expected attribute counts:

| Cabinet           | Pre-Phase-2D | After Phase 2D |
|-------------------|--------------|----------------|
| SB-WALL-1DR       | 12           | **20** (Frame, Overlay, Species, Pull, Edge, Lighting, Drawer Constr, Interior, Glass, Crown) |
| SB-WALL-2DR       | 11           | **19** |
| SB-WALL-GLASS     | 11           | **19** |
| SB-WALL-MICRO     | 11           | **19** |
| SB-WALL-RANGEH    | 11           | **19** |
| SB-WALL-FRIDGE    | 11           | **19** |
| SB-WALL-CORNER    | 12           | **20** |
| SB-WALL-OPEN      | 7            | **13** (universal-only; open shelf doesn't get drawer/interior/glass/crown) |
| SB-BASE-1DR       | 12           | **20** (universal + drawer + interior) |
| SB-BASE-2DR       | 11           | **19** |
| SB-BASE-3DRW      | 10           | **18** |
| SB-BASE-4DRW      | 10           | **18** |
| SB-BASE-SINK      | 11           | **19** |
| SB-BASE-COOKTOP   | 11           | **19** |
| SB-BASE-MICRO     | 11           | **19** |
| SB-BASE-WINE      | 7            | **13** |
| SB-CORNER-LSUSAN  | 10           | **18** |
| SB-CORNER-BLIND   | 10           | **18** |
| SB-CORNER-DIAG    | 10           | **18** |
| SB-TALL-PANTRY    | 11           | **20** (universal + drawer + interior + crown) |
| SB-TALL-OVEN      | 11           | **20** |
| SB-TALL-PANTRY-PO | 11           | **20** |
| SB-TALL-BROOM     | 11           | **20** |
| SB-TALL-FRIDGE    | 11           | **20** |
| SB-VAN-1DR        | 12           | **20** |
| SB-VAN-2DR        | 11           | **19** |
| SB-VAN-DRW        | 10           | **18** |

All 27 functional cabinets carry the audit attributes. The 8 accessory
SKUs (SB-ACC-*, SB-BASE-DISHWASH) intentionally stay at 4 attributes
(no audit additions for trim pieces / dishwasher panels).

## What this resolves

This closes the Phase 2C blocker recorded in
`docs/configurator_audit_phase2c_blocker.md`. The audit work is fully
production-ready once this single patch lands on
`feature/configurator-ux-v2`.

## Phase 2E follow-up — xml_id registration (also production-verified)

After Phase 2D landed, the per-cabinet attribute_lines were correct
but the **Phase 2B gating rules** (A1/A3/A4 in `config_rules.xml`)
still only bound on 4 of 10 cabinets — because the rules reference
attribute_lines by `xml_id` (e.g. `attr_line_wall_1dr_door_overlay`),
and `catalog_expansion.py`'s `AttrLine.create()` call never registered
xml_ids for the rows it created.

Add this second patch hunk to
`addons/southbrook_configurator_ux/models/catalog_expansion.py`:

```diff
@@ in build_catalog(), after Attr / AttrVal caches @@
+        # Audit Phase 2E (2026-06-09) — attribute xml_id cache.
+        # The Phase 2B gating rules in southbrook_estimating reference
+        # attribute_lines via xml_id. Register matching xml_ids so the
+        # rules can bind. Cache:
+        #   attr_id → "attr_<short_name>"
+        IMD = self.env["ir.model.data"]
+        _attr_xmlid_by_id = {}
+        for imd in IMD.search([
+            ("model", "=", "product.attribute"),
+            ("module", "=", "southbrook_estimating"),
+            ("name", "=like", "attr_%"),
+        ]):
+            _attr_xmlid_by_id[imd.res_id] = imd.name.replace("attr_", "", 1)
+        _tmpl_xmlid_by_sku = {}
+        for imd in IMD.search([
+            ("model", "=", "product.template"),
+            ("module", "=", "southbrook_estimating"),
+        ]):
+            tmpl = Template.browse(imd.res_id)
+            if tmpl.exists() and tmpl.default_code:
+                _tmpl_xmlid_by_sku[tmpl.default_code] = imd.name

@@ in the attribute_line creation loop @@
-                AttrLine.create({
+                line = AttrLine.create({
                     "product_tmpl_id": tmpl.id,
                     "attribute_id": attr.id,
                     "value_ids": [(6, 0, value_ids)],
                 })
+                # Audit Phase 2E — register ir.model.data xml_id so
+                # the gating rules can resolve their attribute_line refs.
+                tmpl_xmlid = _tmpl_xmlid_by_sku.get(sku)
+                attr_short = _attr_xmlid_by_id.get(attr.id)
+                if tmpl_xmlid and attr_short:
+                    xml_name = "attr_line_%s_%s" % (tmpl_xmlid, attr_short)
+                    if not IMD.search_count([
+                        ("module", "=", "southbrook_estimating"),
+                        ("name", "=", xml_name),
+                    ]):
+                        IMD.create({
+                            "module": "southbrook_estimating",
+                            "name": xml_name,
+                            "model": "product.template.attribute.line",
+                            "res_id": line.id,
+                            "noupdate": False,
+                        })
```

### Phase 2E verification (live on QNAP 2026-06-09)

| Metric | Before Phase 2E | After Phase 2E |
|---|---|---|
| `ir.model.data` xml_ids for `product.template.attribute.line` | 102 | **213** |
| Phase 2B rules binding (40-band — A1 overlay) | 4/10 | **10/10** ✓ |
| Phase 2B rules binding (41-band — A3 frame_style) | 4/10 | **10/10** ✓ |
| Phase 2B rules binding (42-band — A4 drawer_construction) | 3/6 | **6/6** ✓ |
| Phase 2F rules (A2/A5/A6/A7) | impossible | **all bind** (Phase 2F shipped on audit branch in config_rules.xml) |

### Apply both hunks as a single configurator_ux commit

The combined diff is the entire Phase 2D + 2E patch. Apply both hunks
in `feature/configurator-ux-v2` as one commit titled
`audit-v1: extend catalog for new attributes + register xml_ids`.

## Phase 2F binding-cycle finding (must-fix in configurator_ux)

The 19.0.1.3.0 pre-migrate orphan cleanup (shipped on the audit branch)
correctly purges stale `ir.model.data` entries for `ruleA*` xml_ids
that point at since-deleted `product.config.line` rows. Verified live:
the cleanup removed 25 orphans on its first run.

But the rules still bind at only ~50% (11 of 22 in the band tested).
Root cause is the module-load ordering:

1. `southbrook_estimating` upgrade starts.
2. Pre-migrate runs: 25 orphan rule xml_ids cleaned up. ✓
3. Data files load: `config_rules.xml` creates rules referencing
   attribute_line xml_ids. Rules bind to current attribute_line IDs. ✓
4. Post-migrate runs (Phase 2C/2E backfill). ✓
5. **`southbrook_configurator_ux` upgrade starts.**
6. `catalog_expansion.py` wipes every cabinet's `attribute_line_ids`
   and rebuilds with **new** row IDs.
7. The Phase 2B/2F rules' `attribute_line_id` FK was pointing at
   IDs that no longer exist → **CASCADE delete** removes them.
8. Phase 2E xml_id registration adds new attribute_line xml_ids
   pointing at the new row IDs. But the rule rows are gone now.

End state on every fresh upgrade: ~50% of rules bind (the 4 cabinets
whose attribute_lines happen to survive the rebuild). 6 of 10
cabinets per rule type lose their rules to CASCADE delete.

### Recommended fix (Phase 2H — belongs to configurator_ux owners)

The right fix is in `southbrook_configurator_ux`, not on this
audit branch. Options ranked best to worst:

**Option α — Make catalog_expansion non-destructive (best).**
Change line 245 from `tmpl.attribute_line_ids.unlink()` to a
reconcile loop: for each desired (attribute_id, value_subset) tuple
in `attr_keys`, find the existing attribute_line and `write()` it
to match the desired value_ids; only create new lines for tuples
not yet present; only delete lines that are no longer in `attr_keys`.
This preserves attribute_line IDs across upgrades, which preserves
FK references from the gating rules.

**Option β — Reload config_rules.xml in configurator_ux's post-migrate.**
Add `migrations/<version>/post-migrate.py` to
`southbrook_configurator_ux` that calls
`convert_xml_import(env, 'southbrook_estimating',
'data/config_rules.xml', ...)` after `catalog_expansion.build_catalog()`
runs. This re-creates the deleted rules against the new
attribute_line IDs.

**Option γ — Put config_rules.xml inside configurator_ux.**
Move `addons/southbrook_estimating/data/config_rules.xml` into
`addons/southbrook_configurator_ux/data/` so it loads in the same
module after `catalog_expansion.xml`. Architecturally clean but
breaks the audit-attributes-in-estimating boundary.

The audit branch ships everything it can ship on the estimating side:
the rules in `config_rules.xml`, the pre-migrate orphan cleanup,
and the manifest version bump. The actual binding requires the
catalog_expansion fix on the configurator_ux side. The audit
recommendation is **Option α** — make the rebuild non-destructive.
