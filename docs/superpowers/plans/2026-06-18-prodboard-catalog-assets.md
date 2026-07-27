# Prodboard Catalog Assets Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Clone the Prodboard BetterKitchens catalogue structure into Southbrook-owned taxonomy/metadata, internally cache licensed image assets, and map the 12 locked Southbrook templates to catalogue archetypes without replacing the price-bearing templates.

**Architecture:** Keep the 223-row `southbrook.cabinet.archetype` taxonomy as the canonical cloned catalogue layer. Store Prodboard UUIDs/filenames/URLs as internal references only, cache downloaded binaries as private `ir.attachment` records linked to archetypes, and keep public product imagery served from Southbrook-owned `product.template.image_1920`. Link the 12 locked Q8 templates to archetypes by an idempotent seed helper keyed by template XML slug and archetype code.

**Tech Stack:** Odoo 19 CE, Python ORM models, XML data function seeds, `ir.attachment`, existing `southbrook_estimating` tests using `TransactionCase` and `HttpCase`.

## Global Constraints

- Preserve the 12 locked Q8 product templates in `addons/southbrook_estimating/data/product_templates.xml`.
- Do not create 223 price-bearing `product.template` records.
- Do not embed or render Prodboard asset URLs in customer-facing UI.
- Store Prodboard image UUIDs/filenames/URLs as non-rendered internal references only.
- Public UI continues serving Southbrook-owned `product.template.image_1920` images through the existing catalog-icon controller.
- Keep OCA modules untouched.

---

## File Structure

- Modify `addons/southbrook_estimating/models/cabinet_archetype.py`
  - Add richer source metadata fields.
  - Add asset import tracking fields.
  - Add deterministic asset helper methods.
  - Add an abstract importer model that can download or offline-import licensed images into `ir.attachment`.
- Modify `addons/southbrook_estimating/models/product_template.py`
  - Add `x_prodboard_archetype_id` and related read-only metadata fields for the 12 locked templates.
- Create `addons/southbrook_estimating/models/template_archetype.py`
  - Add an idempotent mapping helper from the 12 locked template XML IDs to Prodboard archetype codes.
- Create `addons/southbrook_estimating/data/template_archetype_assign.xml`
  - Call the mapping and placeholder-image helpers after taxonomy seed and after product templates load.
- Modify `addons/southbrook_estimating/__manifest__.py`
  - Load the new mapping function after `data/prodboard_taxonomy_seed.xml` and `data/template_code_assign.xml`.
- Modify `addons/southbrook_estimating/models/__init__.py`
  - Import the new mapping helper.
- Create `addons/southbrook_estimating/tests/test_prodboard_asset_importer.py`
  - Test mock asset import, idempotency, source URL privacy expectations, and offline import.
- Create `addons/southbrook_estimating/tests/test_template_archetype_mapping.py`
  - Test field existence, mapped templates, unmapped Southbrook-only placeholders, generated PNG placeholders, and preservation of all 12 locked templates.
- Modify `addons/southbrook_estimating/README.md`
  - Document the cloned catalogue layer, internal asset cache, and public image serving rule.

### Task 1: Asset Metadata and Importer

**Files:**
- Modify: `addons/southbrook_estimating/models/cabinet_archetype.py`
- Test: `addons/southbrook_estimating/tests/test_prodboard_asset_importer.py`

**Interfaces:**
- Produces: `southbrook.cabinet.archetype.prodboard_asset_attachment_id`
- Produces: `southbrook.cabinet.archetype.prodboard_asset_status`
- Produces: `southbrook.estimating.prodboard_asset_importer.import_assets(limit=None, offline_dir=None, allow_network=False)`

- [ ] **Step 1: Write failing tests**
  - Assert an archetype with `image_url` can import bytes from an injected fetcher into a private `ir.attachment`.
  - Assert a second import updates the same attachment instead of duplicating it.
  - Assert the importer can read from an offline directory using `image_uuid`.
  - Assert `image_url` remains metadata while the public product image route does not use archetype attachments.

- [ ] **Step 2: Verify tests fail**
  - Run: `odoo -d <test_db> --test-tags southbrook,prodboard_assets --stop-after-init`
  - Expected: fail because fields/importer do not exist.

- [ ] **Step 3: Implement minimal fields and importer**
  - Add private attachment/status/checksum fields on `southbrook.cabinet.archetype`.
  - Add import helper with network disabled by default and injectable fetcher for tests.
  - Add offline directory import path.

- [ ] **Step 4: Verify tests pass**
  - Run: `odoo -d <test_db> --test-tags southbrook,prodboard_assets --stop-after-init`
  - Expected: pass.

### Task 2: Template-to-Archetype Mapping

**Files:**
- Modify: `addons/southbrook_estimating/models/product_template.py`
- Create: `addons/southbrook_estimating/models/template_archetype.py`
- Create: `addons/southbrook_estimating/data/template_archetype_assign.xml`
- Modify: `addons/southbrook_estimating/models/__init__.py`
- Modify: `addons/southbrook_estimating/__manifest__.py`
- Test: `addons/southbrook_estimating/tests/test_template_archetype_mapping.py`

