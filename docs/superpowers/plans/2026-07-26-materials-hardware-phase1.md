# Materials Hardware — Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `sb_materials_hardware` — a faceted, spec-first catalog for Southbrook's hardware, tooling and shop consumables, delivered as an internal Odoo 19 backend client action reproducing the reference UX.

**Architecture:** A domain-agnostic catalog shell (OWL client action) renders whatever a provider returns. Phase 1 ships one provider reading `southbrook_mrp_kitchen_tools` data. The module owns **no** domain data — no taxonomy, no spec fields, no consumption model. Facets and columns are declared as records, so adding one is a data change.

**Tech Stack:** Odoo 19 Community Edition, Python 3.12, OWL 2, SCSS. No new third-party dependencies.

## Global Constraints

- **License header** on every `.py` file, first line: `# SPDX-License-Identifier: LGPL-3.0-only`
- **Manifest key order:** `name`, `version`, `category`, `summary`, `author`, `license`, `depends`, `data`, `assets`, `installable`
- **Version:** `19.0.1.0.0` · **License:** `"LGPL-3"` · **Author:** `"Southbrook / METISA"` · **Category:** `"Manufacturing"`
- **Constraints use `models.Constraint`**, never `_sql_constraints` — Odoo 19 silently ignores the latter. Pattern: `_field_uniq = models.Constraint("unique(field)", "Message.")`
- **Tests:** `from odoo.tests.common import TransactionCase, tagged`, decorated `@tagged("post_install", "-at_install", "southbrook", "sbk_mathw")`
- **JS:** import rpc-adjacent services via `useService("orm")`. The `rpc` *service* was removed in Odoo 19 — if raw rpc is ever needed, `import { rpc } from "@web/core/network/rpc"`.
- **OWL templates:** no Python operators in `t-` expressions. Use `||`, `&&`, `!` — never `or`, `and`, `not`. No JS regex literals in `t-` expressions.
- **SCSS:** never lowercase `min()` / `max()` / `clamp()` with mixed units — libsass mis-parses them. Use `Min()` / `Max()` / `Clamp()`.
- **No `sudo()` on record reads.** No public HTTP routes. No `website` dependency.
- **Absent is a real state.** A spec field that is unset renders as `—`, never `0` or blank.
- **Asset changes need a server restart** to bump the bundle hash; `-u` alone can serve a stale bundle.

**Reference UX (acceptance target):** `Material Hardware App/reference/UX_TEMPLATE_materials_catalog.html`
**Spec:** `Material Hardware App/spec/2026-07-25-materials-hardware-design.md`

## File Structure

```
addons/sb_materials_hardware/
├── __init__.py                          imports models
├── __manifest__.py                      manifest + assets bundle
├── models/
│   ├── __init__.py
│   ├── catalog_declaration.py           materials.catalog.facet, materials.catalog.column
│   ├── catalog_provider.py              materials.catalog.provider — contract, dispatch, helpers
│   └── tools_catalog_provider.py        tools.catalog.provider — the Phase 1 implementation
├── data/
│   ├── catalog_declarations.xml         facet + column records for sections A–E
│   └── catalog_action.xml               ir.actions.client + menu item
├── security/
│   └── ir.model.access.csv
├── static/src/catalog/
│   ├── catalog.js                       OWL component
│   ├── catalog.xml                      OWL templates
│   └── catalog.scss                     styles ported from the reference palette
└── tests/
    ├── __init__.py
    ├── test_install.py
    ├── test_declarations.py
    ├── test_provider_contract.py
    ├── test_category_tree.py
    ├── test_columns.py
    ├── test_facets.py
    ├── test_filtering.py
    ├── test_rows.py
    ├── test_detail.py
    └── test_access.py
```

**Responsibilities.** `catalog_declaration.py` holds only the two declaration models. `catalog_provider.py` holds the abstract contract, the scope dispatcher, and pure helpers with no `southbrook_mrp_kitchen_tools` knowledge. `tools_catalog_provider.py` is the only file that knows about `x_southbrook_*` fields — so Phase 2's second provider is a sibling file, not a rewrite.

**Data facts this plan relies on** (verified in the module, not assumed):
- Taxonomy model: `southbrook.tool.category` — `_parent_store = True`, has `parent_id`, `parent_path`, `complete_name`, `code`, `active`
- Link field on `product.template`: `x_southbrook_tool_category_id` (Many2one)
- All `x_southbrook_*` fields are plain stored fields on `product.template`; none required, none computed
- 101 seeded categories, L0–L2, xml ids like `southbrook_mrp_kitchen_tools.cat_screws`

---

### Task 1: Module scaffold, client action, menu

**Files:**
- Create: `addons/sb_materials_hardware/__init__.py`
- Create: `addons/sb_materials_hardware/__manifest__.py`
- Create: `addons/sb_materials_hardware/models/__init__.py`
- Create: `addons/sb_materials_hardware/data/catalog_action.xml`
- Create: `addons/sb_materials_hardware/security/ir.model.access.csv`
- Test: `addons/sb_materials_hardware/tests/__init__.py`, `addons/sb_materials_hardware/tests/test_install.py`

**Interfaces:**
- Consumes: nothing
- Produces: module `sb_materials_hardware`; xml id `sb_materials_hardware.action_materials_hardware_catalog` (an `ir.actions.client` with `tag = "sb_materials_hardware.catalog"`); menu `sb_materials_hardware.menu_materials_hardware_catalog`

- [ ] **Step 1: Write the failing test**

`tests/test_install.py`:
```python
# SPDX-License-Identifier: LGPL-3.0-only
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "sbk_mathw")
class TestInstall(TransactionCase):
    def test_client_action_exists(self):
        action = self.env.ref(
            "sb_materials_hardware.action_materials_hardware_catalog")
        self.assertEqual(action.tag, "sb_materials_hardware.catalog")
        self.assertEqual(action.target, "current")

    def test_menu_exists(self):
        menu = self.env.ref(
            "sb_materials_hardware.menu_materials_hardware_catalog")
        self.assertTrue(menu.action)
```

`tests/__init__.py`:
```python
# SPDX-License-Identifier: LGPL-3.0-only
from . import test_install
```

- [ ] **Step 2: Run test to verify it fails**

Run: `odoo-bin -d <db> -i sb_materials_hardware --test-enable --stop-after-init --test-tags=sbk_mathw`
Expected: FAIL — module not found / xml id does not exist.

- [ ] **Step 3: Write minimal implementation**

`__init__.py`:
```python
# SPDX-License-Identifier: LGPL-3.0-only
from . import models
```

`models/__init__.py`:
```python
# SPDX-License-Identifier: LGPL-3.0-only
```

`__manifest__.py`:
```python
# SPDX-License-Identifier: LGPL-3.0-only
{
    "name": "Southbrook Materials — Hardware Catalog",
    "version": "19.0.1.0.0",
    "category": "Manufacturing",
    "summary": "Faceted, spec-first catalog for hardware, tooling and shop "
               "consumables. Reads southbrook_mrp_kitchen_tools data; owns no "
               "domain model of its own.",
    "author": "Southbrook / METISA",
    "license": "LGPL-3",
    "depends": ["product", "uom", "stock", "southbrook_mrp_kitchen_tools"],
    "data": [
        "security/ir.model.access.csv",
        "data/catalog_action.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "sb_materials_hardware/static/src/catalog/catalog.scss",
            "sb_materials_hardware/static/src/catalog/catalog.js",
            "sb_materials_hardware/static/src/catalog/catalog.xml",
        ],
    },
    "installable": True,
}
```

`data/catalog_action.xml`:
```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
  <record id="action_materials_hardware_catalog" model="ir.actions.client">
    <field name="name">Hardware Catalog</field>
    <field name="tag">sb_materials_hardware.catalog</field>
    <field name="target">current</field>
  </record>

  <menuitem id="menu_materials_hardware_catalog"
            name="Hardware Catalog"
            parent="stock.menu_stock_root"
            action="action_materials_hardware_catalog"
            sequence="81"/>
</odoo>
```

`security/ir.model.access.csv` (header only for now — no models yet):
```csv
id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
```

Create empty placeholder asset files so the bundle resolves:
`static/src/catalog/catalog.js` containing `/** @odoo-module **/`, `static/src/catalog/catalog.xml` containing `<templates/>`, `static/src/catalog/catalog.scss` empty.

- [ ] **Step 4: Run test to verify it passes**

Run: `odoo-bin -d <db> -i sb_materials_hardware --test-enable --stop-after-init --test-tags=sbk_mathw`
Expected: PASS, 2 tests.

- [ ] **Step 5: Commit**

```bash
git add addons/sb_materials_hardware
git commit -m "feat(materials-hardware): module scaffold, client action, menu"
```

---

### Task 2: Facet and column declaration models

