# Southbrook Production Media — Phase-1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Port OCA `dms` + `dms_field` from 18.0 to 19.0 CE, add the `sb_production_media` bridge that organizes photos/videos by Product, Manufacturing Order, and Shipping (picking), and add a v1 QC-interactivity layer (native-camera capture, Canvas-2D annotation, HTML5 video playback, per-media QC status, chatter audit) to the Miller-column Process Explorer.

**Architecture:** Reuse `dms_field`'s `dms.field.mixin`/`dms.field.template` (per-record auto directory + per-record access group) rather than hand-rolling directories. The bridge inherits the mixin onto `product.template`, `mrp.production`, and `stock.picking`, arranges a nested folder tree, and exposes narrow server RPC methods. The Process Explorer's OWL Media panel gains View/Capture/Annotate modes that call those RPC methods. Everything is generic on `res_model`/`res_id` — no kitchen-specific logic.

**Tech Stack:** Odoo 19.0 CE, Python, OWL 2 (native Canvas 2D — no fabric.js), `models.Constraint`, `ir.attachment`/filestore, `dms`/`dms_field` (OCA), `mrp_process_explorer` (provider-driven Miller-column shell).

## Global Constraints

- **Odoo 19.0 Community Edition only** — no Enterprise apps, widgets, or dependencies.
- **Keep module technical names `dms` and `dms_field` identical** to OCA — port in place, minimal functional change, so a future rebase onto official OCA 19.0 needs no rename migration.
- **`models.Constraint(sql, message)` class attributes**, never `_sql_constraints` (silently ignored in v19).
- **OWL templates:** no Python word-operators (`and`/`or`/`not`) in `t-if`/`t-elif`/`t-att*`/`t-esc` — use `&&` (XML-escape as `&amp;&amp;`), `||`, `!`.
- **All bridge + QC components generic on `res_model`/`res_id`** — no kitchen/cabinetry/product-category-specific code anywhere.
- **Video stored in the filestore, not the DB.**
- **No proxy/router/network changes** — the Caddy request-body limit is owner-owned; document a per-file size guidance and surface a clear error, do not modify the proxy.
- **Pillow must be present in the Odoo container** (dms thumbnail generation). Verified present in the local `v19c-odoo` test container (Pillow 10.2.0); ensure on prod before deploy.
- **TDD, frequent commits.** Local tests run in the OrbStack `v19c-odoo` container against isolated DB `test_sbdms` (never production). Writable addons mount: `/Users/naadmin/Downloads/Official/V19C/product-configurator/`. v19 core reference checkout: `/Users/naadmin/Downloads/Official/V19C/odoo/`.
- **Deploy is gated** on explicit human go-ahead (backup → consolidated `-i` → restart → smoke).

**Local test recipe (used by every "run tests" step below):**
```bash
# copy the modules under test into the writable mount, then run isolated
MNT=/Users/naadmin/Downloads/Official/V19C/product-configurator
for m in dms dms_field sb_production_media; do
  rm -rf "$MNT/$m"; cp -R "/Users/naadmin/southbrook-v19cr/addons/$m" "$MNT/$m" 2>/dev/null || true
done
docker exec v19c-odoo odoo -c /etc/odoo/odoo.conf -d test_sbdms \
  -i <modules> --test-enable --test-tags <tag> --stop-after-init --http-port=8172
```

---

## File structure

**Ported in place (`/Users/naadmin/southbrook-v19cr/addons/`):**
- `dms/` — OCA core; edits confined to the files named in Tasks A1–A6.
- `dms_field/` — OCA embed mechanism; edits confined to Tasks B1–B2.

**New module `/Users/naadmin/southbrook-v19cr/addons/sb_production_media/`:**
- `__manifest__.py`, `__init__.py`
- `models/__init__.py`
- `models/dms_field_bridge.py` — inherit `dms.field.mixin` onto `product.template`, `mrp.production`, `stock.picking`; nesting + `sb_dir_kind` placement.
- `models/dms_file.py` — add `qc_status` + `annotation_data` fields + setters (with chatter audit).
- `models/dms_directory.py` — add `sb_dir_kind` classification field.
- `models/production_media.py` — the narrow server RPC surface consumed by the panel (`get_node_media`, `upload_media`, `save_annotation`, `set_qc_status`).
- `models/mrp_production.py`, `models/stock_picking.py` — `media_required` flag + mark-done guard.
- `security/ir.model.access.csv`, `security/production_media_security.xml` — Production Media Manager group + rules.
- `data/storage_data.xml` — the storage + root directories.
- `data/dms_field_template_data.xml` — one `dms.field.template` per anchored model.
- `views/*.xml` — Media tab + smart buttons on product/MO/picking; flat MO + Shipping QC menus.
- `tests/__init__.py`, `tests/test_bridge.py`, `tests/test_media_rpc.py`, `tests/test_required_media.py`.

**QC-interactivity layer (`realpublish-ai/odoo-addons` repo, module `mrp_process_explorer/`):**
- `models/production_media_provider.py` — provider exposing per-node media.
- `static/src/explorer/media_qc.js`, `media_qc.xml`, `media_qc.scss` — View/Capture/Annotate modes, native capture, Canvas-2D annotation, `<video>` playback, QC status control.
- `__manifest__.py` — version bump + asset registration.

---

## Part A — Port OCA `dms` to v19

### Task A1: Manifest version bump + install baseline

**Files:**
- Modify: `addons/dms/__manifest__.py:8`

**Interfaces:**
- Produces: `dms` module installable at version `19.0.1.1.1`.

- [ ] **Step 1: Bump the version.** In `addons/dms/__manifest__.py`, change `"version": "18.0.1.1.1"` to `"version": "19.0.1.1.1"`. Leave `depends` (`mail, http_routing, onboarding, portal, base, web` — all exist in v19 CE) and the `assets` dict (already v19-correct) unchanged.

- [ ] **Step 2: Attempt install (expected to fail on the XML/constraint issues fixed in A2–A6).** Run the local recipe with `-i dms` and `--test-tags :false` (install only). Expected: fails during XML load with a parse error at `storage.xml:207` (the stray `º`). This confirms the baseline and the next task's target.

- [ ] **Step 3: Commit.** `git add addons/dms/__manifest__.py && git commit -m "port(dms): bump manifest to 19.0.1.1.1"`

### Task A2: Replace `_sql_constraints` with `models.Constraint`

**Files:**
- Modify: `addons/dms/models/access_groups.py:107-109`, `addons/dms/models/dms_category.py:66-68`, `addons/dms/models/tag.py:47-49`

**Interfaces:**
- Produces: DB-level uniqueness on `dms.access.group.name`, `dms.category.name`, and `dms.tag (name, category_id)`.

