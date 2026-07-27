# Size-Aware Procurement Trigger Implementation Plan (Fork-1 Option C)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Wire the native procurement trigger to real material demand: orderpoint MIN (not just MAX) derived from the open-MO `material_demand_qty` rollup, plus a migration that activates Buy-route + orderpoints on the 6 live sheet components — without touching `product_qty`, MO screens, consumption, or valuation.

**Architecture:** Extend the existing `product.template.action_sb_sync_orderpoint_max` (sb_material_mrp, `models/product_template.py:173`) into a min+max sync reusing its exact conversion ladder (native UoM via `_sb_demand_qty_in_uom` → `uom_yield_qty` CEIL → skip+log). Activation ships as an idempotent sb_material_mrp migration (per the cross-module field-order lesson) targeting the 6 components by `default_code`. End-to-end proof extends the existing scheduler test pattern.

**Tech Stack:** Odoo 19 CE; existing `sb_material_mrp` machinery only. No new models.

## Global Constraints
- Odoo 19 CE; LIVE module; additive/backcompat; **`mrp.bom.line.product_qty` untouched** (Fork-1 stands); no MTO; auto-confirm default stays OFF; honesty (skip/log, never fabricate a min/max).
- MIN ≤ MAX invariant: after sync, `product_max_qty = max(existing-MAX-logic, product_min_qty)`.
- Open-MO domain = `_SB_OPEN_MO_STATES = ("confirmed","progress","to_close")` (`product_template.py:37`) — reuse, don't redefine.
- Tests: `TransactionCase`, tags `sbk_material`,`sb_geo`; run `-u sb_material_mrp --test-enable --test-tags sbk_material,sb_geo -d test_sbgeo_b1 --stop-after-init --no-http --http-port=82XX` in `v19c-odoo` after `cp -R addons/{sb_material_core,sb_material_mrp,southbrook_estimating,southbrook_kitchen_3d_configurator} /Users/naadmin/Downloads/Official/V19C/product-configurator/`. New test files must be imported in `tests/__init__.py`; grep the log to confirm the class ran. Distinct unique `code`s per test record.
- Versions: sb_material_mrp 19.0.1.13.0 → **19.0.1.14.0** (T1 code) → migration folder **19.0.1.14.0** carries the activation (T2 rides the same version — ONE bump total).

---

### Task 1: Min+max orderpoint sync

**Files:**
- Modify: `addons/sb_material_mrp/models/product_template.py` (extend `action_sb_sync_orderpoint_max`, keep name as delegating alias; new `action_sb_sync_orderpoints`)
- Modify: `addons/sb_material_mrp/__manifest__.py` (version → 19.0.1.14.0)
- Test: extend `addons/sb_material_mrp/tests/test_orderpoint_sync.py`

**Interfaces:**
- Consumes: `_sb_open_mo_material_demand_qty()` (float, canonical), `_sb_demand_qty_in_uom` conversion, `uom_yield_qty` ladder — all existing in the current MAX sync.
- Produces: `action_sb_sync_orderpoints(warehouse_ids=None)` — creates/updates `stock.warehouse.orderpoint` with `product_min_qty` = converted open-MO demand AND `product_max_qty` = max(existing MAX derivation, min). `action_sb_sync_orderpoint_max` remains, delegating (backcompat for the T5 auto-confirm docs/tests and any callers).

- [ ] **Step 1: Write failing tests** (append to `test_orderpoint_sync.py`; reuse its `_cabinet_with_open_mo` fixture):