**Files:**
- Create: `addons/sb_materials_hardware/models/catalog_declaration.py`
- Modify: `addons/sb_materials_hardware/models/__init__.py`
- Modify: `addons/sb_materials_hardware/security/ir.model.access.csv`
- Modify: `addons/sb_materials_hardware/__manifest__.py` (add `data/catalog_declarations.xml` after this task's data file exists — leave until Task 11; do not add now)
- Test: `addons/sb_materials_hardware/tests/test_declarations.py`

**Interfaces:**
- Consumes: nothing
- Produces:
  - `materials.catalog.facet` with fields `name` (Char, required), `sequence` (Integer, default 10), `category_id` (Many2one `southbrook.tool.category`, required), `field_name` (Char, required), `facet_type` (Selection: `enum`, `enum_distinct`, `range`, `m2m`, `flag`; required), `active` (Boolean, default True)
  - `materials.catalog.column` with fields `name` (Char, required), `sequence`, `category_id` (Many2one, required), `field_name` (Char, required), `align` (Selection `left`/`right`, default `left`), `sortable` (Boolean, default True), `active`
  - Both carry `_order = "sequence, id"` and a uniqueness constraint on `(category_id, field_name)`

- [ ] **Step 1: Write the failing test**

`tests/test_declarations.py`:
```python
# SPDX-License-Identifier: LGPL-3.0-only
from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase, tagged
from psycopg2 import IntegrityError
from odoo.tools import mute_logger


@tagged("post_install", "-at_install", "southbrook", "sbk_mathw")
class TestDeclarations(TransactionCase):
    def setUp(self):
        super().setUp()
        self.cat = self.env.ref("southbrook_mrp_kitchen_tools.cat_screws")

    def test_facet_created(self):
        facet = self.env["materials.catalog.facet"].create({
            "name": "Thread type",
            "category_id": self.cat.id,
            "field_name": "x_southbrook_thread_type",
            "facet_type": "enum",
        })
        self.assertEqual(facet.sequence, 10)
        self.assertTrue(facet.active)

    def test_column_created(self):
        col = self.env["materials.catalog.column"].create({
            "name": "Length (mm)",
            "category_id": self.cat.id,
            "field_name": "x_southbrook_screw_length_mm",
            "align": "right",
        })
        self.assertTrue(col.sortable)

    @mute_logger("odoo.sql_db")
    def test_facet_unique_per_category(self):
        vals = {
            "name": "Thread type",
            "category_id": self.cat.id,
            "field_name": "x_southbrook_thread_type",
            "facet_type": "enum",
        }
        self.env["materials.catalog.facet"].create(vals)
        with self.assertRaises(IntegrityError):
            with self.env.cr.savepoint():
                self.env["materials.catalog.facet"].create(dict(vals))

    def test_field_name_must_exist_on_product_template(self):
        with self.assertRaises(ValidationError):
            self.env["materials.catalog.facet"].create({
                "name": "Nonsense",
                "category_id": self.cat.id,
                "field_name": "x_southbrook_not_a_real_field",
                "facet_type": "enum",
            })
```

Add `from . import test_declarations` to `tests/__init__.py`.

- [ ] **Step 2: Run test to verify it fails**

Run: `odoo-bin -d <db> -u sb_materials_hardware --test-enable --stop-after-init --test-tags=sbk_mathw`
Expected: FAIL — `KeyError: 'materials.catalog.facet'`.

- [ ] **Step 3: Write minimal implementation**

`models/catalog_declaration.py`:
```python
# SPDX-License-Identifier: LGPL-3.0-only
"""Facet and column declarations.

Adding a facet or a column to the catalog is a DATA change: create a record.
No per-category branching exists anywhere in the provider or the frontend.
"""
from odoo import api, fields, models
from odoo.exceptions import ValidationError

FACET_TYPES = [
    ("enum", "Selection values"),
    ("enum_distinct", "Distinct stored values"),
    ("range", "Numeric range"),
    ("m2m", "Related records"),
    ("flag", "Boolean flag"),
]


class CatalogDeclarationMixin(models.AbstractModel):
    _name = "materials.catalog.declaration.mixin"
    _description = "Shared behaviour for catalog facet/column declarations"

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    category_id = fields.Many2one(
        "southbrook.tool.category", required=True, ondelete="cascade",
        index=True,
        help="Declaration applies to this category and its descendants.")
    field_name = fields.Char(
        required=True,
        help="Field name on product.template, e.g. x_southbrook_grit.")
    active = fields.Boolean(default=True)

    @api.constrains("field_name")
    def _check_field_exists(self):
        tmpl_fields = self.env["product.template"]._fields
        for rec in self:
            if rec.field_name not in tmpl_fields:
                raise ValidationError(
                    "%s is not a field on product.template." % rec.field_name)


class CatalogFacet(models.Model):
    _name = "materials.catalog.facet"
    _description = "Catalog Facet Declaration"
    _inherit = "materials.catalog.declaration.mixin"
    _order = "sequence, id"

    facet_type = fields.Selection(FACET_TYPES, required=True, default="enum")

    _cat_field_uniq = models.Constraint(
        "unique(category_id, field_name)",
        "A facet for this field already exists on this category.")


class CatalogColumn(models.Model):
    _name = "materials.catalog.column"
    _description = "Catalog Column Declaration"
    _inherit = "materials.catalog.declaration.mixin"
    _order = "sequence, id"

    align = fields.Selection(
        [("left", "Left"), ("right", "Right")], default="left")
    sortable = fields.Boolean(default=True)

    _cat_field_uniq = models.Constraint(
        "unique(category_id, field_name)",
        "A column for this field already exists on this category.")
```

Append to `models/__init__.py`:
```python
from . import catalog_declaration
```

Append to `security/ir.model.access.csv`:
```csv
access_materials_catalog_facet_user,materials.catalog.facet.user,model_materials_catalog_facet,base.group_user,1,0,0,0
access_materials_catalog_facet_manager,materials.catalog.facet.manager,model_materials_catalog_facet,base.group_system,1,1,1,1
access_materials_catalog_column_user,materials.catalog.column.user,model_materials_catalog_column,base.group_user,1,0,0,0
access_materials_catalog_column_manager,materials.catalog.column.manager,model_materials_catalog_column,base.group_system,1,1,1,1
```

**Note on the mixin — read before implementing.** A `models.Model` inheriting an `AbstractModel` while declaring its own `_name` is the standard Odoo pattern (`mail.thread` works this way). If this build rejects it — registry error, or the mixin's fields missing from the concrete models — **do not fight it**: delete `CatalogDeclarationMixin` and declare the five shared fields (`name`, `sequence`, `category_id`, `field_name`, `active`) plus the `_check_field_exists` constraint directly on each of the two models. The duplication is five lines and is preferable to a registry fight. Note the deviation in the task report.

- [ ] **Step 4: Run test to verify it passes**

Run: `odoo-bin -d <db> -u sb_materials_hardware --test-enable --stop-after-init --test-tags=sbk_mathw`
Expected: PASS, 6 tests.

- [ ] **Step 5: Commit**

```bash
git add addons/sb_materials_hardware
git commit -m "feat(materials-hardware): facet and column declaration models"
```

---

### Task 3: Provider contract, scope dispatch, honest degradation

**Files:**
- Create: `addons/sb_materials_hardware/models/catalog_provider.py`
- Create: `addons/sb_materials_hardware/models/tools_catalog_provider.py`
- Modify: `addons/sb_materials_hardware/models/__init__.py`
- Test: `addons/sb_materials_hardware/tests/test_provider_contract.py`

**Interfaces:**
- Consumes: nothing
- Produces:
  - `materials.catalog.provider` (AbstractModel) with `@api.model get_catalog(self, scope="tools", category_id=None, facets=None, search="", offset=0, limit=80)` returning a dict, and `SCOPES = {"tools": "tools.catalog.provider"}`
  - `tools.catalog.provider` (AbstractModel, `_inherit = "materials.catalog.provider"`) overriding `_build_payload(...)`
  - Payload keys: `ok`, `reason`, `scope`, `categories`, `facets`, `columns`, `rows`, `detail`, `total`, `provenance`

- [ ] **Step 1: Write the failing test**

`tests/test_provider_contract.py`:
```python
# SPDX-License-Identifier: LGPL-3.0-only
from odoo.tests.common import TransactionCase, tagged

REQUIRED_KEYS = {"ok", "scope", "categories", "facets", "columns",
                 "rows", "detail", "total", "provenance"}


@tagged("post_install", "-at_install", "southbrook", "sbk_mathw")
class TestProviderContract(TransactionCase):
    def setUp(self):
        super().setUp()
        self.Provider = self.env["materials.catalog.provider"]

    def test_payload_has_every_required_key(self):
        payload = self.Provider.get_catalog(scope="tools")
        self.assertTrue(payload["ok"])
        self.assertTrue(REQUIRED_KEYS.issubset(set(payload)))

    def test_unknown_scope_degrades(self):
        payload = self.Provider.get_catalog(scope="does_not_exist")
        self.assertFalse(payload["ok"])
        self.assertIn("reason", payload)

    def test_bad_category_degrades_not_raises(self):
        payload = self.Provider.get_catalog(scope="tools", category_id=-1)
        self.assertFalse(payload["ok"])
        self.assertIn("reason", payload)

    def test_provenance_is_a_string(self):
        payload = self.Provider.get_catalog(scope="tools")
        self.assertIsInstance(payload["provenance"], str)
        self.assertTrue(payload["provenance"])
```

Add `from . import test_provider_contract` to `tests/__init__.py`.

- [ ] **Step 2: Run test to verify it fails**

Run: `odoo-bin -d <db> -u sb_materials_hardware --test-enable --stop-after-init --test-tags=sbk_mathw`
Expected: FAIL — `KeyError: 'materials.catalog.provider'`.

- [ ] **Step 3: Write minimal implementation**

`models/catalog_provider.py`:
```python
# SPDX-License-Identifier: LGPL-3.0-only
"""Catalog contract: one shell, many providers.

The frontend calls get_catalog() and renders whatever comes back. It knows
nothing about hardware, tooling or sheet goods. A provider maps one data
domain onto the payload contract.

CONTRACT — the frontend reads exactly these keys:
    ok, reason, scope, categories, facets, columns, rows, detail, total,
    provenance
Rows are keyed on `product_id`. Renaming that key makes rows silently
unselectable in the UI.

Any failure degrades to {"ok": False, "reason": ...}. The catalog never
returns a 500 to the client action.
"""
import logging

from odoo import api, models

_logger = logging.getLogger(__name__)

SCOPES = {
    "tools": "tools.catalog.provider",
}


class MaterialsCatalogProvider(models.AbstractModel):
    _name = "materials.catalog.provider"
    _description = "Materials catalog provider contract"

    @api.model
    def get_catalog(self, scope="tools", category_id=None, facets=None,
                    search="", offset=0, limit=80):
        """Return one catalog payload. Never raises."""
        try:
            provider_name = SCOPES.get(scope)
            if not provider_name or provider_name not in self.env:
                return self._degrade("Unknown catalog scope: %s" % scope, scope)
            provider = self.env[provider_name]
            return provider._build_payload(
                scope=scope, category_id=category_id, facets=facets or {},
                search=search or "", offset=offset, limit=limit)
        except Exception as exc:  # noqa: BLE001 — degrade, never 500
            _logger.exception("Catalog payload build failed")
            return self._degrade(str(exc)[:200], scope)

    @api.model
    def _degrade(self, reason, scope):
        return {
            "ok": False, "reason": reason, "scope": scope,
            "categories": [], "facets": [], "columns": [], "rows": [],
            "detail": {}, "total": 0,
            "provenance": "Catalog unavailable.",
        }

    # ---- to be implemented by each provider -------------------------
    @api.model
    def _build_payload(self, scope, category_id, facets, search, offset, limit):
        raise NotImplementedError(
            "%s must implement _build_payload" % self._name)
```

`models/tools_catalog_provider.py`:
```python
# SPDX-License-Identifier: LGPL-3.0-only
"""Phase 1 provider: southbrook_mrp_kitchen_tools data.

This is the ONLY file that knows about x_southbrook_* fields or
southbrook.tool.category. Phase 2's hardware provider is a sibling file.
"""
from odoo import api, models

PROVENANCE = (
    "Read-only view of the tool and consumable master. Specs are optional — "
    "an absent value is shown as a dash, never as zero."
)


class ToolsCatalogProvider(models.AbstractModel):
    _name = "tools.catalog.provider"
    _inherit = "materials.catalog.provider"
    _description = "Tools and consumables catalog provider"

    @api.model
    def _build_payload(self, scope, category_id, facets, search, offset, limit):
        category = self.env["southbrook.tool.category"].browse(
            category_id) if category_id else None
        if category is not None and not category.exists():
            return self._degrade("Unknown category: %s" % category_id, scope)
        return {
            "ok": True,
            "scope": scope,
            "categories": [],
            "facets": [],
            "columns": [],
            "rows": [],
            "detail": {},
            "total": 0,
            "provenance": PROVENANCE,
        }
```

Append both to `models/__init__.py`:
```python
from . import catalog_provider
from . import tools_catalog_provider
```

- [ ] **Step 4: Run test to verify it passes**

Run: `odoo-bin -d <db> -u sb_materials_hardware --test-enable --stop-after-init --test-tags=sbk_mathw`
Expected: PASS, 10 tests.

- [ ] **Step 5: Commit**

```bash
git add addons/sb_materials_hardware
git commit -m "feat(materials-hardware): provider contract with honest degradation"
```

---

### Task 4: Category rail tree

**Files:**
- Modify: `addons/sb_materials_hardware/models/tools_catalog_provider.py`
- Test: `addons/sb_materials_hardware/tests/test_category_tree.py`

**Interfaces:**
- Consumes: `_build_payload` from Task 3
- Produces: `_categories(category)` returning a list of dicts, each `{"id": int, "name": str, "parent_id": int|False, "count": int, "has_children": bool}`. `count` is the number of `product.product` records whose template points at that category **or any descendant**.

- [ ] **Step 1: Write the failing test**

`tests/test_category_tree.py`:
```python
# SPDX-License-Identifier: LGPL-3.0-only
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "sbk_mathw")
class TestCategoryTree(TransactionCase):
    def setUp(self):
        super().setUp()
        self.Provider = self.env["materials.catalog.provider"]
        self.cat_screws = self.env.ref("southbrook_mrp_kitchen_tools.cat_screws")
        self.cat_conf = self.env.ref(
            "southbrook_mrp_kitchen_tools.cat_screw_confirmat")
        self.tmpl = self.env["product.template"].create({
            "name": "TEST Confirmat 7x50",
            "x_southbrook_tool_category_id": self.cat_conf.id,
        })

    def _cats(self):
        payload = self.Provider.get_catalog(scope="tools")
        return {c["id"]: c for c in payload["categories"]}

    def test_tree_includes_seeded_categories(self):
        cats = self._cats()
        self.assertIn(self.cat_screws.id, cats)
        self.assertIn(self.cat_conf.id, cats)

    def test_parent_link_is_reported(self):
        cats = self._cats()
        self.assertEqual(cats[self.cat_conf.id]["parent_id"], self.cat_screws.id)

    def test_has_children_flag(self):
        cats = self._cats()
        self.assertTrue(cats[self.cat_screws.id]["has_children"])
        self.assertFalse(cats[self.cat_conf.id]["has_children"])

    def test_count_rolls_up_to_ancestors(self):
        cats = self._cats()
        self.assertGreaterEqual(cats[self.cat_conf.id]["count"], 1)
        self.assertGreaterEqual(
            cats[self.cat_screws.id]["count"], cats[self.cat_conf.id]["count"])
```

Add `from . import test_category_tree` to `tests/__init__.py`.

- [ ] **Step 2: Run test to verify it fails**

Run: `odoo-bin -d <db> -u sb_materials_hardware --test-enable --stop-after-init --test-tags=sbk_mathw`
Expected: FAIL — `categories` is `[]`, so `assertIn` fails.

- [ ] **Step 3: Write minimal implementation**

In `tools_catalog_provider.py`, add the method and call it from `_build_payload` (replace `"categories": []` with `"categories": self._categories()`):

```python
    @api.model
    def _categories(self):
        """Rail tree with descendant-inclusive product counts.

        Counts are computed with ONE read_group over product.template rather
        than a query per category — 101 categories would otherwise mean 101
        queries on every catalog load.
        """
        Category = self.env["southbrook.tool.category"]
        cats = Category.search([])
        if not cats:
            return []

        # Odoo 17+ grouping API: _read_group returns a list of tuples,
        # (group_value, *aggregates). The old public read_group is gone.
        grouped = self.env["product.template"]._read_group(
            [("x_southbrook_tool_category_id", "in", cats.ids)],
            groupby=["x_southbrook_tool_category_id"],
            aggregates=["__count"],
        )
        direct = {cat.id: count for cat, count in grouped if cat}

        # Roll direct counts up through parent_path, so an ancestor reports
        # everything beneath it.
        rollup = dict.fromkeys(cats.ids, 0)
        by_id = {c.id: c for c in cats}
        for cat in cats:
            n = direct.get(cat.id, 0)
            if not n:
                continue
            for raw in (cat.parent_path or "").strip("/").split("/"):
                if raw and int(raw) in rollup:
                    rollup[int(raw)] += n

        child_ids = {c.parent_id.id for c in cats if c.parent_id}
        return [{
            "id": c.id,
            "name": c.name,
            "parent_id": c.parent_id.id or False,
            "count": rollup.get(c.id, 0),
            "has_children": c.id in child_ids,
        } for c in cats.sorted(lambda r: (r.complete_name or ""))]
```

Note `parent_path` includes the record's own id, so the loop above adds each category's own direct count to itself as well as to every ancestor — which is the intended roll-up.

- [ ] **Step 4: Run test to verify it passes**

Run: `odoo-bin -d <db> -u sb_materials_hardware --test-enable --stop-after-init --test-tags=sbk_mathw`
Expected: PASS, 14 tests.

- [ ] **Step 5: Commit**

```bash
git add addons/sb_materials_hardware
git commit -m "feat(materials-hardware): category rail with rolled-up counts"
```

---

### Task 5: Column resolution per category

**Files:**
- Modify: `addons/sb_materials_hardware/models/tools_catalog_provider.py`
- Test: `addons/sb_materials_hardware/tests/test_columns.py`

**Interfaces:**
- Consumes: `materials.catalog.column` (Task 2), `_build_payload` (Task 3)
- Produces: `_columns(category)` returning `[{"key": str, "label": str, "align": str, "sortable": bool}]`. Always begins with the generic columns `name` and `default_code`. Declarations from the selected category **and its ancestors** apply, nearest first; a descendant declaration for the same `field_name` overrides its ancestor's.

- [ ] **Step 1: Write the failing test**

`tests/test_columns.py`:
```python
# SPDX-License-Identifier: LGPL-3.0-only
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "sbk_mathw")
class TestColumns(TransactionCase):
    def setUp(self):
        super().setUp()
        self.Provider = self.env["materials.catalog.provider"]
        self.Column = self.env["materials.catalog.column"]
        self.parent = self.env.ref("southbrook_mrp_kitchen_tools.cat_screws")
        self.child = self.env.ref(
            "southbrook_mrp_kitchen_tools.cat_screw_confirmat")

    def _keys(self, category):
        payload = self.Provider.get_catalog(
            scope="tools", category_id=category.id)
        return [c["key"] for c in payload["columns"]]

    def test_generic_columns_always_present(self):
        keys = self._keys(self.child)
        self.assertEqual(keys[0], "name")
        self.assertIn("default_code", keys)

    def test_declared_column_appears(self):
        self.Column.create({
            "name": "Length (mm)", "category_id": self.parent.id,
            "field_name": "x_southbrook_screw_length_mm", "align": "right",
        })
        self.assertIn("x_southbrook_screw_length_mm", self._keys(self.parent))

    def test_ancestor_columns_inherited_by_child(self):
        self.Column.create({
            "name": "Length (mm)", "category_id": self.parent.id,
            "field_name": "x_southbrook_screw_length_mm",
        })
        self.assertIn("x_southbrook_screw_length_mm", self._keys(self.child))

    def test_child_declaration_overrides_ancestor_label(self):
        self.Column.create({
            "name": "Length (mm)", "category_id": self.parent.id,
            "field_name": "x_southbrook_screw_length_mm",
        })
        self.Column.create({
            "name": "Screw length", "category_id": self.child.id,
            "field_name": "x_southbrook_screw_length_mm",
        })
        payload = self.Provider.get_catalog(
            scope="tools", category_id=self.child.id)
        labels = {c["key"]: c["label"] for c in payload["columns"]}
        self.assertEqual(labels["x_southbrook_screw_length_mm"], "Screw length")
```

Add `from . import test_columns` to `tests/__init__.py`.

- [ ] **Step 2: Run test to verify it fails**

Run: `odoo-bin -d <db> -u sb_materials_hardware --test-enable --stop-after-init --test-tags=sbk_mathw`
Expected: FAIL — `columns` is `[]`.

- [ ] **Step 3: Write minimal implementation**

Add to `tools_catalog_provider.py`, and wire `"columns": self._columns(category)` into `_build_payload`:

```python
GENERIC_COLUMNS = [
    {"key": "name", "label": "Description", "align": "left", "sortable": True},
    {"key": "default_code", "label": "Reference", "align": "left",
     "sortable": True},
]


    @api.model
    def _ancestor_ids(self, category):
        """Category's own id plus every ancestor id, nearest LAST.

        parent_path is '/1/7/33/' — root first, self last.
        """
        if not category:
            return []
        return [int(x) for x in (category.parent_path or "").strip("/").split("/") if x]

    @api.model
    def _columns(self, category):
        cols = list(GENERIC_COLUMNS)
        if not category:
            return cols
        ids = self._ancestor_ids(category)
        if not ids:
            return cols
        declared = self.env["materials.catalog.column"].search(
            [("category_id", "in", ids)])
        # Nearest declaration wins: order by depth of its category in `ids`.
        depth = {cat_id: i for i, cat_id in enumerate(ids)}
        by_field = {}
        for dec in declared.sorted(
                lambda d: (depth.get(d.category_id.id, -1), d.sequence, d.id)):
            by_field[dec.field_name] = {
                "key": dec.field_name,
                "label": dec.name,
                "align": dec.align,
                "sortable": dec.sortable,
            }
        return cols + list(by_field.values())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `odoo-bin -d <db> -u sb_materials_hardware --test-enable --stop-after-init --test-tags=sbk_mathw`
Expected: PASS, 18 tests.

- [ ] **Step 5: Commit**

```bash
git add addons/sb_materials_hardware
git commit -m "feat(materials-hardware): per-category column resolution"
```

---

### Task 6: Facet building, including numeric-aware ordering

**Files:**
- Modify: `addons/sb_materials_hardware/models/catalog_provider.py` (helper only)
- Modify: `addons/sb_materials_hardware/models/tools_catalog_provider.py`
- Test: `addons/sb_materials_hardware/tests/test_facets.py`

**Interfaces:**
- Consumes: `materials.catalog.facet` (Task 2), `_ancestor_ids` (Task 5)
- Produces:
  - `materials.catalog.provider._numeric_prefix(value)` → `float` or `None`; parses a leading number from a string (`"120"` → 120.0, `"120 grit"` → 120.0, `"coarse"` → None)
  - `tools.catalog.provider._facets(category)` → `[{"key", "label", "type", "values": [{"value", "label", "count"}]}]`. For `range` facets, `values` is `[]` and the dict carries `"min"` and `"max"`.

- [ ] **Step 1: Write the failing test**

`tests/test_facets.py`:
```python
# SPDX-License-Identifier: LGPL-3.0-only
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "sbk_mathw")
class TestFacets(TransactionCase):
    def setUp(self):
        super().setUp()
        self.Provider = self.env["materials.catalog.provider"]
        self.Facet = self.env["materials.catalog.facet"]
        self.cat = self.env.ref("southbrook_mrp_kitchen_tools.cat_abr_disc")
        Tmpl = self.env["product.template"]
        for grit in ["80", "120", "220", "100"]:
            Tmpl.create({
                "name": "TEST Disc %s" % grit,
                "x_southbrook_tool_category_id": self.cat.id,
                "x_southbrook_grit": grit,
            })
        Tmpl.create({
            "name": "TEST Disc assorted",
            "x_southbrook_tool_category_id": self.cat.id,
            "x_southbrook_grit": "assorted",
        })

    def test_numeric_prefix_helper(self):
        f = self.Provider._numeric_prefix
        self.assertEqual(f("120"), 120.0)
        self.assertEqual(f("120 grit"), 120.0)
        self.assertIsNone(f("assorted"))
        self.assertIsNone(f(False))

    def _facet(self, key):
        payload = self.Provider.get_catalog(scope="tools", category_id=self.cat.id)
        return {f["key"]: f for f in payload["facets"]}[key]

    def test_enum_distinct_values_are_numerically_ordered(self):
        self.Facet.create({
            "name": "Grit", "category_id": self.cat.id,
            "field_name": "x_southbrook_grit", "facet_type": "enum_distinct",
        })
        values = [v["value"] for v in self._facet("x_southbrook_grit")["values"]]
        numeric = [v for v in values if v != "assorted"]
        self.assertEqual(numeric, ["80", "100", "120", "220"])

    def test_unparseable_value_sorts_last_and_is_kept(self):
        self.Facet.create({
            "name": "Grit", "category_id": self.cat.id,
            "field_name": "x_southbrook_grit", "facet_type": "enum_distinct",
        })
        values = [v["value"] for v in self._facet("x_southbrook_grit")["values"]]
        self.assertEqual(values[-1], "assorted")

    def test_enum_facet_uses_selection_labels(self):
        cat = self.env.ref("southbrook_mrp_kitchen_tools.cat_screws")
        self.env["product.template"].create({
            "name": "TEST Confirmat", "x_southbrook_tool_category_id": cat.id,
            "x_southbrook_thread_type": "confirmat",
        })
        self.Facet.create({
            "name": "Thread type", "category_id": cat.id,
            "field_name": "x_southbrook_thread_type", "facet_type": "enum",
        })
        payload = self.Provider.get_catalog(scope="tools", category_id=cat.id)
        facet = {f["key"]: f for f in payload["facets"]}["x_southbrook_thread_type"]
        labels = {v["value"]: v["label"] for v in facet["values"]}
        self.assertEqual(labels["confirmat"], "Confirmat")

    def test_range_facet_reports_min_and_max(self):
        cat = self.env.ref("southbrook_mrp_kitchen_tools.cat_screws")
        Tmpl = self.env["product.template"]
        for length in [30.0, 50.0, 70.0]:
            Tmpl.create({
                "name": "TEST Screw %s" % length,
                "x_southbrook_tool_category_id": cat.id,
                "x_southbrook_screw_length_mm": length,
            })
        self.Facet.create({
            "name": "Length", "category_id": cat.id,
            "field_name": "x_southbrook_screw_length_mm", "facet_type": "range",
        })
        payload = self.Provider.get_catalog(scope="tools", category_id=cat.id)
        facet = {f["key"]: f for f in payload["facets"]}[
            "x_southbrook_screw_length_mm"]
        self.assertEqual(facet["min"], 30.0)
        self.assertEqual(facet["max"], 70.0)