**Interfaces:**
- Produces: `product.template.x_prodboard_archetype_id`
- Produces: `southbrook.estimating.template_archetype.assign_archetypes()`

- [ ] **Step 1: Write failing tests**
  - Assert the 12 locked XML IDs still resolve.
  - Assert canonical mapped templates point to expected archetype codes:
    - `base_1dr` -> `CC-BHL1DR`
    - `base_2dr` -> `CC-BHL2DR`
    - `drawer_bank` -> `CC-BMD3DW`
    - `sink_base` -> `CC-BHS1DR`
    - `wall_1dr` -> `CC-WD{H}1DR`
    - `wall_2dr` -> `CC-WD{H}2DR`
    - `tall_oven` -> `CC-TA{H}SODRS`
    - `corner` -> `CC-CHL{S}`
  - Assert `vanity`, `accessory`, and `worktop` remain intentionally unmapped unless a real catalogue archetype exists.

- [ ] **Step 2: Verify tests fail**
  - Run: `odoo -d <test_db> --test-tags southbrook,prodboard_mapping --stop-after-init`
  - Expected: fail because field/helper do not exist.

- [ ] **Step 3: Implement mapping helper**
  - Add `x_prodboard_archetype_id` to `product.template`.
  - Add an idempotent helper that resolves template XML IDs and archetype codes.
  - Load it from XML after taxonomy and template code assignment.

- [ ] **Step 4: Verify tests pass**
  - Run: `odoo -d <test_db> --test-tags southbrook,prodboard_mapping --stop-after-init`
  - Expected: pass.

### Task 3: Documentation and Regression Verification

**Files:**
- Modify: `addons/southbrook_estimating/README.md`

**Interfaces:**
- Consumes: importer and mapping behavior from Tasks 1-2.
- Produces: operator guidance for online/offline asset import and the no-Prodboard-URL frontend rule.

- [ ] **Step 1: Document behavior**
  - Add a README section describing cloned taxonomy, private attachment cache, offline import option, mapped templates, and the public-image rule.

- [ ] **Step 2: Run focused tests**
  - Run: `odoo -d <test_db> --test-tags southbrook,prodboard_taxonomy,prodboard_assets,prodboard_mapping,image_uuid --stop-after-init`
  - Expected: pass.

- [ ] **Step 3: Static privacy scan**
  - Run: `rg "blobs\\.prodboard\\.com" addons/southbrook_estimating/static addons/southbrook_estimating/controllers addons/southbrook_estimating/views`
  - Expected: no matches.

- [ ] **Step 4: Review diff**
  - Run: `git diff --stat && git diff -- addons/southbrook_estimating docs/superpowers/plans/2026-06-18-prodboard-catalog-assets.md`
  - Expected: only planned files changed.

### Task 4: Southbrook-Owned Placeholder Images

**Files:**
- Modify: `addons/southbrook_estimating/models/template_archetype.py`
- Modify: `addons/southbrook_estimating/data/template_archetype_assign.xml`
- Modify: `addons/southbrook_estimating/tests/test_template_archetype_mapping.py`
- Modify: `addons/southbrook_estimating/README.md`

**Interfaces:**
- Produces: `southbrook.estimating.template_archetype.assign_placeholder_images(force=False)`
- Produces: deterministic `product.template.image_1920`, `x_image_uuid`, and `x_image_filename` values for the 12 locked templates.

- [ ] **Step 1: Write failing tests**
  - Assert `assign_placeholder_images(force=True)` gives all 12 locked templates PNG `image_1920` data and `southbrook-<xml_id>.png` filenames.
  - Assert `assign_placeholder_images()` preserves an existing product image while still assigning UUID/filename metadata.

- [ ] **Step 2: Verify tests fail**
  - Run: `odoo -d <test_db> --test-tags southbrook,prodboard_mapping --stop-after-init`
  - Expected: fail because `assign_placeholder_images()` does not exist yet.

- [ ] **Step 3: Implement placeholder generator**
  - Generate deterministic Southbrook-owned PNG bytes in Python.
  - Fill blank `image_1920` fields only by default.
  - Wire the helper into `data/template_archetype_assign.xml`.

- [ ] **Step 4: Verify locally**
  - Run: `python3 -m compileall -q addons/southbrook_estimating/models/template_archetype.py addons/southbrook_estimating/tests/test_template_archetype_mapping.py`
  - Run: `xmllint --noout addons/southbrook_estimating/data/template_archetype_assign.xml`
  - Expected: both pass.

## Self-Review

- Spec coverage: the plan preserves the locked templates, clones catalogue metadata into archetypes, imports assets privately, and keeps public UI on Southbrook-owned images.
- Placeholder scan: no task uses TBD/fill-in language.
- Type consistency: field and helper names are consistent across tasks.