```python
    def test_sync_sets_min_from_open_mo_demand(self):
        product, wh = self._cabinet_with_open_mo(code_suffix="minsync")
        product.product_tmpl_id.action_sb_sync_orderpoints()
        op = self.env["stock.warehouse.orderpoint"].search(
            [("product_id", "=", product.id)])
        self.assertEqual(len(op), 1)
        self.assertGreater(op.product_min_qty, 0.0)
        self.assertGreaterEqual(op.product_max_qty, op.product_min_qty)

    def test_min_skipped_when_no_conversion_and_no_yield(self):
        # incompatible UoM + no uom_yield_qty -> orderpoint untouched (honesty)
        product, wh = self._cabinet_with_open_mo(
            code_suffix="minskip", incompatible_uom=True, with_yield=False)
        before = self.env["stock.warehouse.orderpoint"].search_count(
            [("product_id", "=", product.id)])
        product.product_tmpl_id.action_sb_sync_orderpoints()
        after = self.env["stock.warehouse.orderpoint"].search_count(
            [("product_id", "=", product.id)])
        self.assertEqual(before, after)

    def test_legacy_max_alias_still_works(self):
        product, wh = self._cabinet_with_open_mo(code_suffix="alias")
        product.product_tmpl_id.action_sb_sync_orderpoint_max()
        op = self.env["stock.warehouse.orderpoint"].search(
            [("product_id", "=", product.id)])
        self.assertEqual(len(op), 1)
```
(Adapt fixture-arg names to the file's actual `_cabinet_with_open_mo` signature — read it first; if it lacks `incompatible_uom`/`with_yield` switches, build that case inline the way `test_max_native_conversion_when_material_uom_compatible` does.)

- [ ] **Step 2: Run to verify FAIL** (`action_sb_sync_orderpoints` missing). Port 8290.
- [ ] **Step 3: Implement** — rename the body to `action_sb_sync_orderpoints`, compute the converted demand ONCE per product (existing ladder), write BOTH `product_min_qty` (the converted demand) and `product_max_qty` (existing MAX derivation, clamped `>= min`); keep the create-or-update-by-(product,location,company) idempotency; keep skip+log honesty paths; add `def action_sb_sync_orderpoint_max(self, warehouse_ids=None): return self.action_sb_sync_orderpoints(warehouse_ids)`. Update docstrings ("MIN is never touched" is now obsolete — document the new contract). Bump manifest.
- [ ] **Step 4: Run to verify PASS** — all new + all pre-existing orderpoint tests green (the old tests assert MAX behavior; where one asserts `product_min_qty == 0.0`, update it to the new contract with a comment citing this plan). Port 8290.
- [ ] **Step 5: Commit** — `git add` the three files; `git commit -m "feat(sb_material_mrp): orderpoint MIN from open-MO demand (size-aware trigger T1)"`.

---

### Task 2: Activation migration + end-to-end scheduler proof

**Files:**
- Create: `addons/sb_material_mrp/migrations/19.0.1.14.0/post-migrate.py`
- Test: extend `addons/sb_material_mrp/tests/test_scheduler_draft_rfq.py`
- Modify: `addons/sb_material_mrp/README.md` (short "size-aware trigger" note)

**Interfaces:**
- Consumes: `action_sb_set_route_buy()` (existing), `action_sb_sync_orderpoints()` (T1).

- [ ] **Step 1: Failing end-to-end test** (append to `test_scheduler_draft_rfq.py`, mirroring its existing fixture):

```python
    def test_min_from_demand_triggers_draft_rfq_end_to_end(self):
        # open MO -> sync (MIN>0) -> native scheduler -> draft RFQ in purchase units
        # Build: material+component+seller-with-yield+geometry cabinet + CONFIRMED MO,
        # exactly like the existing test's fixture but WITHOUT hand-setting the
        # orderpoint min: call action_sb_sync_orderpoints() instead.
        ...  # reuse/extract the existing test's setup helper; assert:
        # op.product_min_qty > 0; then run_scheduler; then a draft purchase.order
        # exists containing the component with order qty >= 1 (purchase units).
```
(The existing test proves scheduler mechanics with a hand-set orderpoint; this one proves the SYNCED MIN drives it. Extract the shared setup into a helper if duplication is ugly.)

- [ ] **Step 2: Run to verify FAIL/gap.** Port 8291.
- [ ] **Step 3: Migration** — `migrations/19.0.1.14.0/post-migrate.py`, mirroring the module's `19.0.1.13.0` idiom (`migrate(cr, version)`, `if not version: return`, env via `api.Environment`): for the 6 `default_code`s (`RM-MELAMINE_WHITE_5_8, SBK-SHEET-MB34-WW, RM-PLY_3_4, SBK-SHEET-BPY12, SBK-SHEET-BPY14, RM-HARDBOARD_1_4`), find the product (skip absent), call `action_sb_set_route_buy()` then `action_sb_sync_orderpoints()` on its template; log per-product outcome + a summary line. Idempotent by construction (route add is (4,id); sync is create-or-update).
- [ ] **Step 4: Run to verify PASS** — end-to-end test green, migration fires on `-u` (grep `19.0.1.14.0`), all prior suites green. Port 8291.
- [ ] **Step 5: README note + Commit** — document: MIN now demand-driven, activation migration, Fork-1/product_qty still untouched, Option A deferred. `git commit -m "feat(sb_material_mrp): activate size-aware trigger on sheet components (T2)"`.

---

## Self-Review
**Spec coverage:** MIN-from-demand (T1) ✓; MIN≤MAX clamp (T1 Step 3) ✓; activation of 6 components via sanctioned migration (T2) ✓; end-to-end proof (T2 test) ✓; non-goals preserved (no product_qty/MTO/consumption change — nothing in either task touches them) ✓; honesty skip paths kept + tested (T1 test 2) ✓.
**Placeholders:** T2 Step 1 shows intent + exact assertions but defers fixture reuse to the file's real helper — acceptable because the referenced fixture exists and is named; implementer adapts, reviewer verifies.
**Type consistency:** `action_sb_sync_orderpoints(warehouse_ids=None)` produced T1, consumed T2 migration; alias keeps old name callable. One version bump (19.0.1.14.0) shared by code+migration — folder matches manifest.