```

Add `from . import test_facets` to `tests/__init__.py`.

- [ ] **Step 2: Run test to verify it fails**

Run: `odoo-bin -d <db> -u sb_materials_hardware --test-enable --stop-after-init --test-tags=sbk_mathw`
Expected: FAIL — `_numeric_prefix` does not exist.

- [ ] **Step 3: Write minimal implementation**

Add to `catalog_provider.py` (inside `MaterialsCatalogProvider`):
```python
    @api.model
    def _numeric_prefix(self, value):
        """Leading number in a string, or None.

        Grit '120' must sort before '220' and after '80'. Values that carry
        no leading number ('assorted', 'coarse') return None, sort LAST, and
        keep their label — a chip that silently vanishes is worse than one
        that sorts oddly.
        """
        if value is None or value is False:
            return None
        text = str(value).strip()
        digits = ""
        for ch in text:
            if ch.isdigit() or (ch == "." and "." not in digits):
                digits += ch
            else:
                break
        if not digits or digits == ".":
            return None
        try:
            return float(digits)
        except ValueError:
            return None
```

Add to `tools_catalog_provider.py`, and wire `"facets": self._facets(category)` into `_build_payload`:
```python
    @api.model
    def _facets(self, category):
        if not category:
            return []
        ids = self._ancestor_ids(category)
        declared = self.env["materials.catalog.facet"].search(
            [("category_id", "in", ids)])
        if not declared:
            return []

        Tmpl = self.env["product.template"]
        tmpl_domain = [("x_southbrook_tool_category_id", "child_of", category.id)]
        out = []
        for dec in declared:
            field = Tmpl._fields.get(dec.field_name)
            if not field:
                continue
            entry = {"key": dec.field_name, "label": dec.name,
                     "type": dec.facet_type, "values": []}
            if dec.facet_type == "range":
                rows = Tmpl.search_read(
                    tmpl_domain + [(dec.field_name, "!=", False)],
                    [dec.field_name])
                nums = [r[dec.field_name] for r in rows
                        if isinstance(r[dec.field_name], (int, float))]
                entry["min"] = min(nums) if nums else 0.0
                entry["max"] = max(nums) if nums else 0.0
            elif dec.facet_type == "flag":
                entry["values"] = [{"value": True, "label": dec.name,
                                    "count": Tmpl.search_count(
                                        tmpl_domain + [(dec.field_name, "=", True)])}]
            else:
                # Odoo 17+ API: list of (group_value, count) tuples.
                grouped = Tmpl._read_group(
                    tmpl_domain + [(dec.field_name, "!=", False)],
                    groupby=[dec.field_name],
                    aggregates=["__count"],
                )
                raw = []
                for val, count in grouped:
                    if val is False or val is None:
                        continue
                    if hasattr(val, "id"):                 # m2o / m2m recordset
                        raw.append({"value": val.id, "label": val.display_name,
                                    "count": count})
                    else:
                        label = val
                        if field.type == "selection":
                            label = dict(
                                field._description_selection(self.env)
                            ).get(val, val)
                        raw.append({"value": val, "label": label,
                                    "count": count})
                entry["values"] = self._order_values(raw)
            out.append(entry)
        return out

    @api.model
    def _order_values(self, raw):
        """Numeric-aware ordering; unparseable values keep their label and
        sort last."""
        numbered, unnumbered = [], []
        for item in raw:
            n = self._numeric_prefix(item["value"])
            (numbered if n is not None else unnumbered).append((n, item))
        numbered.sort(key=lambda pair: pair[0])
        unnumbered.sort(key=lambda pair: str(pair[1]["label"]))
        return [item for _n, item in numbered] + [item for _n, item in unnumbered]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `odoo-bin -d <db> -u sb_materials_hardware --test-enable --stop-after-init --test-tags=sbk_mathw`