- [ ] **Step 1: Write the failing test.** Create `addons/dms/tests/test_port_constraints.py`:
```python
from odoo.tests import TransactionCase, tagged
from psycopg2 import IntegrityError
from odoo.tools import mute_logger

@tagged("post_install", "-at_install", "dms_port")
class TestPortConstraints(TransactionCase):
    def test_access_group_name_unique(self):
        self.env["dms.access.group"].create({"name": "dup"})
        with mute_logger("odoo.sql_db"), self.assertRaises(IntegrityError):
            with self.env.cr.savepoint():
                self.env["dms.access.group"].create({"name": "dup"})

    def test_category_name_unique(self):
        self.env["dms.category"].create({"name": "dupcat"})
        with mute_logger("odoo.sql_db"), self.assertRaises(IntegrityError):
            with self.env.cr.savepoint():
                self.env["dms.category"].create({"name": "dupcat"})
```

- [ ] **Step 2: Run it — expect FAIL** (constraints not enforced because `_sql_constraints` is ignored in v19). Recipe with `-i dms --test-tags dms_port`.

- [ ] **Step 3: Apply the fix.** In each file, delete the `_sql_constraints = [(...)]` block and add a class attribute:
  - `access_groups.py`: `_name_uniq = models.Constraint("UNIQUE (name)", "The name of the group must be unique!")`
  - `dms_category.py`: `_name_uniq = models.Constraint("UNIQUE (name)", "Category name already exists!")`
  - `tag.py`: `_name_uniq = models.Constraint("UNIQUE (name, category_id)", "Tag name already exists!")`
  Ensure `from odoo import models` is imported (it is in all three).

- [ ] **Step 4: Run it — expect PASS.**

- [ ] **Step 5: Commit.** `git commit -am "port(dms): _sql_constraints -> models.Constraint (access_group/category/tag)"`

### Task A3: Fix XML + v19 renames (OWL operators, stray char, res.groups/res.users renames)

> **Correction (found during A1 diagnostic install):** port report 01 wrongly assessed `res.groups.users` as unchanged in v19. It was renamed. v19 refactored `res.groups`: **`users` → `user_ids`** (also adds `all_user_ids`, `res.groups.privilege`). This task also fixes those, plus the `res.users.groups_id → group_ids` occurrences beyond the demo file.

