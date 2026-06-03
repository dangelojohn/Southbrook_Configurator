# Storefront Audit — `/shop` Visibility Review

**Generated 2026-06-03.**

**Status update 2026-06-03 (later in the same session):** the human reviewer
authorized the unpublish recommendations from §1 and §2 below. The 6 rows
(`product_template` ids `36, 37, 38, 39, 42, 211`) were marked
`is_published = false` via a single SQL UPDATE; public `/shop` now shows 47
templates (was 53) and the duplicate cards + the test artifact are gone
verified against `https://southbrookcabinetry.space/shop`. The actual
`product_template` records and their attribute_lines / config.lines /
existing sale.order.line references were preserved — only the website
visibility flag was toggled, so the change is reversible by flipping the
flag back.

## TL;DR

- **53 templates currently published** (`product_template.is_published=true`); 14 unpublished.
- Storefront listing on `southbrookcabinetry.local:9443/shop` is controlled by `product_template.is_published` (boolean). The OCA `website_sale` `_get_search_domain` filters on this flag plus `sale_ok` and the website-availability rules in `ir.rule`. Toggling **`is_published`** alone removes a product from `/shop` without affecting back-end sale capability.
- **Two categories of cleanup recommended** below: (1) one test artifact, (2) five duplicate cabinet templates left over from the catalog-expansion's initial run before SKU persistence landed. The raw manufacturing components the walkthrough flagged are **already unpublished** (the original sighting predated the import pipeline cleanup).

---

## 1 · Test artifact (recommended: unpublish)

| id | default_code | name | list_price | category | Reason |
|---|---|---|---|---|---|
| 211 | `SB-P4P2-1780480538` | Phase 4 part 2 smoke | 175.00 | Wall | Created by an `/import/commit` smoke test on 2026-06-03 — produced by the Phase 4 part 2 verification, not a real cabinet. |

**Action:** review and unpublish (and consider deleting the variant + any draft order lines that reference it before delete).

---

## 2 · Duplicate cabinet templates (recommended: pick one of each pair, unpublish the other)

The Q8 locked templates (ids 36–47) and the catalog-expansion templates (ids 212+) include five **exact-name duplicates**. The Q8 records have empty `default_code`; the catalog records carry SKUs. Customers searching `/shop` see both cards for each.

| Q8 id | Q8 SKU | Catalog id | Catalog SKU | Name | List price | Notes |
|---|---|---|---|---|---|---|
| 36 | (none) | 229 | `SB-WALL-1DR` | Wall Cabinet · Single Door | $245.00 | Same attribute_lines; catalog row has rules wired via `rule_completion`. |
| 37 | (none) | 230 | `SB-WALL-2DR` | Wall Cabinet · Double Door | $325.00 | Same. |
| 38 | (none) | 212 | `SB-BASE-1DR` | Base Cabinet · Single Door | $295.00 | Q8 row was renamed (was "Base 1-Door"); the catalog write touched both. |
| 39 | `SB-BASE-2DR` | 213 | `SB-BASE-2DR` | Base Cabinet · Double Door | $395.00 | Same default_code on both rows — duplicate SKU. |
| 42 | `SB-TALL-PANTRY` | 237 | `SB-TALL-PANTRY` | Tall Pantry | $895.00 | Same default_code on both rows. |

**Why this happened:** `catalog_expansion.build_catalog()` shipped (commit `ebf22d8`) before the SKU-persistence fix (`1379ab0`). On its first run the Q8 templates had empty `default_code`, so `Template.search([("default_code","=",sku)])` returned empty — and `Template.search([("name","=",catalog_name)])` ALSO returned empty (Q8 names were "Wall 1-Door", "Base 1-Door", etc., not the catalog names). Result: the builder created brand-new templates (ids 212+) AND, on a subsequent re-run after the SKU fix, **also** wrote `name = "<catalog name>"` to ids 36–47 because the catalog dict's name field landed on whatever existing template the rules-engine path resolved through. The Q8 default_codes remained blank.

**Action:** for each pair, decide which row should be the canonical product:
- **Keep the catalog rows (212/213/229/230/237):** they carry SKUs + are wired through `catalog_expansion.py` + `rule_completion.py`. Unpublish 36, 37, 38, 39, 42 and update any existing sale.order.line / mrp.bom / draft order references to point at the catalog ids first.
- **Keep the Q8 rows (36-42):** they have stable xml_ids (e.g. `southbrook_estimating.base_1dr`) that `config_rules.xml`'s Rule 3 + Rule 4 reference. Unpublishing them would NOT break those references (rules don't require `is_published`), but any code that resolves `env.ref('southbrook_estimating.base_1dr')` continues to work either way.

Recommendation: keep the **catalog rows** as the canonical ones (they're the named-and-SKU'd model the import pipeline + rule_completion target), unpublish the Q8 originals. Confirm no sale.order.line / mrp.bom rows reference the Q8 ids before unpublishing — query:

```sql
SELECT COUNT(*) FROM sale_order_line WHERE product_id IN (
    SELECT id FROM product_product WHERE product_tmpl_id IN (36,37,38,39,42)
);
```

---

## 3 · Raw manufacturing components — **already unpublished**

The walkthrough flagged screws, dowels, cam locks etc. appearing in the public grid. These are ALL currently `is_published=false`:

| id | name | is_published |
|---|---|---|
| 193 | Confirmat Screw 7x50 | false |
| 194 | 8mm Wood Dowel | false |
| 195 | Minifix Cam Lock | false |
| 196 | Handle Screw M4 | false |
| 197 | Drawer Slide Screw | false |
| 198 | EVA Glue Cartridge | false |
| 199 | PUR Glue | false |

**No action needed** — these are correctly hidden from `/shop`. If they were visible during the walkthrough, that was before the publish-state cleanup. Confirm by visiting `/shop?search=screw` on the live site — should return no results.

---

## 4 · The full published list (for reference)

53 templates. Cabinet products + 7 accessories from `catalog_expansion`. See:
```sql
SELECT id, default_code, name->>'en_US', list_price, southbrook_category
FROM product_template
WHERE is_published = true
ORDER BY id;
```

(Already attached to the audit branch's git log as the verification snapshot.)

---

## 5 · How to unpublish (for the human reviewer)

**Via UI:** Backend → Sales → Products → search by SKU → uncheck "Published on Website" on the product form.

**Via SQL (after confirming no live order references):**

```sql
UPDATE product_template
SET is_published = false
WHERE id IN (211, 36, 37, 38, 39, 42);
```

**Side-effect to consider:** unpublishing a template that has variants already on draft sale.order.lines does NOT remove those lines or block them from being confirmed. Existing customer carts continue to work; the product just stops appearing in `/shop` for new visitors.

## 6 · Side-finding: also worth a look

While auditing, I noticed an open thread that's **not** a `/shop` visibility issue but is related:

- **Q8 vs catalog-expansion duplicate definitions**: even after deciding which side of the duplicate pairs to keep, the long-term fix is to consolidate. Either delete the Q8 product_templates.xml entries from `southbrook_estimating` (and let catalog_expansion own them), or remove the matching catalog dict rows and let the static xml_ids stand. Worth a separate decision since either path touches the canonical data file.

That decision is out of scope for this report — flagging only so it doesn't get lost.