Expected: PASS, 23 tests.

- [ ] **Step 5: Commit**

```bash
git add addons/sb_materials_hardware
git commit -m "feat(materials-hardware): facet building with numeric-aware ordering"
```

---

### Task 7: Facet filtering — OR within a facet, AND across facets

**Files:**
- Modify: `addons/sb_materials_hardware/models/tools_catalog_provider.py`
- Test: `addons/sb_materials_hardware/tests/test_filtering.py`

**Interfaces:**
- Consumes: `_facets` (Task 6)
- Produces: `_facet_domain(facets)` → an Odoo domain list. Input shape: `{"x_southbrook_thread_type": ["confirmat", "euro"], "x_southbrook_screw_length_mm": {"min": 30, "max": 60}}`

- [ ] **Step 1: Write the failing test**

`tests/test_filtering.py`:
```python
# SPDX-License-Identifier: LGPL-3.0-only
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "sbk_mathw")
class TestFiltering(TransactionCase):
    def setUp(self):
        super().setUp()
        self.Provider = self.env["materials.catalog.provider"]
        self.cat = self.env.ref("southbrook_mrp_kitchen_tools.cat_screws")
        Tmpl = self.env["product.template"]
        self.confirmat = Tmpl.create({
            "name": "TEST Confirmat 7x50", "x_southbrook_tool_category_id": self.cat.id,
            "x_southbrook_thread_type": "confirmat",
            "x_southbrook_screw_length_mm": 50.0,
        })
        self.euro = Tmpl.create({
            "name": "TEST Euro 6.3x13", "x_southbrook_tool_category_id": self.cat.id,
            "x_southbrook_thread_type": "euro",
            "x_southbrook_screw_length_mm": 13.0,
        })
        self.coarse = Tmpl.create({
            "name": "TEST Coarse 4x40", "x_southbrook_tool_category_id": self.cat.id,
            "x_southbrook_thread_type": "coarse",
            "x_southbrook_screw_length_mm": 40.0,
        })

    def _matching(self, facets):
        """Apply the facet domain directly to product.template.

        This task is tested against the DOMAIN BUILDER, not against rows —
        rows arrive in Task 8. Keeping the test at this level is what makes
        Task 7 independently green.
        """
        domain = self.env["tools.catalog.provider"]._facet_domain(facets)
        base = [("x_southbrook_tool_category_id", "child_of", self.cat.id)]
        return set(self.env["product.template"].search(base + domain).mapped("name"))

    def test_single_value_filters(self):
        names = self._matching({"x_southbrook_thread_type": ["confirmat"]})
        self.assertIn("TEST Confirmat 7x50", names)
        self.assertNotIn("TEST Euro 6.3x13", names)

    def test_multi_select_within_facet_is_or(self):
        names = self._matching({"x_southbrook_thread_type": ["confirmat", "euro"]})
        self.assertIn("TEST Confirmat 7x50", names)
        self.assertIn("TEST Euro 6.3x13", names)
        self.assertNotIn("TEST Coarse 4x40", names)

    def test_across_facets_is_and(self):
        names = self._matching({
            "x_southbrook_thread_type": ["confirmat", "euro"],
            "x_southbrook_screw_length_mm": {"min": 40.0, "max": 60.0},
        })
        self.assertIn("TEST Confirmat 7x50", names)
        self.assertNotIn("TEST Euro 6.3x13", names)

    def test_empty_facets_returns_everything_in_category(self):
        names = self._matching({})
        self.assertTrue({"TEST Confirmat 7x50", "TEST Euro 6.3x13",
                         "TEST Coarse 4x40"}.issubset(names))

    def test_unknown_field_is_ignored_not_crashed(self):
        names = self._matching({"x_southbrook_not_a_field": ["anything"]})
        self.assertIn("TEST Confirmat 7x50", names)
```