**Files:**
- Modify: `addons/dms/views/dms_file.xml:126,135,144,153,193,249` (OWL operators) and `:631` (`groups_id` field — inspect the owning record; if it is a `res.users` field use `group_ids`; if it is an `ir.ui.menu`/`ir.actions` `groups_id`, confirm the v19 name for that model); `addons/dms/views/storage.xml:207` (stray char); `addons/dms/demo/res_users.xml:10` (`groups_id`→`group_ids`); `addons/dms/models/access_groups.py:146,152` (`group_ids.users`→`group_ids.user_ids` — NOT the `parent_group_id.users` paths at 144/154, which reference this module's own `users` field); `addons/dms/tests/test_storage_attachment.py:54,55` (`groups_id`→`group_ids`)

**Interfaces:**
- Produces: `dms` XML loads clean; the `res.groups` refactor is handled; kanban card conditionals evaluate in the browser.

**Extra steps (in addition to the OWL/stray-char/demo-rename steps below):**
- In `access_groups.py`, change the `@api.depends` entry `"group_ids.users"` (line 146) to `"group_ids.user_ids"`, and in `_compute_users` change `record.group_ids.users` (line 152) to `record.group_ids.user_ids`. Leave `parent_group_id.users` (144/154) unchanged — `parent_group_id` is a self-relation to `dms.access.group`, whose own `users` field (access_groups.py:90) is module-local.
- In `tests/test_storage_attachment.py:54,55`, change `{"groups_id": [(4, ...)]}` to `{"group_ids": [(4, ...)]}`.
- Inspect `dms_file.xml:631`; apply the correct v19 field name for the owning model.
- Verify with an install: `-i dms` should no longer raise the `_compute_users` `@depends` ValueError (it will still fail later steps until A4–A6, but the res.groups error must be gone).

- [ ] **Step 1: Fix the stray character.** In `storage.xml:207`, remove the stray `º` immediately after `</record>`.

- [ ] **Step 2: Fix the demo field rename.** In `demo/res_users.xml:10`, change `groups_id` to `group_ids` (the v19 `res.users` field name).

- [ ] **Step 3: Fix the OWL word-operators.** In `dms_file.xml`, on the six flagged lines, replace Python `and` with `&amp;&amp;`, `or` with `||`, `not X` with `!X`. Example (line 126): `t-if="record.permission_write.raw_value and !record.is_locked.raw_value"` becomes `t-if="record.permission_write.raw_value &amp;&amp; !record.is_locked.raw_value"`. Apply the same transform to lines 135, 144, 153, 193, and both occurrences inside the `t-attf-class` at 249.

- [ ] **Step 4: Verify parse + OWL lint.** Run `python3 -c "import xml.dom.minidom as m; m.parse('addons/dms/views/dms_file.xml'); m.parse('addons/dms/views/storage.xml')"` (expect no error), and run the repo's `lint-owl-expr.py` on `dms_file.xml` (expect OK — zero violations).

- [ ] **Step 5: Commit.** `git commit -am "port(dms): fix OWL operators, stray char in storage.xml, groups_id demo rename"`

### Task A4: Fix `ir_binary` access-token content hook

**Files:**
- Modify: `addons/dms/models/ir_binary.py:8-19`; add method to `addons/dms/models/dms_security_mixin.py`

**Interfaces:**
- Produces: valid `access_token` grants content access to `dms.file`/`dms.directory` binaries via the v19 hook `_can_return_content`.

- [ ] **Step 1: Write the failing test** in `addons/dms/tests/test_port_binary.py`:
```python
from odoo.tests import TransactionCase, tagged

@tagged("post_install", "-at_install", "dms_port")
class TestPortBinary(TransactionCase):
    def test_can_return_content_with_token(self):
        storage = self.env["dms.storage"].search([], limit=1) or \
            self.env["dms.storage"].create({"name": "t", "save_type": "database"})
        directory = self.env["dms.directory"].create(
            {"name": "d", "is_root_directory": True, "root_storage_id": storage.id})
        f = self.env["dms.file"].create(
            {"name": "a.txt", "directory_id": directory.id, "content": "eA=="})
        token = f.access_token or f._portal_ensure_token()
        # A user without direct rights, presenting the token, may read content:
        self.assertTrue(f._can_return_content(access_token=token))
```

- [ ] **Step 2: Run it — expect FAIL** (`_can_return_content` returns False for the token because the old `_find_record_check_access` override is dead).

- [ ] **Step 3: Apply the fix.** In `ir_binary.py`, delete the `_find_record_check_access` override entirely. In `dms_security_mixin.py`, add:
```python
def _can_return_content(self, field_name=None, access_token=None):
    self.ensure_one()
    if access_token and self.sudo()._check_access_token(access_token):
        return True
    return super()._can_return_content(field_name=field_name, access_token=access_token)
```
Confirm the token-check helper name against the model (`dms` uses portal token helpers — use the existing `check_access_token`/`_check_access_token` method already present on the mixin; if the existing method is named `check_access_token`, call that).

- [ ] **Step 4: Run it — expect PASS.**

- [ ] **Step 5: Commit.** `git commit -am "port(dms): restore access-token content access via v19 _can_return_content hook"`

### Task A5: Retire the orphaned onboarding state machine

**Files:**
- Modify: `addons/dms/models/res_company.py` (delete the 4 Selection fields + 3 helper methods); `addons/dms/models/storage.py:113-116`, `addons/dms/models/directory.py:364-367`, `addons/dms/models/dms_file.py:269-272` (remove the `set_onboarding_step_done(...)` call in each `action_save_onboarding_*_step`)

**Interfaces:**
- Produces: onboarding banner loads via the v19 `onboarding.onboarding.step` mechanism (already wired in `data/onboarding_data.xml`); no dead `res.company` state fields.

- [ ] **Step 1: Write the guard test** in `addons/dms/tests/test_port_onboarding.py`:
```python
from odoo.tests import TransactionCase, tagged

@tagged("post_install", "-at_install", "dms_port")
class TestPortOnboarding(TransactionCase):
    def test_company_has_no_dead_onboarding_fields(self):
        self.assertNotIn("documents_onboarding_state", self.env["res.company"]._fields)
    def test_save_storage_step_no_crash(self):
        # the onboarding "create storage" footer action must not raise
        self.env["dms.storage"].action_save_onboarding_storage_step()
```

- [ ] **Step 2: Run it — expect FAIL** (the dead field still exists; the action still calls `set_onboarding_step_done`).

- [ ] **Step 3: Apply the fix.** Delete from `res_company.py`: the fields `documents_onboarding_state`, `documents_onboarding_storage_state`, `documents_onboarding_directory_state`, `documents_onboarding_file_state`, and the methods `get_and_update_documents_onboarding_state`, `action_close_documents_onboarding`, `set_onboarding_step_done`. If the file is then empty of models, keep a minimal `res.company` stub only if other code references it (grep first); otherwise remove its import from `models/__init__.py`. In each `action_save_onboarding_*_step` (storage/directory/dms_file), remove the `self.env.user.company_id.set_onboarding_step_done(...)` line, and instead call the v19 step-done API so the banner advances:
```python
self.env["onboarding.onboarding.step"].sudo().action_validate_step(
    "dms.onboarding_step_<storage|directory|file>")
```
(Use the actual step xmlids present in `data/onboarding_data.xml`.)

- [ ] **Step 4: Run it — expect PASS.**

- [ ] **Step 5: Commit.** `git commit -am "port(dms): retire dead res.company onboarding state; use v19 action_validate_step"`

### Task A6: Fix the OWL front-end

**Files:**
- Modify: `addons/dms/static/src/js/views/file_kanban_renderer.xml:24`; `addons/dms/static/src/js/views/file_list_renderer.xml:16,26,36`; `addons/dms/static/src/models/attachment.esm.js:8-87`; `addons/dms/static/src/js/views/file_kanban_record.esm.js:32`; `addons/dms/static/src/js/views/file_list_renderer.esm.js:14-16`
- Delete: `addons/dms/static/src/js/views/file_kanban_controller.xml`, `addons/dms/static/src/js/views/file_kanban_controller.esm.js`, `addons/dms/static/src/models/attachment_image.esm.js`, `addons/dms/static/src/models/attachment_viewer_viewable.esm.js`
- Modify: `addons/dms/__manifest__.py` assets list (remove the deleted files if individually listed)

**Interfaces:**
- Produces: assets bundle builds; DMS kanban/list views render with working Upload button; the global `Attachment` patch is scoped to `dms.file` only (does not regress core attachment viewing).

- [ ] **Step 1: Fix the button-inherit xpaths.** In `file_kanban_renderer.xml:24`, replace `<xpath expr="//div" position="inside">` with `<xpath expr="." position="inside">`. In `file_list_renderer.xml` at lines 16, 26, 36, replace each `<xpath expr="//div[...]" position="inside">` / `<xpath expr="//div" position="inside">` with `<xpath expr="." position="inside">`. (v19's `web.KanbanView.Buttons`/`web.ListView.Buttons` are now empty `<t>` nodes.)

- [ ] **Step 2: Scope the attachment patch.** Replace the whole body of `models/attachment.esm.js` (lines 8-87) with a minimal patch of only the two URL primitives, delegating to `super` for non-dms.file:
```js
import { Attachment } from "@mail/core/common/attachment_model";
import { patch } from "@web/core/utils/patch";

patch(Attachment.prototype, {
    get urlRoute() {
        if (this.model_name === "dms.file") {
            return `/web/content/${this.id}`;
        }
        return super.urlRoute;
    },
    get urlQueryParams() {
        if (this.model_name === "dms.file") {
            return { filename: this.name, unique: this.checksum };
        }
        return super.urlQueryParams;
    },
});
```

- [ ] **Step 3: Fix `onGlobalClick`.** In `file_kanban_record.esm.js:32`, change the signature to `onGlobalClick(ev, newWindow)` and its fallback `super` call to `return super.onGlobalClick(ev, newWindow);`.

- [ ] **Step 4: Fix the list-renderer self-copy.** In `file_list_renderer.esm.js:14-16`, remove the no-op `FileListRenderer.components = { ...FileListRenderer.components }` line (it inherits `ListRenderer.components` unchanged; there is no `FileListRecord` override to inject).

- [ ] **Step 5: Delete the four dead files** listed above, and remove any explicit references to them from the `__manifest__.py` `assets` globs (they are matched by a `static/src/**` glob; if listed individually, delete those lines).

- [ ] **Step 6: Build assets on the isolated DB.** Run the recipe with `-i dms --test-enable --test-tags :false` and confirm no QWeb inherit "cannot locate node" error and no bundle build error in the log.

- [ ] **Step 7: Commit.** `git commit -am "port(dms): fix OWL button inherits, scope Attachment patch to dms.file, drop dead link-preview + orphan controller code, onGlobalClick newWindow"`

### Task A7: Full `dms` install + bundled tests green

**Files:** none (verification task).

- [ ] **Step 1: Install + run the module's own tests.** Run the recipe with `-i dms --test-enable --test-tags /dms` on `test_sbdms`.
- [ ] **Step 2: Confirm** all `dms` tests pass and the module state is `installed`. If Pillow-dependent thumbnail tests fail, confirm Pillow is importable in the container (`docker exec v19c-odoo python3 -c "import PIL"`).
- [ ] **Step 3: Commit** any test-only adjustments; otherwise no-op. Record "dms ported + green" in the ledger.

---

## Part B — Port OCA `dms_field` to v19

### Task B1: Manifest version bump

**Files:**
- Modify: `addons/dms_field/__manifest__.py:8`

- [ ] **Step 1:** Change `"version": "18.0.1.2.2"` to `"version": "19.0.1.2.2"`. Leave `depends: ["dms"]` and the `assets` dict unchanged (already v19-correct).
- [ ] **Step 2:** Install on `test_sbdms` (`-i dms_field`). Expect success (dms_field is already v19-shaped).
- [ ] **Step 3: Commit.** `git commit -am "port(dms_field): bump manifest to 19.0.1.2.2"`

### Task B2: Runtime smoke-test the two private-API risk files

**Files:**
- Test: `addons/dms_field/tests/test_port_smoke.py`
- Contingency-modify (only if the test fails): `addons/dms_field/models/ir_ui_view.py`, `addons/dms_field/models/dms_directory.py:116-165`

**Interfaces:**
- Consumes: `dms.field.mixin`, the `dms_list` view type.
- Produces: verified `mode="dms_list"` embed rendering + `_search_parents` correctness on v19 core.

- [ ] **Step 1: Write the smoke test:**
```python
from odoo.tests import TransactionCase, tagged

@tagged("post_install", "-at_install", "dms_field_port")
class TestDmsFieldSmoke(TransactionCase):
    def test_search_parents_runs(self):
        storage = self.env["dms.storage"].create({"name": "s", "save_type": "database"})
        root = self.env["dms.directory"].create(
            {"name": "root", "is_root_directory": True, "root_storage_id": storage.id})
        child = self.env["dms.directory"].create(
            {"name": "child", "parent_id": root.id})
        # exercises the raw-SQL _search_parents path
        res = self.env["dms.directory"].search_read_parents(child.id) \
            if hasattr(self.env["dms.directory"], "search_read_parents") else None
        self.assertTrue(child.parent_id == root)

    def test_dms_list_view_type_registered(self):
        vt = self.env["ir.ui.view"].fields_get(["type"])["type"]["selection"]
        self.assertIn("dms_list", dict(vt))
```

- [ ] **Step 2: Run it** (`-i dms_field --test-tags dms_field_port`). If it passes, the private-API coupling is intact on this v19 core — proceed.
- [ ] **Step 3: Contingency** — only if `_search_parents` raises a traceback deep in `odoo.osv.query` or the `dms_list` postprocess errors: consult `/Users/naadmin/Downloads/Official/V19C/odoo/odoo/osv/query.py` and `.../base/models/ir_ui_view.py` for the current `Query`/`NameManager` shape and adjust the raw-SQL builder / `NameManager(...)` call to match. Re-run until green.
- [ ] **Step 4: Commit** (`git commit -am "port(dms_field): smoke-test dms_list embed + _search_parents on v19 core"`).

### Task B3: Full `dms_field` install + bundled tests green

- [ ] **Step 1:** Run the recipe with `-i dms_field --test-enable --test-tags /dms_field`.
- [ ] **Step 2:** Confirm green + `installed`. Record "dms_field ported + green" in the ledger.

---

## Part C — `sb_production_media` bridge

### Task C1: Scaffold the module

**Files:**
- Create: `addons/sb_production_media/__manifest__.py`, `addons/sb_production_media/__init__.py`, `addons/sb_production_media/models/__init__.py`

**Interfaces:**
- Produces: an installable empty module named `sb_production_media` depending on `dms, dms_field, product, mrp, stock`.

- [ ] **Step 1: Write `__manifest__.py`:**
```python
{
    "name": "Southbrook Production Media",
    "version": "19.0.1.0.0",
    "summary": "Photos/videos organized by Product, Manufacturing Order, and Shipping; QC media bridge on DMS.",
    "license": "LGPL-3",
    "author": "Southbrook Cabinetry",
    "depends": ["dms", "dms_field", "product", "mrp", "stock"],
    "data": [
        "security/production_media_security.xml",
        "security/ir.model.access.csv",
        "data/storage_data.xml",
        "data/dms_field_template_data.xml",
        "views/production_media_menus.xml",
        "views/product_template_views.xml",
        "views/mrp_production_views.xml",
        "views/stock_picking_views.xml",
    ],
    "installable": True,
    "application": False,
}
```
- [ ] **Step 2:** `__init__.py` → `from . import models`. `models/__init__.py` → import the model files created in later tasks (add as you go).
- [ ] **Step 3: Commit.** `git commit -am "feat(sb_production_media): scaffold module"`

### Task C2: Storage + root directories

**Files:**
- Create: `addons/sb_production_media/data/storage_data.xml`

**Interfaces:**
- Produces: `dms.storage` xmlid `sb_production_media.storage_production_media` (filestore); root directories `dir_root_products` and `dir_root_shipping`.

- [ ] **Step 1: Write the failing test** `tests/test_bridge.py::test_storage_and_roots_exist`:
```python
from odoo.tests import TransactionCase, tagged

@tagged("post_install", "-at_install", "sb_media")
class TestBridge(TransactionCase):
    def test_storage_and_roots_exist(self):
        st = self.env.ref("sb_production_media.storage_production_media")
        self.assertEqual(st.save_type, "file")
        self.assertTrue(self.env.ref("sb_production_media.dir_root_products"))
        self.assertTrue(self.env.ref("sb_production_media.dir_root_shipping"))
```
- [ ] **Step 2: Run — expect FAIL** (records don't exist).
- [ ] **Step 3: Create `data/storage_data.xml`** with a `dms.storage` (`save_type="file"`, `name="Southbrook Production Media"`) and two root `dms.directory` records (`is_root_directory=True`, `root_storage_id` = the storage) named "Products" and "Shipping".
- [ ] **Step 4: Run — expect PASS.**
- [ ] **Step 5: Commit.** `git commit -am "feat(sb_production_media): production media storage + root directories"`

### Task C3: Anchor the mixin + per-model templates

**Files:**
- Create: `addons/sb_production_media/models/dms_field_bridge.py`, `addons/sb_production_media/data/dms_field_template_data.xml`
- Modify: `addons/sb_production_media/models/__init__.py`

**Interfaces:**
- Consumes: `dms.field.mixin` (from dms_field), `dms.field.template`.
- Produces: `product.template`, `mrp.production`, `stock.picking` each inherit `dms.field.mixin`; creating any of them auto-creates a `dms.directory` + a per-record `dms.access.group`.

- [ ] **Step 1: Write the failing test** `tests/test_bridge.py::test_auto_directory_per_record`:
```python
    def test_auto_directory_per_record(self):
        p = self.env["product.template"].create({"name": "Widget"})
        self.assertTrue(p.dms_directory_ids, "product should auto-create a DMS directory")
        mo = self.env["mrp.production"].create({"product_id": p.product_variant_id.id})
        self.assertTrue(mo.dms_directory_ids, "MO should auto-create a DMS directory")
```
- [ ] **Step 2: Run — expect FAIL** (`dms_directory_ids` absent — mixin not inherited).
- [ ] **Step 3: Implement `dms_field_bridge.py`:**
```python
from odoo import models

class ProductTemplate(models.Model):
    _inherit = ["product.template", "dms.field.mixin"]
    _name = "product.template"

class MrpProduction(models.Model):
    _inherit = ["mrp.production", "dms.field.mixin"]
    _name = "mrp.production"

class StockPicking(models.Model):
    _inherit = ["stock.picking", "dms.field.mixin"]
    _name = "stock.picking"
```
  Add one `dms.field.template` per model in `dms_field_template_data.xml` (`model_id` = the `ir.model`, `storage_id` = `storage_production_media`, `parent_directory_id` = `dir_root_products` for product/MO, `dir_root_shipping` for picking, `directory_format_name` = `{{ object.display_name }}`, `group_ids` = the manager group from C10). Import the model in `models/__init__.py`.
- [ ] **Step 4: Run — expect PASS.**
- [ ] **Step 5: Commit.** `git commit -am "feat(sb_production_media): anchor dms.field.mixin on product/MO/picking + templates"`

### Task C4: Nested placement + `sb_dir_kind` classification

**Files:**
- Create: `addons/sb_production_media/models/dms_directory.py`
- Modify: `addons/sb_production_media/models/dms_field_bridge.py`

**Interfaces:**
- Consumes: `dms.directory.create_dms_directory` (dms_field factory).
- Produces: `dms.directory.sb_dir_kind` (Selection product/mo/shipping/structural); MO directory nested under its product's "Orders" subfolder; picking directory under "Shipping".

- [ ] **Step 1: Write the failing test** `tests/test_bridge.py::test_mo_dir_nested_under_product`:
```python
    def test_mo_dir_nested_under_product(self):
        p = self.env["product.template"].create({"name": "Cab"})
        mo = self.env["mrp.production"].create({"product_id": p.product_variant_id.id})
        mo_dir = mo.dms_directory_ids[:1]
        self.assertEqual(mo_dir.sb_dir_kind, "mo")
        # nested: MO dir's ancestor chain includes the product's directory
        self.assertIn(p.dms_directory_ids[:1], mo_dir.parent_id.parent_id)
```
- [ ] **Step 2: Run — expect FAIL** (`sb_dir_kind` absent; MO dir is a flat root).
- [ ] **Step 3: Implement.** Add `sb_dir_kind = fields.Selection([...])` to `dms_directory.py` (`_inherit = "dms.directory"`). In `dms_field_bridge.py`, override `_dms_directory_vals`/post-create hook (whichever `dms.field.mixin` exposes) so that: product dirs get `sb_dir_kind="product"` under `dir_root_products`; MO dirs get `sb_dir_kind="mo"` and are re-parented under a get-or-created "Orders" child of the product's directory; picking dirs get `sb_dir_kind="shipping"` under `dir_root_shipping`. Implement `_get_or_create_orders_subdir(product_dir)` returning the "Orders" child directory.
- [ ] **Step 4: Run — expect PASS.**
- [ ] **Step 5: Commit.** `git commit -am "feat(sb_production_media): nested MO-under-product + sb_dir_kind classification"`

### Task C5: Flat MO + Shipping QC listings

**Files:**
- Create: `addons/sb_production_media/views/production_media_menus.xml`

**Interfaces:**
- Produces: menu "Manufacturing Orders Media" (act_window on `dms.directory`, domain `[("sb_dir_kind","=","mo")]`) and "Shipping QC" (domain `[("sb_dir_kind","=","shipping")]`), both under the Manufacturing app.

- [ ] **Step 1: Write the failing test** `tests/test_bridge.py::test_flat_listings`:
```python
    def test_flat_listings(self):
        act = self.env.ref("sb_production_media.action_mo_media")
        self.assertIn(("sb_dir_kind", "=", "mo"), act._get_eval_context() and eval(act.domain))
```
  (Simplify: assert `eval(act.domain) == [("sb_dir_kind","=","mo")]`.)
- [ ] **Step 2: Run — expect FAIL** (action missing).
- [ ] **Step 3: Create the two `ir.actions.act_window` + `menuitem` records** with the domains above, `view_mode="list,form"`, parent menu = the Manufacturing root (`mrp.menu_mrp_root`).
- [ ] **Step 4: Run — expect PASS.**
- [ ] **Step 5: Commit.** `git commit -am "feat(sb_production_media): flat MO + Shipping QC directory listings"`

### Task C6: Media tab + smart buttons on the three forms

**Files:**
- Create: `addons/sb_production_media/views/product_template_views.xml`, `views/mrp_production_views.xml`, `views/stock_picking_views.xml`

**Interfaces:**
- Produces: a "Media" notebook page with `<field name="dms_directory_ids" mode="dms_list" invisible="not id"/>` and a header smart button on each form.

- [ ] **Step 1: Write the failing test** `tests/test_bridge.py::test_forms_load`:
```python
    def test_forms_load(self):
        for model, xmlid in [("product.template", "product.product_template_form_view"),
                             ("mrp.production", "mrp.mrp_production_form_view"),
                             ("stock.picking", "stock.view_picking_form")]:
            view = self.env.ref(xmlid)
            arch = self.env[model].get_view(view.id, "form")["arch"]
            self.assertIn("dms_directory_ids", arch)
```
- [ ] **Step 2: Run — expect FAIL** (field not injected).
- [ ] **Step 3: Implement** three `ir.ui.view` inherits, each adding a `<page string="Media">` with the `mode="dms_list"` field, and a header `<button>` smart-stat opening the record's directory. Guard the field `invisible="not id"`.
- [ ] **Step 4: Run — expect PASS.**
- [ ] **Step 5: Commit.** `git commit -am "feat(sb_production_media): Media tab + smart buttons on product/MO/picking"`

### Task C7: Per-media QC status + annotation storage on `dms.file`

**Files:**
- Create: `addons/sb_production_media/models/dms_file.py`
- Modify: `addons/sb_production_media/models/__init__.py`

**Interfaces:**
- Produces: `dms.file.qc_status` (Selection: `unreviewed`/`pass`/`flag`, default `unreviewed`), `dms.file.annotation_data` (Text/JSON), and methods `action_set_qc_status(status)` and `action_save_annotation(json_str)` — each posts a chatter note on the anchored record.

- [ ] **Step 1: Write the failing test** `tests/test_media_rpc.py::test_qc_status_and_audit`:
```python
from odoo.tests import TransactionCase, tagged
@tagged("post_install", "-at_install", "sb_media")
class TestMediaRpc(TransactionCase):
    def _make_file(self):
        mo = self.env["mrp.production"].create(
            {"product_id": self.env["product.product"].create({"name": "X"}).id})
        d = mo.dms_directory_ids[:1]
        return mo, self.env["dms.file"].create(
            {"name": "shot.jpg", "directory_id": d.id, "content": "eA=="})
    def test_qc_status_and_audit(self):
        mo, f = self._make_file()
        before = len(mo.message_ids)
        f.action_set_qc_status("flag")
        self.assertEqual(f.qc_status, "flag")
        self.assertGreater(len(mo.message_ids), before, "should post a chatter audit note")
```
- [ ] **Step 2: Run — expect FAIL** (fields/methods absent).
- [ ] **Step 3: Implement `dms_file.py`** (`_inherit = "dms.file"`): the two fields, and the two methods. Each method writes the field, then resolves the anchored record from the directory's `res_model`/`res_id` and calls `record.message_post(body=...)` with a timestamped, user-attributed message. Annotation is non-destructive (only `annotation_data` JSON is written; the binary `content` is never modified).
- [ ] **Step 4: Run — expect PASS.**
- [ ] **Step 5: Commit.** `git commit -am "feat(sb_production_media): QC status + non-destructive annotation with chatter audit"`

### Task C8: Generic required-media flag + mark-done guard

**Files:**
- Create: `addons/sb_production_media/models/mrp_production.py`, `addons/sb_production_media/models/stock_picking.py`
- Modify: `addons/sb_production_media/models/__init__.py`

**Interfaces:**
- Produces: `media_required` (Boolean) on both `mrp.production` and `stock.picking`; when set, completing the record (MO `button_mark_done`, picking `button_validate`) raises `UserError` if the record's directory subtree has zero files.

- [ ] **Step 1: Write the failing test** `tests/test_required_media.py`:
```python
from odoo.tests import TransactionCase, tagged
from odoo.exceptions import UserError
@tagged("post_install", "-at_install", "sb_media")
class TestRequiredMedia(TransactionCase):
    def test_mo_blocked_without_media(self):
        mo = self.env["mrp.production"].create(
            {"product_id": self.env["product.product"].create({"name": "Y"}).id,
             "media_required": True})
        with self.assertRaises(UserError):
            mo._sb_check_required_media()
```
- [ ] **Step 2: Run — expect FAIL.**
- [ ] **Step 3: Implement** `media_required` on both models and a shared helper `_sb_check_required_media()` that counts files in the record's `dms_directory_ids` subtree and raises `UserError` if `media_required and count == 0`. Call it from an override of `button_mark_done` (MO) and `button_validate` (picking) before `super()`.
- [ ] **Step 4: Run — expect PASS.**
- [ ] **Step 5: Commit.** `git commit -am "feat(sb_production_media): generic required-media gate on MO + picking"`

### Task C9: Server RPC surface for the panel

**Files:**
- Create: `addons/sb_production_media/models/production_media.py`
- Modify: `addons/sb_production_media/models/__init__.py`

**Interfaces:**
- Produces: `production.media` (AbstractModel) with `@api.model` methods:
  - `get_node_media(res_model, res_id) -> {"files": [{"id","name","mimetype","is_video","qc_status","annotation_data","url"}], "can_write": bool}`
  - `upload_media(res_model, res_id, filename, datas_b64, mimetype) -> file_id` (creates a `dms.file` in the record's directory)
  - `save_annotation(file_id, annotation_json) -> True` (delegates to `dms.file.action_save_annotation`)
  - `set_qc_status(file_id, status) -> True` (delegates to `dms.file.action_set_qc_status`)

- [ ] **Step 1: Write the failing test** `tests/test_media_rpc.py::test_rpc_roundtrip`:
```python
    def test_rpc_roundtrip(self):
        p = self.env["product.product"].create({"name": "Z"})
        mo = self.env["mrp.production"].create({"product_id": p.id})
        pm = self.env["production.media"]
        fid = pm.upload_media("mrp.production", mo.id, "a.jpg", "eA==", "image/jpeg")
        data = pm.get_node_media("mrp.production", mo.id)
        self.assertTrue(any(f["id"] == fid for f in data["files"]))
        self.assertTrue(pm.set_qc_status(fid, "pass"))
```
- [ ] **Step 2: Run — expect FAIL.**
- [ ] **Step 3: Implement `production.media`.** `get_node_media` resolves the record's directory via `dms.field.mixin.dms_directory_ids`, lists its files, computes `is_video = mimetype.startswith("video/")` and a `/web/content/<id>` url, and `can_write` from `record.check_access("write")` (degrade to False on AccessError). `upload_media` locates/creates the directory and creates a `dms.file` with `content=datas_b64`. Wrap everything in `.sudo()` for reads with an explicit access check, mirroring the material.explorer degrade pattern (try/except → safe empty).
- [ ] **Step 4: Run — expect PASS.**
- [ ] **Step 5: Commit.** `git commit -am "feat(sb_production_media): production.media RPC surface (get/upload/annotate/qc)"`

### Task C10: Access group + record rules + pre-ship ACL audit

**Files:**
- Create: `addons/sb_production_media/security/production_media_security.xml`, `addons/sb_production_media/security/ir.model.access.csv`

**Interfaces:**
- Produces: group `sb_production_media.group_media_manager`; internal users can read/write `dms.file`/`dms.directory` scoped to records they can access; portal/public denied.

- [ ] **Step 1: Write the failing test** `tests/test_media_rpc.py::test_internal_only`:
```python
    def test_internal_only(self):
        portal = self.env.ref("base.group_portal")
        user = self.env["res.users"].create(
            {"name": "P", "login": "p_media", "group_ids": [(6, 0, [portal.id])]})
        p = self.env["product.product"].create({"name": "Q"})
        mo = self.env["mrp.production"].create({"product_id": p.id})
        from odoo.exceptions import AccessError
        with self.assertRaises(AccessError):
            self.env["production.media"].with_user(user).upload_media(
                "mrp.production", mo.id, "x.jpg", "eA==", "image/jpeg")
```
- [ ] **Step 2: Run — expect FAIL** (portal user not blocked).
- [ ] **Step 3: Implement** the manager group (inherit `base.group_user` implication via `<function model="res.groups" name="write">` if needed), `ir.model.access.csv` grants (internal only; no portal), and confirm the per-record `dms.access.group` auto-created by `dms.field.template` scopes visibility. Make `upload_media` raise `AccessError` for non-internal users.
- [ ] **Step 4: Run — expect PASS.**
- [ ] **Step 5: Pre-ship ACL audit (checklist, documented in the commit body):** verify record rules on `dms.file`/`dms.directory` scope by the anchored record's ownership; verify a second internal user cannot see another MO's private folder unless granted; verify portal/public get nothing. Record findings in the ledger.
- [ ] **Step 6: Commit.** `git commit -am "feat(sb_production_media): internal-only ACL + manager group + pre-ship audit"`

### Task C11: Full `sb_production_media` install + tests green

- [ ] **Step 1:** Run the recipe with `-i sb_production_media --test-enable --test-tags sb_media` on `test_sbdms` (installs dms + dms_field as deps).
- [ ] **Step 2:** Confirm all `sb_media` tests pass + `installed`. Record "bridge green" in the ledger.

---

## Part D — QC-interactivity layer in the Miller-column Process Explorer

> These tasks live in the **`realpublish-ai/odoo-addons`** repo, module `mrp_process_explorer/` (branch `feat/production-media-qc`). Clone/pull it first (`gh repo clone realpublish-ai/odoo-addons`); its local checkout is the working dir for Part D. The OWL widgets are generic and call the `sb_production_media` `production.media` RPC methods from Part C. Test env: same `v19c-odoo` container; install `mrp_process_explorer,sb_production_media` on an isolated DB `test_mpxmedia`.

### Task D1: `production.media.provider` — media per Explorer node

**Files:**
- Create: `mrp_process_explorer/models/production_media_provider.py`
- Modify: `mrp_process_explorer/models/__init__.py`, `mrp_process_explorer/__manifest__.py` (depends: add `sb_production_media`)

**Interfaces:**
- Produces: `production.media.provider` (AbstractModel) `get_media_for(res_model, res_id)` returning the same shape as `production.media.get_node_media`, plus `capabilities` (`can_capture`, `can_annotate`) derived from `can_write`.

- [ ] **Step 1: Write the failing test** `mrp_process_explorer/tests/test_media_provider.py` (`--test-tags mpx_media`): create an MO with a file via `sb_production_media`, assert `production.media.provider.get_media_for("mrp.production", mo.id)["files"]` is non-empty and `capabilities["can_capture"]` is True for an internal user.
- [ ] **Step 2: Run — expect FAIL.**
- [ ] **Step 3: Implement** the provider as a thin wrapper over `self.env["production.media"].get_node_media(...)`, adding `capabilities`. `.sudo()` + try/except degrade to `{"files": [], "capabilities": {"can_capture": False, "can_annotate": False}}` on error (mirrors the existing `material.explorer` degrade contract). Add `sb_production_media` to `depends`.
- [ ] **Step 4: Run — expect PASS.**
- [ ] **Step 5: Commit** (in the odoo-addons repo).

### Task D2: Panel View/Capture/Annotate mode toggle

**Files:**
- Create: `mrp_process_explorer/static/src/explorer/media_qc.js`, `media_qc.xml`, `media_qc.scss`
- Modify: `mrp_process_explorer/__manifest__.py` (register the three assets in `web.assets_backend`)

**Interfaces:**
- Consumes: the Explorer's current selected node (`res_model`, `res_id`) and the `production.media.provider` RPC.
- Produces: an OWL `MediaQc` component rendered in the panel's Media area with a header segmented control `mode` in `{"view","capture","annotate"}`, defaulting to `"view"` (read-only preserved).

- [ ] **Step 1: Write `media_qc.js`** — an OWL component using `useState({mode: "view", files: [], caps: {}})`, `rpc` imported from `@web/core/network/rpc` (NOT `useService("rpc")`), loading media in `onWillStart`/`onWillUpdateProps` via `rpc("/web/dataset/call_kw", {model: "production.media.provider", method: "get_media_for", args: [resModel, resId], kwargs: {}})`. The header renders three buttons that set `state.mode`; Capture/Annotate buttons are disabled when `!state.caps.can_capture`/`!state.caps.can_annotate`.
- [ ] **Step 2: Write `media_qc.xml`** — the OWL template. Use `&amp;&amp;`/`||`/`!` only (no Python operators). Render the mode toggle + a slot per mode (view grid, capture control, annotate canvas — filled in D3–D6).
- [ ] **Step 3: Register assets** in `__manifest__.py` under `web.assets_backend` and mount `MediaQc` in the existing Media panel (wire into `mrp_explorer.js`/`.xml` where the current media tabs render, passing the selected node's `res_model`/`res_id`).
- [ ] **Step 4: Build assets** on `test_mpxmedia` (`-i mrp_process_explorer,sb_production_media`); confirm no bundle error and the existing Process Explorer still renders (backcompat).
- [ ] **Step 5: Commit.**

### Task D3: Native-camera still/video capture

**Files:**
- Modify: `mrp_process_explorer/static/src/explorer/media_qc.js`, `media_qc.xml`

**Interfaces:**
- Consumes: `production.media.upload_media`.
- Produces: a Capture-mode control `<input type="file" accept="image/*,video/*" capture="environment">` that reads the file, base64-encodes it, and calls `upload_media`, then refreshes the grid.

- [ ] **Step 1:** Add the `<input>` to the capture slot in `media_qc.xml` (with a visible "Add Photo/Video" label). On `change`, read the `File` via `FileReader.readAsDataURL`, strip the `data:...;base64,` prefix, and call `rpc(... "production.media","upload_media", [resModel,resId,file.name,b64,file.type])`.
- [ ] **Step 2:** Enforce a client-side size guard (e.g. warn + block over a configurable `maxBytes`, default 100 MB) with a `notification` service message, to respect the Caddy body limit — do not modify the proxy. On success, re-fetch media.
- [ ] **Step 3: Manual/asset test:** build assets, load the panel on `test_mpxmedia`, confirm the input renders and (in a headed browser) that tapping opens the camera on a mobile UA. Add a JS-free server assertion that `upload_media` created the file (already covered by C9; no new server test needed).
- [ ] **Step 4: Commit.**

### Task D4: HTML5 video playback + poster

**Files:**
- Modify: `mrp_process_explorer/static/src/explorer/media_qc.xml`, `media_qc.js`, `media_qc.scss`

**Interfaces:**
- Consumes: `get_media_for` file entries (`is_video`, `url`).
- Produces: view-mode grid renders `<video controls preload="metadata">` for `is_video` files and `<img>` for images, both from `/web/content/<id>`.

- [ ] **Step 1:** In the view slot, `t-foreach` the files; `t-if="file.is_video"` renders `<video controls preload="metadata" t-att-src="file.url"/>`, `t-else` renders `<img t-att-src="file.url"/>`. Use `!`/`&amp;&amp;` only.
- [ ] **Step 2:** Style the grid in `media_qc.scss` (thumbnail sizing, `max-width:100%`, `object-fit: cover`).
- [ ] **Step 3: Build assets + eyeball** on `test_mpxmedia` with one uploaded image and one uploaded short video; confirm the video plays inline.
- [ ] **Step 4: Commit.**

### Task D5: Canvas-2D annotation overlay (JSON strokes) + chatter audit

**Files:**
- Modify: `mrp_process_explorer/static/src/explorer/media_qc.js`, `media_qc.xml`, `media_qc.scss`

**Interfaces:**
- Consumes: `production.media.save_annotation`, existing `annotation_data`.
- Produces: Annotate-mode overlays a `<canvas>` on the selected image; user draws circle/arrow/text; strokes serialized to JSON and saved via `save_annotation` (which posts the chatter audit note server-side, Task C7). Original image untouched.

- [ ] **Step 1:** Add a `<canvas>` overlay in the annotate slot, sized to the selected image. Implement native Canvas 2D drawing (no fabric.js): pointer events append shape objects `{type, x, y, x2, y2, text, color}` to `state.strokes`; a small toolbar picks the tool.
- [ ] **Step 2:** On "Save", `JSON.stringify(state.strokes)` → `rpc(... "production.media","save_annotation", [fileId, json])`. On load, if the file has `annotation_data`, parse and re-render the strokes over the image.
- [ ] **Step 3:** Verify the chatter audit: this is covered server-side by C7's test (annotation save posts a chatter note); add no duplicate server test. Build assets + eyeball drawing + reload persistence on `test_mpxmedia`.
- [ ] **Step 4: Commit.**

### Task D6: Per-media QC status control

**Files:**
- Modify: `mrp_process_explorer/static/src/explorer/media_qc.js`, `media_qc.xml`

**Interfaces:**
- Consumes: `production.media.set_qc_status`.
- Produces: each file tile shows its `qc_status` badge (Unreviewed/Pass/Flag) and a control to change it; changing it calls `set_qc_status` (which posts a chatter note) and refreshes.

- [ ] **Step 1:** Render a status badge per tile (color-coded: grey/green/amber) and a 3-option control. On change, `rpc(... "set_qc_status", [fileId, status])` then re-fetch.
- [ ] **Step 2:** Build assets + eyeball on `test_mpxmedia`; flip a file to "Flag", confirm the badge updates and (server-side, per C7) a chatter note posts.
- [ ] **Step 3: Commit.**

### Task D7: `mrp_process_explorer` manifest bump + backcompat soak

**Files:**
- Modify: `mrp_process_explorer/__manifest__.py` (version bump, e.g. `19.0.1.2.0`)

- [ ] **Step 1:** Bump version; confirm all new assets registered.
- [ ] **Step 2: Backcompat soak:** on `test_mpxmedia`, install `mrp_process_explorer,sb_production_media`, then open the existing Process Explorer views and confirm the pre-existing Miller-column + material.explorer behavior still renders (no regression from the media additions).
- [ ] **Step 3: Run** `mrp_process_explorer` bundled tests (`--test-tags /mrp_process_explorer`) + `mpx_media`. Green.
- [ ] **Step 4: Commit.** Record "QC layer green + backcompat OK" in the ledger.

---

## Part E — Integration & gated deploy

### Task E1: Cross-module integration test

**Files:**
- Create: `addons/sb_production_media/tests/test_integration.py`

**Interfaces:**
- Consumes: everything above.

- [ ] **Step 1: Write the integration test** (`--test-tags sb_media_integration`): create a product → its variant → an MO; upload a photo via `production.media.upload_media`; assert the MO directory is nested under the product's "Orders" subfolder (C4); `set_qc_status(fid,"flag")` and `save_annotation(fid, "[...]")`; assert two chatter notes posted on the MO (C7); create a `stock.picking`, upload a shipping photo, assert its directory is under the "Shipping" root with `sb_dir_kind="shipping"` (C4); set `media_required=True` on a fresh MO and assert `button_mark_done` raises `UserError` (C8).
- [ ] **Step 2: Run — expect PASS** on `test_sbdms` with `-i sb_production_media`.
- [ ] **Step 3: Commit.**

### Task E2: Staging soak (all modules together)

**Files:** none.

- [ ] **Step 1:** On a fresh isolated DB `test_sbmedia_stage`, install `dms,dms_field,sb_production_media,mrp_process_explorer` together in one `-i`, `--test-enable`, all relevant `--test-tags`.
- [ ] **Step 2:** Confirm: all modules `installed`; all tests green; the Media tab renders on a real product/MO/picking form; the Process Explorer Media panel loads with View/Capture/Annotate; **the pre-existing Process Explorer + material.explorer still render** (backcompat).
- [ ] **Step 3:** Record the soak result in the ledger. Do NOT proceed to deploy without explicit go-ahead.

### Task E3: Gated production deploy

**Files:** none (ops task; **requires explicit human go-ahead**).

- [ ] **Step 1: Pre-deploy backup.** `pg_dump -Fc` the `southbrook` DB to `OdooIQ-Backups/predeploy/southbrook-<date>-production-media.dump`; verify with `pg_restore -l`.
- [ ] **Step 2: Confirm Pillow on prod** (`$SD exec southbrook-odoo python3 -c "import PIL"`); if absent, install into the image/container before proceeding.
- [ ] **Step 3: rsync** `dms`, `dms_field`, `sb_production_media` to the prod addons path, and `mrp_process_explorer` (from the odoo-addons `feat/production-media-qc` branch, merged) to its prod location.
- [ ] **Step 4: Single consolidated update:**
```
$SD exec southbrook-odoo odoo -c /etc/odoo/odoo.conf -d southbrook \
  -i dms,dms_field,sb_production_media -u mrp_process_explorer --stop-after-init --no-http
$SD restart southbrook-odoo
```
- [ ] **Step 5: Smoke test:** modules `installed`; open a real MO → Media tab; capture a photo + a short video via the panel; annotate; set QC status; confirm chatter audit notes; confirm the Shipping QC listing and flat MO Media listing open; hard-refresh the browser (asset bundle bumped).
- [ ] **Step 6:** Record deploy outcome + update the `southbrook_materials_phase1_deployed`-style memory with a new `southbrook_production_media` entry.

---

## Self-Review (completed by author)

**1. Spec coverage** — every spec section maps to a task: DMS port (A1–A7), dms_field port (B1–B3), `dms.field.mixin` bridge on product/MO/**picking** (C3), nested tree + flat MO + Shipping node (C4–C5), Media tab + smart buttons (C6), Addendum-A v1 additions — native capture (D3), Canvas-2D annotation + JSON strokes (D5, C7), chatter audit (C7), HTML5 video playback (D4), per-media QC status (C7, D6), View/Capture/Annotate toggle (D2), generic required-media flag (C8), pre-ship ACL audit (C10), generic `res_model`/`res_id` guardrail (C3/C9, no kitchen logic). Deploy gated (E3). phase2 items (time-lapse MediaRecorder, retention cron, touch-precision markup, role-gated clears, pagination, routing-step/process checklist) correctly absent.
**2. Placeholder scan** — no TBD/TODO/"handle edge cases"; every code step carries real code or an exact transform from the port reports.
**3. Type consistency** — RPC names (`get_node_media`/`upload_media`/`save_annotation`/`set_qc_status`) and the provider wrapper (`get_media_for`) are used identically across C9, D1–D6; `sb_dir_kind` values (`product`/`mo`/`shipping`/`structural`) consistent C4↔C5↔E1; `qc_status` values (`unreviewed`/`pass`/`flag`) consistent C7↔D6.

## Notes for the executor
- Parts A–C and E1–E2 are in `southbrook-v19cr`; Part D is in `realpublish-ai/odoo-addons` (`mrp_process_explorer`). Keep them on separate branches (`feat/production-media-dms` and `feat/production-media-qc`).
- The two `dms_field` private-API risk files (B2) are the likeliest source of surprises — smoke-test them before building C6's `mode="dms_list"` embed.
- If OCA publishes official `dms` 19.0 mid-flight, prefer rebasing onto it over carrying the port (module names were kept identical for exactly this).