Add `from . import test_filtering` to `tests/__init__.py`.

- [ ] **Step 2: Run test to verify it fails**

Run: `odoo-bin -d <db> -u sb_materials_hardware --test-enable --stop-after-init --test-tags=sbk_mathw`
Expected: FAIL — `rows` is empty (rows arrive in Task 8; this task's assertions on filtering fail first).

- [ ] **Step 3: Write minimal implementation**

Add to `tools_catalog_provider.py`:
```python
    @api.model
    def _facet_domain(self, facets):
        """Domain fragment for the selected facet values.

        Within one facet, selected values are OR'ed. Across facets, the
        fragments are AND'ed (Odoo domains are implicitly AND).
        """
        domain = []
        for field_name, selection in (facets or {}).items():
            if field_name not in self.env["product.template"]._fields:
                continue
            if isinstance(selection, dict):          # range
                low, high = selection.get("min"), selection.get("max")
                if low is not None:
                    domain.append((field_name, ">=", low))
                if high is not None:
                    domain.append((field_name, "<=", high))
                continue
            values = [v for v in (selection or []) if v not in (None, "")]
            if not values:
                continue
            if len(values) == 1:
                domain.append((field_name, "=", values[0]))
            else:
                domain += ["|"] * (len(values) - 1)
                domain += [(field_name, "=", v) for v in values]
        return domain
```

Prefix-notation reminder: `n` OR'ed leaves need `n - 1` `"|"` tokens **before** them.
Two values produce `["|", (f, "=", a), (f, "=", b)]`.

- [ ] **Step 4: Run test to verify it passes**

Run: `odoo-bin -d <db> -u sb_materials_hardware --test-enable --stop-after-init --test-tags=sbk_mathw`
Expected: PASS, 28 tests. This task is green on its own — the tests exercise
`_facet_domain` directly and do not depend on Task 8.

- [ ] **Step 5: Commit**

```bash
git add addons/sb_materials_hardware
git commit -m "feat(materials-hardware): facet domain — OR within, AND across"
```

---

### Task 8: Rows, search, pagination

**Files:**
- Modify: `addons/sb_materials_hardware/models/tools_catalog_provider.py`
- Test: `addons/sb_materials_hardware/tests/test_rows.py`

**Interfaces:**
- Consumes: `_columns` (Task 5), `_facet_domain` (Task 7)
- Produces: `_rows(category, facets, search, offset, limit, columns)` → `(rows, total)` where each row is `{"product_id": int, "name": str, "default_code": str|False, <column keys>...}`

- [ ] **Step 1: Write the failing test**

`tests/test_rows.py`:
```python
# SPDX-License-Identifier: LGPL-3.0-only
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "sbk_mathw")
class TestRows(TransactionCase):
    def setUp(self):
        super().setUp()
        self.Provider = self.env["materials.catalog.provider"]
        self.cat = self.env.ref("southbrook_mrp_kitchen_tools.cat_screws")
        self.env["materials.catalog.column"].create({
            "name": "Length (mm)", "category_id": self.cat.id,
            "field_name": "x_southbrook_screw_length_mm", "align": "right",
        })
        Tmpl = self.env["product.template"]
        self.a = Tmpl.create({
            "name": "TEST Confirmat 7x50", "default_code": "SB-CONF-750",
            "x_southbrook_tool_category_id": self.cat.id,
            "x_southbrook_screw_length_mm": 50.0,
        })
        self.b = Tmpl.create({
            "name": "TEST Pocket screw", "default_code": "SB-PKT-125",
            "x_southbrook_tool_category_id": self.cat.id,
        })

    def _payload(self, **kw):
        return self.Provider.get_catalog(
            scope="tools", category_id=self.cat.id, **kw)

    def test_rows_are_keyed_on_product_id(self):
        rows = self._payload()["rows"]
        self.assertTrue(rows)
        self.assertIn("product_id", rows[0])

    def test_row_carries_declared_column_value(self):
        rows = {r["name"]: r for r in self._payload()["rows"]}
        self.assertEqual(
            rows["TEST Confirmat 7x50"]["x_southbrook_screw_length_mm"], 50.0)

    def test_absent_spec_is_none_not_zero(self):
        rows = {r["name"]: r for r in self._payload()["rows"]}
        self.assertIsNone(rows["TEST Pocket screw"]["x_southbrook_screw_length_mm"])

    def test_search_matches_name_and_reference(self):
        self.assertIn("TEST Confirmat 7x50",
                      {r["name"] for r in self._payload(search="confirmat")["rows"]})
        self.assertIn("TEST Pocket screw",
                      {r["name"] for r in self._payload(search="SB-PKT")["rows"]})

    def test_total_is_count_before_pagination(self):
        payload = self._payload(limit=1)
        self.assertEqual(len(payload["rows"]), 1)
        self.assertGreaterEqual(payload["total"], 2)
```

Add `from . import test_rows` to `tests/__init__.py`.

- [ ] **Step 2: Run test to verify it fails**

Run: `odoo-bin -d <db> -u sb_materials_hardware --test-enable --stop-after-init --test-tags=sbk_mathw`
Expected: FAIL — `rows` is empty.

- [ ] **Step 3: Write minimal implementation**

Add to `tools_catalog_provider.py`, and wire into `_build_payload`:
```python
        columns = self._columns(category)
        rows, total = self._rows(category, facets, search, offset, limit, columns)
```
then return `"columns": columns, "rows": rows, "total": total`.

```python
    @api.model
    def _rows(self, category, facets, search, offset, limit, columns):
        """One row per variant.

        Spec fields live on product.template, so templates are read ONCE in
        a batch and joined in Python — never one read per row.
        """
        Product = self.env["product.product"]
        domain = [("product_tmpl_id.x_southbrook_tool_category_id",
                   "child_of", category.id)] if category else []
        for leaf in self._facet_domain(facets):
            domain.append(("product_tmpl_id.%s" % leaf[0], leaf[1], leaf[2])
                          if isinstance(leaf, tuple) else leaf)
        if search:
            domain += ["|", ("name", "ilike", search),
                       ("default_code", "ilike", search)]

        total = Product.search_count(domain)
        products = Product.search(domain, offset=offset, limit=limit,
                                  order="default_code, name")
        if not products:
            return [], total

        spec_keys = [c["key"] for c in columns
                     if c["key"] not in ("name", "default_code")]
        tmpl_data = {}
        if spec_keys:
            for rec in products.mapped("product_tmpl_id").read(spec_keys):
                tmpl_data[rec["id"]] = rec

        rows = []
        for product in products:
            row = {
                "product_id": product.id,
                "name": product.display_name,
                "default_code": product.default_code or False,
            }
            specs = tmpl_data.get(product.product_tmpl_id.id, {})
            for key in spec_keys:
                value = specs.get(key)
                # False from an unset Char/Float is "absent", not zero.
                row[key] = None if value in (False, None, "") else value
            rows.append(row)
        return rows, total
```

**Note on the domain rewrite:** `_facet_domain` returns leaves naming `product.template` fields. Because rows are `product.product`, each leaf field is prefixed with `product_tmpl_id.`; operator strings (`"|"`) pass through untouched.

- [ ] **Step 4: Run test to verify it passes**

Run: `odoo-bin -d <db> -u sb_materials_hardware --test-enable --stop-after-init --test-tags=sbk_mathw`
Expected: PASS — Task 7 and Task 8 tests both green, 32 tests total.

- [ ] **Step 5: Commit**

```bash
git add addons/sb_materials_hardware
git commit -m "feat(materials-hardware): rows, search and pagination with batched template reads"
```

---

### Task 9: Detail payload

**Files:**
- Modify: `addons/sb_materials_hardware/models/tools_catalog_provider.py`
- Test: `addons/sb_materials_hardware/tests/test_detail.py`

**Interfaces:**
- Consumes: `_columns` (Task 5)
- Produces: `get_detail(product_id)` on `materials.catalog.provider`, dispatching to the provider, returning `{"ok": bool, "title", "subtitle", "specs": [{"label", "value"}], "engineering": [{"label", "value"}], "badges": [str]}`

- [ ] **Step 1: Write the failing test**

`tests/test_detail.py`:
```python
# SPDX-License-Identifier: LGPL-3.0-only
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "sbk_mathw")
class TestDetail(TransactionCase):
    def setUp(self):
        super().setUp()
        self.Provider = self.env["materials.catalog.provider"]
        self.cat = self.env.ref("southbrook_mrp_kitchen_tools.cat_adhesives")
        self.env["materials.catalog.column"].create({
            "name": "Open time (min)", "category_id": self.cat.id,
            "field_name": "x_southbrook_open_time_min", "align": "right",
        })
        self.tmpl = self.env["product.template"].create({
            "name": "TEST PVA Type II",
            "x_southbrook_tool_category_id": self.cat.id,
            "x_southbrook_open_time_min": 8.0,
            "x_southbrook_hazardous": True,
            "x_southbrook_min_stock_qty": 4.0,
        })
        self.product = self.tmpl.product_variant_ids[0]

    def test_detail_has_title_and_specs(self):
        detail = self.Provider.get_detail(self.product.id)
        self.assertTrue(detail["ok"])
        self.assertIn("TEST PVA Type II", detail["title"])
        labels = {s["label"]: s["value"] for s in detail["specs"]}
        self.assertEqual(labels["Open time (min)"], 8.0)

    def test_hazard_badge_present(self):
        detail = self.Provider.get_detail(self.product.id)
        self.assertIn("Hazardous", detail["badges"])

    def test_engineering_rail_includes_min_stock(self):
        detail = self.Provider.get_detail(self.product.id)
        labels = {e["label"]: e["value"] for e in detail["engineering"]}
        self.assertEqual(labels["Min stock"], 4.0)

    def test_unknown_product_degrades(self):
        detail = self.Provider.get_detail(-1)
        self.assertFalse(detail["ok"])
```

Add `from . import test_detail` to `tests/__init__.py`.

- [ ] **Step 2: Run test to verify it fails**

Run: `odoo-bin -d <db> -u sb_materials_hardware --test-enable --stop-after-init --test-tags=sbk_mathw`
Expected: FAIL — `get_detail` does not exist.

- [ ] **Step 3: Write minimal implementation**

Add to `catalog_provider.py`:
```python
    @api.model
    def get_detail(self, product_id, scope="tools"):
        try:
            provider_name = SCOPES.get(scope)
            if not provider_name or provider_name not in self.env:
                return {"ok": False, "reason": "Unknown scope", "specs": [],
                        "engineering": [], "badges": [], "title": "",
                        "subtitle": ""}
            return self.env[provider_name]._build_detail(product_id)
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Catalog detail build failed")
            return {"ok": False, "reason": str(exc)[:200], "specs": [],
                    "engineering": [], "badges": [], "title": "",
                    "subtitle": ""}
```

Add to `tools_catalog_provider.py`:
```python
BADGE_FIELDS = [
    ("x_southbrook_hazardous", "Hazardous"),
    ("x_southbrook_flammable", "Flammable"),
    ("x_southbrook_msds_required", "MSDS required"),
    ("x_southbrook_requires_ventilation", "Ventilation required"),
    ("x_southbrook_expiry_required", "Expiry tracked"),
]

ENGINEERING_FIELDS = [
    ("x_southbrook_preferred_vendor_id", "Preferred vendor"),
    ("x_southbrook_vendor_sku", "Vendor SKU"),
    ("x_southbrook_issue_uom_id", "Issue UoM"),
    ("x_southbrook_min_stock_qty", "Min stock"),
    ("x_southbrook_max_stock_qty", "Max stock"),
    ("x_southbrook_reorder_multiple", "Reorder multiple"),
    ("x_southbrook_estimated_life_qty", "Estimated life"),
    ("x_southbrook_estimated_life_unit", "Life unit"),
    ("x_southbrook_tool_lifecycle_state", "Lifecycle"),
]


    @api.model
    def _build_detail(self, product_id):
        product = self.env["product.product"].browse(product_id)
        if not product.exists():
            return {"ok": False, "reason": "Unknown product", "specs": [],
                    "engineering": [], "badges": [], "title": "",
                    "subtitle": ""}
        tmpl = product.product_tmpl_id
        category = tmpl.x_southbrook_tool_category_id
        columns = self._columns(category)

        specs = []
        for col in columns:
            if col["key"] in ("name", "default_code"):
                continue
            raw = tmpl[col["key"]] if col["key"] in tmpl._fields else False
            specs.append({"label": col["label"],
                          "value": None if raw in (False, None, "") else raw})

        engineering = []
        for field_name, label in ENGINEERING_FIELDS:
            if field_name not in tmpl._fields:
                continue
            raw = tmpl[field_name]
            if hasattr(raw, "display_name"):
                raw = raw.display_name if raw else None
            engineering.append(
                {"label": label,
                 "value": None if raw in (False, None, "") else raw})

        badges = [label for field_name, label in BADGE_FIELDS
                  if field_name in tmpl._fields and tmpl[field_name]]

        return {
            "ok": True,
            "title": product.display_name,
            "subtitle": category.complete_name if category else "",
            "specs": specs,
            "engineering": engineering,
            "badges": badges,
        }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `odoo-bin -d <db> -u sb_materials_hardware --test-enable --stop-after-init --test-tags=sbk_mathw`
Expected: PASS, 36 tests.

- [ ] **Step 5: Commit**

```bash
git add addons/sb_materials_hardware
git commit -m "feat(materials-hardware): detail payload with engineering rail and badges"
```

---

### Task 10: Access safety — the provider never elevates

**Files:**
- Test only: `addons/sb_materials_hardware/tests/test_access.py`
- Modify: `addons/sb_materials_hardware/models/tools_catalog_provider.py` only if the test fails

**Interfaces:**
- Consumes: everything above
- Produces: no new interface; a standing guarantee that catalog reads run as the calling user

- [ ] **Step 1: Write the failing test**

`tests/test_access.py`:
```python
# SPDX-License-Identifier: LGPL-3.0-only
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "sbk_mathw")
class TestAccess(TransactionCase):
    def setUp(self):
        super().setUp()
        self.cat = self.env.ref("southbrook_mrp_kitchen_tools.cat_screws")
        self.env["product.template"].create({
            "name": "TEST Visible screw",
            "x_southbrook_tool_category_id": self.cat.id,
        })
        self.plain_user = self.env["res.users"].create({
            "name": "Catalog Reader",
            "login": "catalog_reader_test",
            "group_ids": [(6, 0, [self.env.ref("base.group_user").id])],
        })

    def test_internal_user_can_read_catalog(self):
        payload = self.env["materials.catalog.provider"].with_user(
            self.plain_user).get_catalog(scope="tools", category_id=self.cat.id)
        self.assertTrue(payload["ok"])
        self.assertIn("TEST Visible screw",
                      {r["name"] for r in payload["rows"]})

    def test_provider_source_contains_no_sudo(self):
        """The catalog must never elevate to read records."""
        import inspect
        from odoo.addons.sb_materials_hardware.models import (
            tools_catalog_provider, catalog_provider)
        for module in (tools_catalog_provider, catalog_provider):
            source = inspect.getsource(module)
            self.assertNotIn(".sudo()", source)
```

Add `from . import test_access` to `tests/__init__.py`.

**Note:** Odoo 19 renamed `res.users.groups_id` to `group_ids`. The test above uses the v19 name. If this build still carries the old name, the create will raise `ValueError: Invalid field 'group_ids'` — in that case use `groups_id` and note the deviation in the task report.

- [ ] **Step 2: Run test to verify it fails or passes**

Run: `odoo-bin -d <db> -u sb_materials_hardware --test-enable --stop-after-init --test-tags=sbk_mathw`
Expected: PASS if Tasks 3–9 were written without `sudo()`. If it FAILS, remove the elevation rather than relaxing the test.

- [ ] **Step 3: Implementation**

No code change if green. If red, delete every `.sudo()` from the provider files and re-run.

- [ ] **Step 4: Run test to verify it passes**

Run: `odoo-bin -d <db> -u sb_materials_hardware --test-enable --stop-after-init --test-tags=sbk_mathw`
Expected: PASS, 38 tests.

- [ ] **Step 5: Commit**

```bash
git add addons/sb_materials_hardware
git commit -m "test(materials-hardware): assert the catalog never elevates"
```

---

### Task 11: Facet and column seed data for sections A–E

**Files:**
- Create: `addons/sb_materials_hardware/data/catalog_declarations.xml`
- Modify: `addons/sb_materials_hardware/__manifest__.py` (add the data file **after** `catalog_action.xml`)
- Test: extend `addons/sb_materials_hardware/tests/test_declarations.py`

**Interfaces:**
- Consumes: `materials.catalog.facet`, `materials.catalog.column` (Task 2)
- Produces: seeded declarations for Screws, Fasteners, Saw Blades, CNC Router Bits, Drill and Boring Bits, Adhesives, Abrasives, Finishing

- [ ] **Step 1: Write the failing test**

Append to `tests/test_declarations.py`:
```python
    def test_seeded_declarations_exist_for_screws(self):
        facets = self.env["materials.catalog.facet"].search([
            ("category_id", "=",
             self.env.ref("southbrook_mrp_kitchen_tools.cat_screws").id)])
        fields_declared = set(facets.mapped("field_name"))
        self.assertIn("x_southbrook_thread_type", fields_declared)
        self.assertIn("x_southbrook_head_type", fields_declared)
        self.assertIn("x_southbrook_drive_type", fields_declared)
        self.assertIn("x_southbrook_compatible_material_ids", fields_declared)

    def test_seeded_declarations_exist_for_adhesives(self):
        facets = self.env["materials.catalog.facet"].search([
            ("category_id", "=",
             self.env.ref("southbrook_mrp_kitchen_tools.cat_adhesives").id)])
        self.assertIn("x_southbrook_glue_type", set(facets.mapped("field_name")))

    def test_every_seeded_declaration_names_a_real_field(self):
        tmpl_fields = self.env["product.template"]._fields
        for model in ("materials.catalog.facet", "materials.catalog.column"):
            for rec in self.env[model].search([]):
                self.assertIn(rec.field_name, tmpl_fields,
                              "%s declares missing field %s" % (model, rec.field_name))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `odoo-bin -d <db> -u sb_materials_hardware --test-enable --stop-after-init --test-tags=sbk_mathw`
Expected: FAIL — no seeded declarations.

- [ ] **Step 3: Write minimal implementation**

`data/catalog_declarations.xml` — the Screws and Adhesives branches in full; follow the identical pattern for Fasteners, Saw Blades, CNC Router Bits, Drill and Boring Bits, Abrasives and Finishing using the field lists in spec §4.2 and §4.3.

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
  <data noupdate="1">

    <!-- ============ SCREWS ============ -->
    <record id="facet_screws_thread" model="materials.catalog.facet">
      <field name="name">Thread type</field>
      <field name="sequence">10</field>
      <field name="category_id" ref="southbrook_mrp_kitchen_tools.cat_screws"/>
      <field name="field_name">x_southbrook_thread_type</field>
      <field name="facet_type">enum</field>
    </record>
    <record id="facet_screws_head" model="materials.catalog.facet">
      <field name="name">Head type</field>
      <field name="sequence">20</field>
      <field name="category_id" ref="southbrook_mrp_kitchen_tools.cat_screws"/>
      <field name="field_name">x_southbrook_head_type</field>
      <field name="facet_type">enum</field>
    </record>
    <record id="facet_screws_drive" model="materials.catalog.facet">
      <field name="name">Drive</field>
      <field name="sequence">30</field>
      <field name="category_id" ref="southbrook_mrp_kitchen_tools.cat_screws"/>
      <field name="field_name">x_southbrook_drive_type</field>
      <field name="facet_type">enum</field>
    </record>
    <record id="facet_screws_size" model="materials.catalog.facet">
      <field name="name">Size</field>
      <field name="sequence">40</field>
      <field name="category_id" ref="southbrook_mrp_kitchen_tools.cat_screws"/>
      <field name="field_name">x_southbrook_screw_size</field>
      <field name="facet_type">enum_distinct</field>
    </record>
    <record id="facet_screws_length" model="materials.catalog.facet">
      <field name="name">Length (mm)</field>
      <field name="sequence">50</field>
      <field name="category_id" ref="southbrook_mrp_kitchen_tools.cat_screws"/>
      <field name="field_name">x_southbrook_screw_length_mm</field>
      <field name="facet_type">range</field>
    </record>
    <record id="facet_screws_substrate" model="materials.catalog.facet">
      <field name="name">Substrate</field>
      <field name="sequence">60</field>
      <field name="category_id" ref="southbrook_mrp_kitchen_tools.cat_screws"/>
      <field name="field_name">x_southbrook_compatible_material_ids</field>
      <field name="facet_type">m2m</field>
    </record>

    <record id="col_screws_size" model="materials.catalog.column">
      <field name="name">Size</field>
      <field name="sequence">10</field>
      <field name="category_id" ref="southbrook_mrp_kitchen_tools.cat_screws"/>
      <field name="field_name">x_southbrook_screw_size</field>
    </record>
    <record id="col_screws_length" model="materials.catalog.column">
      <field name="name">Length (mm)</field>
      <field name="sequence">20</field>
      <field name="category_id" ref="southbrook_mrp_kitchen_tools.cat_screws"/>
      <field name="field_name">x_southbrook_screw_length_mm</field>
      <field name="align">right</field>
    </record>
    <record id="col_screws_head" model="materials.catalog.column">
      <field name="name">Head</field>
      <field name="sequence">30</field>
      <field name="category_id" ref="southbrook_mrp_kitchen_tools.cat_screws"/>
      <field name="field_name">x_southbrook_head_type</field>
    </record>
    <record id="col_screws_drive" model="materials.catalog.column">
      <field name="name">Drive</field>
      <field name="sequence">40</field>
      <field name="category_id" ref="southbrook_mrp_kitchen_tools.cat_screws"/>
      <field name="field_name">x_southbrook_drive_type</field>
    </record>
    <record id="col_screws_thread" model="materials.catalog.column">
      <field name="name">Thread</field>
      <field name="sequence">50</field>
      <field name="category_id" ref="southbrook_mrp_kitchen_tools.cat_screws"/>
      <field name="field_name">x_southbrook_thread_type</field>
    </record>

    <!-- ============ ADHESIVES ============ -->
    <record id="facet_adh_type" model="materials.catalog.facet">
      <field name="name">Glue type</field>
      <field name="sequence">10</field>
      <field name="category_id" ref="southbrook_mrp_kitchen_tools.cat_adhesives"/>
      <field name="field_name">x_southbrook_glue_type</field>
      <field name="facet_type">enum</field>
    </record>
    <record id="facet_adh_open" model="materials.catalog.facet">
      <field name="name">Open time (min)</field>
      <field name="sequence">20</field>
      <field name="category_id" ref="southbrook_mrp_kitchen_tools.cat_adhesives"/>
      <field name="field_name">x_southbrook_open_time_min</field>
      <field name="facet_type">range</field>
    </record>
    <record id="facet_adh_cure" model="materials.catalog.facet">
      <field name="name">Cure time (min)</field>
      <field name="sequence">30</field>
      <field name="category_id" ref="southbrook_mrp_kitchen_tools.cat_adhesives"/>
      <field name="field_name">x_southbrook_cure_time_min</field>
      <field name="facet_type">range</field>
    </record>
    <record id="facet_adh_hazard" model="materials.catalog.facet">
      <field name="name">Hazardous</field>
      <field name="sequence">40</field>
      <field name="category_id" ref="southbrook_mrp_kitchen_tools.cat_adhesives"/>
      <field name="field_name">x_southbrook_hazardous</field>
      <field name="facet_type">flag</field>
    </record>

    <record id="col_adh_type" model="materials.catalog.column">
      <field name="name">Glue type</field>
      <field name="sequence">10</field>
      <field name="category_id" ref="southbrook_mrp_kitchen_tools.cat_adhesives"/>
      <field name="field_name">x_southbrook_glue_type</field>
    </record>
    <record id="col_adh_open" model="materials.catalog.column">
      <field name="name">Open time (min)</field>
      <field name="sequence">20</field>
      <field name="category_id" ref="southbrook_mrp_kitchen_tools.cat_adhesives"/>
      <field name="field_name">x_southbrook_open_time_min</field>
      <field name="align">right</field>
    </record>
    <record id="col_adh_cure" model="materials.catalog.column">
      <field name="name">Cure time (min)</field>
      <field name="sequence">30</field>
      <field name="category_id" ref="southbrook_mrp_kitchen_tools.cat_adhesives"/>
      <field name="field_name">x_southbrook_cure_time_min</field>
      <field name="align">right</field>
    </record>
    <record id="col_adh_shelf" model="materials.catalog.column">
      <field name="name">Shelf life (days)</field>
      <field name="sequence">40</field>
      <field name="category_id" ref="southbrook_mrp_kitchen_tools.cat_adhesives"/>
      <field name="field_name">x_southbrook_shelf_life_days</field>
      <field name="align">right</field>
    </record>

  </data>
</odoo>
```

**The remaining records, in full.** Each uses the identical XML shape as the two branches
above — a `materials.catalog.facet` or `materials.catalog.column` record whose `category_id`
is `ref="southbrook_mrp_kitchen_tools.<category>"`. Every value you need is in these tables;
nothing is left to judgement. Give each record an `id` of `facet_<cat>_<short>` or
`col_<cat>_<short>`, and sequence in tens in the order listed.

**Facets:**

| Category ref | `field_name` | `facet_type` | `name` |
|---|---|---|---|
| `cat_fasteners` | `x_southbrook_compatible_material_ids` | m2m | Substrate |
| `cat_fasteners` | `x_southbrook_screw_length_mm` | range | Length (mm) |
| `cat_saw_blades` | `x_southbrook_blade_diameter_mm` | range | Blade diameter (mm) |
| `cat_saw_blades` | `x_southbrook_tooth_count` | range | Teeth |
| `cat_saw_blades` | `x_southbrook_bore_size_mm` | enum_distinct | Bore (mm) |
| `cat_saw_blades` | `x_southbrook_material_grade` | enum_distinct | Grade |
| `cat_saw_blades` | `x_southbrook_coating` | enum_distinct | Coating |
| `cat_saw_blades` | `x_southbrook_compatible_material_ids` | m2m | Substrate |
| `cat_cnc_bits` | `x_southbrook_cutting_diameter_mm` | range | Cutting diameter (mm) |
| `cat_cnc_bits` | `x_southbrook_shank_diameter_mm` | enum_distinct | Shank (mm) |
| `cat_cnc_bits` | `x_southbrook_cutting_length_mm` | range | Cut length (mm) |
| `cat_cnc_bits` | `x_southbrook_coating` | enum_distinct | Coating |
| `cat_cnc_bits` | `x_southbrook_compatible_material_ids` | m2m | Substrate |
| `cat_drill_bits` | `x_southbrook_cutting_diameter_mm` | range | Diameter (mm) |
| `cat_drill_bits` | `x_southbrook_shank_diameter_mm` | enum_distinct | Shank (mm) |
| `cat_drill_bits` | `x_southbrook_overall_length_mm` | range | Overall length (mm) |
| `cat_drill_bits` | `x_southbrook_material_grade` | enum_distinct | Grade |
| `cat_abrasives` | `x_southbrook_grit` | enum_distinct | Grit |
| `cat_abrasives` | `x_southbrook_compatible_material_ids` | m2m | Substrate |
| `cat_finishing` | `x_southbrook_hazardous` | flag | Hazardous |
| `cat_finishing` | `x_southbrook_flammable` | flag | Flammable |
| `cat_finishing` | `x_southbrook_requires_ventilation` | flag | Needs ventilation |
| `cat_finishing` | `x_southbrook_shelf_life_days` | range | Shelf life (days) |

**Columns** (`align` is `right` for every numeric field, `left` otherwise):

| Category ref | `field_name` | `name` | `align` |
|---|---|---|---|
| `cat_fasteners` | `x_southbrook_screw_size` | Size | left |
| `cat_fasteners` | `x_southbrook_screw_length_mm` | Length (mm) | right |
| `cat_saw_blades` | `x_southbrook_blade_diameter_mm` | Diameter (mm) | right |
| `cat_saw_blades` | `x_southbrook_tooth_count` | Teeth | right |
| `cat_saw_blades` | `x_southbrook_kerf_width_mm` | Kerf (mm) | right |
| `cat_saw_blades` | `x_southbrook_bore_size_mm` | Bore (mm) | right |
| `cat_saw_blades` | `x_southbrook_material_grade` | Grade | left |
| `cat_cnc_bits` | `x_southbrook_cutting_diameter_mm` | Cutting Ø (mm) | right |
| `cat_cnc_bits` | `x_southbrook_shank_diameter_mm` | Shank (mm) | right |
| `cat_cnc_bits` | `x_southbrook_cutting_length_mm` | Cut length (mm) | right |
| `cat_cnc_bits` | `x_southbrook_coating` | Coating | left |
| `cat_cnc_bits` | `x_southbrook_rotation_speed_max` | Max RPM | right |
| `cat_drill_bits` | `x_southbrook_cutting_diameter_mm` | Diameter (mm) | right |
| `cat_drill_bits` | `x_southbrook_shank_diameter_mm` | Shank (mm) | right |
| `cat_drill_bits` | `x_southbrook_overall_length_mm` | Overall (mm) | right |
| `cat_abrasives` | `x_southbrook_grit` | Grit | left |
| `cat_finishing` | `x_southbrook_shelf_life_days` | Shelf life (days) | right |
| `cat_finishing` | `x_southbrook_storage_temperature_notes` | Storage | left |

Add to the manifest `data` list, after `data/catalog_action.xml`:
```python
        "data/catalog_declarations.xml",
```

- [ ] **Step 4: Run test to verify it passes**

Run: `odoo-bin -d <db> -u sb_materials_hardware --test-enable --stop-after-init --test-tags=sbk_mathw`
Expected: PASS, 41 tests.

- [ ] **Step 5: Commit**

```bash
git add addons/sb_materials_hardware
git commit -m "feat(materials-hardware): seed facet and column declarations for sections A-E"
```

---

### Task 12: The catalog client action (OWL)

**Files:**
- Modify: `addons/sb_materials_hardware/static/src/catalog/catalog.js`
- Modify: `addons/sb_materials_hardware/static/src/catalog/catalog.xml`
- Modify: `addons/sb_materials_hardware/static/src/catalog/catalog.scss`
- Test: manual verification against the reference UX (see Step 4)

**Interfaces:**
- Consumes: `materials.catalog.provider.get_catalog` and `get_detail`
- Produces: the client action registered under tag `sb_materials_hardware.catalog`

- [ ] **Step 1: Write the component**

`static/src/catalog/catalog.js`:
```javascript
/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class MaterialsHardwareCatalog extends Component {
    static template = "sb_materials_hardware.Catalog";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.state = useState({
            loading: true,
            ok: true,
            reason: "",
            categories: [],
            facets: [],
            columns: [],
            rows: [],
            total: 0,
            provenance: "",
            categoryId: null,
            selectedFacets: {},
            search: "",
            detail: null,
        });
        onWillStart(() => this.load());
    }

    async load() {
        this.state.loading = true;
        const payload = await this.orm.call(
            "materials.catalog.provider", "get_catalog", [], {
                scope: "tools",
                category_id: this.state.categoryId,
                facets: this.state.selectedFacets,
                search: this.state.search,
            });
        Object.assign(this.state, payload, { loading: false });
        this.state.detail = null;
    }

    get topCategories() {
        return this.state.categories.filter((c) => !c.parent_id);
    }

    childrenOf(categoryId) {
        return this.state.categories.filter((c) => c.parent_id === categoryId);
    }

    isSelected(key, value) {
        const chosen = this.state.selectedFacets[key] || [];
        return chosen.includes(value);
    }

    async selectCategory(categoryId) {
        this.state.categoryId = categoryId;
        this.state.selectedFacets = {};
        await this.load();
    }

    async toggleFacet(key, value) {
        const chosen = this.state.selectedFacets[key] || [];
        const next = chosen.includes(value)
            ? chosen.filter((v) => v !== value)
            : chosen.concat([value]);
        if (next.length) {
            this.state.selectedFacets[key] = next;
        } else {
            delete this.state.selectedFacets[key];
        }
        await this.load();
    }

    async clearFilters() {
        this.state.selectedFacets = {};
        this.state.search = "";
        await this.load();
    }

    async onSearchInput(ev) {
        this.state.search = ev.target.value;
        await this.load();
    }

    async selectRow(productId) {
        this.state.detail = await this.orm.call(
            "materials.catalog.provider", "get_detail", [productId]);
    }

    cell(row, key) {
        const value = row[key];
        return value === null || value === undefined || value === false
            ? "—"
            : value;
    }
}

registry.category("actions").add(
    "sb_materials_hardware.catalog", MaterialsHardwareCatalog);
```

`static/src/catalog/catalog.xml`:
```xml
<?xml version="1.0" encoding="utf-8"?>
<templates xml:space="preserve">

<t t-name="sb_materials_hardware.Catalog">
  <div class="o_matcat">
    <div class="o_matcat_masthead">
      <span class="o_matcat_brand">HARDWARE CATALOG</span>
      <input type="text" class="o_matcat_search"
             placeholder="Search parts, specs, references"
             t-att-value="state.search"
             t-on-input="onSearchInput"/>
      <button class="o_matcat_clear" t-on-click="clearFilters">Clear</button>
    </div>

    <t t-if="!state.ok">
      <div class="o_matcat_empty">
        Catalog unavailable. <t t-esc="state.reason"/>
      </div>
    </t>

    <t t-if="state.ok">
      <div class="o_matcat_body">
        <aside class="o_matcat_rail">
          <h4>Categories</h4>
          <t t-foreach="topCategories" t-as="top" t-key="top.id">
            <button class="o_matcat_cat"
                    t-att-class="{ o_selected: state.categoryId === top.id }"
                    t-on-click="() => this.selectCategory(top.id)">
              <span t-esc="top.name"/>
              <span class="o_matcat_count" t-esc="top.count"/>
            </button>
            <t t-foreach="childrenOf(top.id)" t-as="sub" t-key="sub.id">
              <button class="o_matcat_cat o_matcat_child"
                      t-att-class="{ o_selected: state.categoryId === sub.id }"
                      t-on-click="() => this.selectCategory(sub.id)">
                <span t-esc="sub.name"/>
                <span class="o_matcat_count" t-esc="sub.count"/>
              </button>
            </t>
          </t>

          <t t-foreach="state.facets" t-as="facet" t-key="facet.key">
            <div class="o_matcat_facet">
              <div class="o_matcat_facet_title" t-esc="facet.label"/>
              <div class="o_matcat_chips">
                <t t-foreach="facet.values" t-as="val" t-key="val.value">
                  <button class="o_matcat_chip"
                          t-att-class="{ o_on: isSelected(facet.key, val.value) }"
                          t-on-click="() => this.toggleFacet(facet.key, val.value)">
                    <t t-esc="val.label"/>
                  </button>
                </t>
              </div>
            </div>
          </t>
        </aside>

        <section class="o_matcat_results">
          <div class="o_matcat_resbar">
            <b t-esc="state.total"/> variants
          </div>
          <div class="o_matcat_tablewrap">
            <table class="o_matcat_table">
              <thead>
                <tr>
                  <t t-foreach="state.columns" t-as="col" t-key="col.key">
                    <th t-att-class="col.align === 'right' ? 'o_right' : ''"
                        t-esc="col.label"/>
                  </t>
                </tr>
              </thead>
              <tbody>
                <t t-if="!state.rows.length">
                  <tr><td t-att-colspan="state.columns.length" class="o_matcat_empty">
                    No matching parts. Try removing a filter or broadening your search.
                  </td></tr>
                </t>
                <t t-foreach="state.rows" t-as="row" t-key="row.product_id">
                  <tr t-on-click="() => this.selectRow(row.product_id)">
                    <t t-foreach="state.columns" t-as="col" t-key="col.key">
                      <td t-att-class="col.align === 'right' ? 'o_right' : ''"
                          t-esc="cell(row, col.key)"/>
                    </t>
                  </tr>
                </t>
              </tbody>
            </table>
          </div>

          <t t-if="state.detail &amp;&amp; state.detail.ok">
            <div class="o_matcat_detail">
              <h3 t-esc="state.detail.title"/>
              <div class="o_matcat_sub" t-esc="state.detail.subtitle"/>
              <div class="o_matcat_badges">
                <t t-foreach="state.detail.badges" t-as="badge" t-key="badge">
                  <span class="o_matcat_badge" t-esc="badge"/>
                </t>
              </div>
              <div class="o_matcat_specgrid">
                <t t-foreach="state.detail.specs" t-as="spec" t-key="spec.label">
                  <div class="o_matcat_spec">
                    <span class="o_k" t-esc="spec.label"/>
                    <span class="o_v" t-esc="spec.value === null ? '—' : spec.value"/>
                  </div>
                </t>
              </div>
              <div class="o_matcat_eng">
                <t t-foreach="state.detail.engineering" t-as="eng" t-key="eng.label">
                  <div class="o_matcat_kv">
                    <span class="o_k" t-esc="eng.label"/>
                    <span class="o_v" t-esc="eng.value === null ? '—' : eng.value"/>
                  </div>
                </t>
              </div>
            </div>
          </t>
        </section>
      </div>
      <div class="o_matcat_provenance" t-esc="state.provenance"/>
    </t>
  </div>
</t>

</templates>
```

`static/src/catalog/catalog.scss` — port the reference palette. Note `Min()` capitalisation per Global Constraints:
```scss
.o_matcat {
    --mc-bg: #f4f6f8;
    --mc-surface: #ffffff;
    --mc-line: #d6dde3;
    --mc-text: #111418;
    --mc-text-soft: #4a5560;
    --mc-text-mute: #8b97a3;
    --mc-accent: #b8242a;
    --mc-row-hover: #fff8e1;
    --mc-link: #1851a8;

    background: var(--mc-bg);
    color: var(--mc-text);
    height: 100%;
    overflow: auto;

    .o_matcat_masthead {
        display: flex; align-items: center; gap: 12px;
        padding: 10px 16px; background: var(--mc-surface);
        border-bottom: 2px solid var(--mc-accent);
    }
    .o_matcat_brand { font-weight: 800; color: var(--mc-accent); }
    .o_matcat_search {
        flex: 1; min-width: 180px; padding: 6px 10px;
        border: 1px solid var(--mc-line); border-radius: 4px;
    }
    .o_matcat_body { display: flex; align-items: flex-start; }
    .o_matcat_rail {
        width: Min(260px, 30%);
        border-right: 1px solid var(--mc-line);
        background: var(--mc-surface);
    }
    .o_matcat_cat {
        display: flex; justify-content: space-between; width: 100%;
        border: 0; background: none; text-align: left;
        padding: 6px 14px; cursor: pointer;
        &.o_matcat_child { padding-left: 28px; color: var(--mc-text-soft); }
        &.o_selected { color: var(--mc-accent); font-weight: 700; }
    }
    .o_matcat_count { color: var(--mc-text-mute); font-size: 11px; }
    .o_matcat_chip {
        border: 1px solid var(--mc-line); border-radius: 4px;
        padding: 3px 8px; margin: 2px; cursor: pointer; font-size: 11.5px;
        &.o_on { background: var(--mc-accent); color: #fff; }
    }
    .o_matcat_results { flex: 1; min-width: 0; }
    .o_matcat_tablewrap { overflow-x: auto; }
    .o_matcat_table {
        width: 100%; border-collapse: collapse; font-size: 12.5px;
        th {
            position: sticky; top: 0; background: #fafbfc;
            text-align: left; font-size: 10px; text-transform: uppercase;
            letter-spacing: .07em; color: var(--mc-text-mute);
            padding: 8px 10px; border-bottom: 1px solid var(--mc-line);
        }
        td { padding: 7px 10px; border-bottom: 1px solid #e6ebef; }
        tbody tr:hover { background: var(--mc-row-hover); cursor: pointer; }
        .o_right { text-align: right; font-variant-numeric: tabular-nums; }
    }
    .o_matcat_empty { padding: 24px; text-align: center; color: var(--mc-text-mute); }
    .o_matcat_detail { border-top: 1px solid var(--mc-line); padding: 14px 16px; }
    .o_matcat_specgrid { display: flex; flex-wrap: wrap; gap: 12px; }
    .o_matcat_spec, .o_matcat_kv { display: flex; flex-direction: column; }
    .o_matcat_spec .o_k, .o_matcat_kv .o_k {
        font-size: 9.5px; text-transform: uppercase; letter-spacing: .08em;
        color: var(--mc-text-mute);
    }
    .o_matcat_badge {
        border: 1px solid var(--mc-accent); color: var(--mc-accent);
        border-radius: 3px; padding: 2px 7px; font-size: 10.5px; margin-right: 4px;
    }
    .o_matcat_provenance {
        padding: 10px 16px; font-size: 12px; color: var(--mc-text-soft);
    }
}
```

- [ ] **Step 2: Restart and load the action**

Asset bundles are hashed. `-u` alone can serve a stale bundle:
```bash
odoo-bin -d <db> -u sb_materials_hardware --stop-after-init
# then restart the server process
```
Open **Inventory → Hardware Catalog**.

- [ ] **Step 3: Verify against the reference UX**

Open `Material Hardware App/reference/UX_TEMPLATE_materials_catalog.html` side by side and confirm:
category rail with counts · facet chips that toggle and re-query · dense table with sticky header and hover · row click opens the detail · absent specs render `—` · empty state reads "No matching parts. Try removing a filter or broadening your search."

- [ ] **Step 4: Check the browser console**

Expected: no errors. An OWL "Missing template" error means the bundle is stale — restart rather than re-`-u`.

- [ ] **Step 5: Commit**

```bash
git add addons/sb_materials_hardware
git commit -m "feat(materials-hardware): OWL catalog client action"
```

---

## Completion

After Task 12:

1. **Full test run:** `odoo-bin -d <db> -u sb_materials_hardware --test-enable --stop-after-init --test-tags=sbk_mathw` — all green.
2. **Push to both remotes** per spec §10 — Forgejo primary, GitHub mirror.
3. **Multi-agent code review** per spec §11 — parallel low-cost subagents across correctness, Odoo 19 conformance, security, performance, test coverage, UX fidelity and data correctness; findings verified adversarially before any repair; reports into `Material Hardware App/reports/`.
4. **Repairs and upgrades**, then re-review what changed.
5. **Install remains gated** — staging first, on explicit go-ahead only.
