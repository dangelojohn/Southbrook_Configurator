# Configurator Audit — June 2026

> **Author:** Senior Product Manager, Southbrook Cabinetry
> **Date:** 2026-06-09
> **Scope:** `southbrook_estimating` configurator attribute & customization surface
> **Decision asked:** Are we competitive with high-end semi-custom and fully-custom cabinet manufacturers in 2026, and where are the gaps?

## TL;DR

Our current MVP ships with **11 user-facing attributes** (Q2-locked) and **12 cabinet templates** (Q8-locked). That's enough for a "stock-plus" line — it competes with IKEA Sektion and the lower tier of MasterBrand's family (Hampton Bay, lower Diamond, lower KraftMaid). It is **not enough** to compete head-to-head with the manufacturers in the price band Southbrook is positioned to sell into (Wood-Mode, Plain & Fancy, Mouser, Wellborn, Brighton, Cabico, Decora, mid-Diamond, upper KraftMaid).

This audit lands **10 new attributes + 6 new door styles** in the same configurator data file, with one new `display_type=color` swatch picker (pull finish). All additions are declarative (no Python), so the Q3.4 acceptance gate is preserved. Pricing is intentionally NOT in this commit — product manager populates the 6-channel matrix before launch.

## What today's configurator actually offers

| # | Attribute | Values | Comment |
|---|---|---|---|
| 1 | family | Wall, Base, Drawer, Sink, Tall, Corner, Vanity, Worktop, Accessory | OK; "Corner" is one lump |
| 2 | family_subtype | Standard, Bi-fold | Used only on Corner |
| 3 | width | 9–36 in (10 values) | OK |
| 4 | series | Contractor, Contemporary, Elegance, Signature | OK — tier ladder |
| 5 | box_material | White Melamine, Maple | **Thin** — 2 values |
| 6 | door_style | Thermofoil Slab White, Five-Piece Woodgrain, Custom | **Critically thin** — 3 values, conflates everything |
| 7 | finish | White, Maple Stain, Cherry Stain, Walnut Stain, Custom | Conflates species + stain |
| 8 | hinge_side | LH, RH, N/A | OK |
| 9 | finished_sides | None, Left, Right, Both | OK |
| 10 | gables | Standard, Finished, Decorative | OK |
| 11 | handle | Bar Pull, Knob, Cup Pull, Integrated, None | Style only — no finish |
| 12 | accessories | Soft-Close, Drawer Organisers, Pull-Outs | **Critically vague** — too coarse for a BoM |
| 13 | accessory_type | End Panel, Filler, Cornice, Pelmet, Plinth | Sub-attribute of Accessory family |
| 14 | door_count | 1, 2 | Derived from width, hidden from customer |

**12 cabinet templates** — `wall_1dr`, `wall_2dr`, `base_1dr`, `base_2dr`, `drawer_bank`, `sink_base`, `tall_pantry`, `tall_oven`, `corner`, `vanity`, `accessory`, `worktop`. Q8-locked.

## Methodology

I benchmarked the catalog against 8 competitors in the price band Southbrook wants to compete in:

1. **Wood-Mode** — semi-custom + fully-custom, traditional → contemporary
2. **Plain & Fancy** — bench-built fully-custom
3. **Mouser** — Tier-1 semi-custom (inset & inset-bead specialist)
4. **Wellborn Cabinet** — semi-custom, deep finish menu
5. **Brighton Cabinetry** — Canadian semi-custom (closest direct comp)
6. **Cabico** — Canadian fully-custom (framed + frameless)
7. **MasterBrand Diamond** — top mass-market semi-custom
8. **MasterBrand KraftMaid** — upper-tier semi-custom

I scraped current configurator option counts from each (where public; sales-rep walkthroughs where not). Attributes were normalized to common categories for comparison.

## Gap analysis — what high-end competitors offer that we don't

### Category A — Construction (the biggest gap)

| Attribute | Competitive baseline | Our state | Gap |
|---|---|---|---|
| **Frame Style** (framed vs frameless) | 100% of competitors | Not modeled | **Critical** — first question every buyer asks |
| **Door Overlay** (full / partial / inset / beaded inset) | 100% offer ≥3 options; premium offer beaded inset | Not modeled | **Critical** — premium-tier signaling |
| **Drawer Construction** (dovetail solid wood / plywood / particleboard / Blum metal) | 100% expose this | Not modeled | **Critical** — dovetail is the dividing line for "semi-custom" |
| **Wood Species** as a first-class attribute | 100% expose 5–12 species | Conflated into "finish" (4 species-stained options) | **Critical** — buyer's primary palette decision |

### Category B — Door style depth

| Attribute | Competitive baseline | Our state | Gap |
|---|---|---|---|
| Door styles | 15–60 per competitor; Wood-Mode lists 120+ | 3 (slab/woodgrain/custom) | **Critical** — Shaker alone is the #1 selling style in NA 2026 |
| Glass insert | 4–8 options (clear, frosted, seeded, reeded, leaded) | Not modeled | **Important** — required for any glass-door wall |
| Edge profile | 3–8 options (square, eased, ogee, bevel, bullnose) | Not modeled | **Important** — signals tier |

### Category C — Finish menu

| Attribute | Competitive baseline | Our state | Gap |
|---|---|---|---|
| Stain colors | 12–40 per species + custom match | 4 generic species-stains | **Important** — needs to scope by species |
| Painted finishes | 25–60 standards + custom | "White" + Custom | **Important** |
| Glaze overlay | Optional on premium | Not modeled | **Nice-to-have** for upper tiers |
| Distressing | Optional on premium | Not modeled | **Nice-to-have** |

### Category D — Hardware

| Attribute | Competitive baseline | Our state | Gap |
|---|---|---|---|
| Pull style | 5–8 styles | 5 (bar/knob/cup/integrated/none) ✓ | OK |
| Pull finish | 6–10 metal finishes | Not modeled | **Critical** — drives the whole room palette |
| Soft-close | Standard, not optional, at high-end | Optional flag | **Important** — change default; old default looks budget |
| Drawer slides | Soft-close + full-extension as standard | Bundled under "accessories" vaguely | **Important** |

### Category E — Interior accessories

| Attribute | Competitive baseline | Our state | Gap |
|---|---|---|---|
| Interior catalog | 30–60 specific items | 3 buckets (Soft-Close, Drawer Organisers, Pull-Outs) | **Critical** — current grouping cannot drive a BoM |
| Lighting | 3–5 options (under-cab LED, interior LED, toekick, puck) | Not modeled | **Important** — high-margin upsell |
| Mixer lift, charging drawer | Sold widely at premium | Not modeled | **Nice-to-have** differentiator |

### Category F — Crown, molding, trim

| Attribute | Competitive baseline | Our state | Gap |
|---|---|---|---|
| Crown style | 5–10 profiles | Hidden under Accessory subtype → Cornice (single value) | **Important** — needs first-class attribute |
| Light rail | Standard option | Not modeled | **Nice-to-have** |
| Toe kick | 2–3 options | Single default | **Nice-to-have** |

### Category G — Cabinet types beyond the locked 12

The Q8 lock blocks new template additions in this audit. Flagging the gap so it gets a Phase-2 RFC:

- Lazy Susan corner / Diagonal corner / Blind corner (current "Corner" is one undifferentiated lump)
- Wall Bridge (over range)
- Microwave Wall (with shelf cutout)
- Range Hood Cover
- Appliance Garage
- Trash Pullout Base (as a dedicated template, not just an interior accessory)
- Refrigerator End Panel / Tall Side Panel
- Wine Cabinet
- Bookcase Open Shelving

## Recommendations

**P0 — Ship now (this audit commit):**

1. Add 10 new first-class attributes covering Construction, Hardware Finish, Interior Storage, Lighting, Glass, Edge, Crown.
2. Add 6 new values to `attr_door_style` (Shaker, Raised Panel, Beadboard, Mullion Glass, V-Groove, Reeded).
3. Document 8 gating-rule business intents in `config_rules.xml` for Phase-2 wiring.

**P1 — Next sprint:**

4. Wire the gating rules to per-template `product.config.line` records once the new attributes are added to each cabinet template's `attribute_ids`.
5. Populate pricing for the new values across all 6 channels in `cabinet_prices.xml`. PM responsibility.
6. Change the default for soft-close from optional → standard (with an opt-out, not opt-in). Hard-budget tier (Contractor) opts out by default; everyone else opts in.

**P2 — Next quarter:**

7. RFC to open the Q8 cabinet template lock and add 6–10 cabinet types (lazy susan corner, blind corner, microwave wall, range hood cover, trash pullout base, wine cabinet, refrigerator end panel, bookcase, appliance garage, wall bridge).
8. Scope `attr_finish` (stain/paint color) by `attr_wood_species` — declarative rule, not Python.
9. Add `glaze` and `distressing` as upper-tier (Elegance + Signature) finish overlays.

## What's in this commit

- `addons/southbrook_estimating/data/attributes.xml` — 10 new `product.attribute` records (sequences 120–210), ~50 new `product.attribute.value` records.
- `addons/southbrook_estimating/data/config_rules.xml` — 7 new reusable `product.config.domain` predicates + documented business rules A1–A8 ready for Phase-2 binding.
- `docs/configurator_audit_2026_06.md` — this document.

## What is intentionally **not** in this commit

- **Pricing** for the new values. Every value needs a real number in each of the 6 channels (`retail`, `dealer`, `tradesperson`, `kd`, `bigbox`, `refacing`) sourced from the Price Master tab of `Southbrook_Consolidated_Dataset.xlsx`. That's a separate PM data-entry pass.
- **`product.config.line` bindings** for the audit rules. The rules are documented; binding them requires `attribute_line_ids` that exist only once the new attributes are added to each cabinet template's `attribute_ids` (~40 lines per template × 12 templates). Phase-2 task.
- **New cabinet templates.** Q8 locks the 12. Audit flags the gap; opening the lock is a separate RFC.
- **UI changes.** The new attributes render with their natural `display_type` (radio/select/multi/color). Order-builder and customer-facing kitchen-planner UI changes (e.g., a "Finish & Hardware" tab grouping) are a Phase-2 UX task.

## Risks

- **Catalog explosion.** With `create_variant='dynamic'`, the variants are created on demand. We won't accidentally pre-create 10⁶ stock variants. But the spec-sheet PDF needs to render the new attributes in a readable layout; the QWeb template will need a Phase-2 pass.
- **BoM rollup.** The new `attr_interior_storage` multi-select needs `mrp_bom.py` to translate each chosen interior item into the correct vendor part. Phase-2 task.
- **Sales rep training.** 10 new attributes is a meaningful jump. PM owns a sales-rep training session before launch.

## What we did NOT change

- The 11 Q2-locked attributes — unchanged.
- The 12 Q8-locked cabinet templates — unchanged.
- Python code — zero changes (Q3.4 declarative-rules gate preserved).
- The 4 declarative rules from `Southbrook_Excel_to_Odoo_Mapping.md` §3.4 — unchanged.
- Pricelists — unchanged. PM populates new prices.

---

*Submitted to the Southbrook product committee for review.*
*Acceptance: configurator installs clean (`odoo-bin -i southbrook_estimating --stop-after-init`), new attributes appear in the order-builder attribute pane, no regressions on the existing Q7 smoke test (Demo Tradesperson Tier 3 9-line build, BoM preview, MO creation).*

---

# Implementation outcome (2026-06-09 → 2026-06-10)

The proposed audit was accepted and shipped over Phases **2A → 2N**. This
section is the handoff: what landed, where it lives, and the two
silent-killer gotchas a future contributor must know before touching
audit-class data.

## What's live on `origin/main`

| Surface | Before audit | After |
|---|---|---|
| User-facing attributes | 11 | **21** (10 new from §3 above) |
| Door style values | 3 | **9** (6 new) |
| Declarative gating rules | 4 | **85** (`ruleA1`–`ruleA8`) |
| Wizard layout | one flat scroll | **4 tabbed steps** per cabinet |
| Accessories default | nothing pre-selected | **Soft-Close** on 34/34 SB-* cabinets |
| `price_extra` deltas | sparse | **62 new** demo-grade deltas |
| Regression tests | 0 audit-specific | **23** locked in (`test_audit_phase2.py`) |
| Live-browser walkthrough | none | Playwright scaffold in `e2e/` |
| Deploy reproducibility | scp by hand | `scripts/deploy_to_qnap.sh` |

Module version after Phase 2N: `southbrook_estimating == 19.0.1.7.0`.

## Phase-by-phase trace

| Phase | Concern | Files touched | Where the rules / data live |
|---|---|---|---|
| 2A/2B | Add 10 attrs + wire to 12 templates | `data/attributes.xml`, `data/product_templates.xml`, `data/config_rules.xml` | 77 new `attr_line_*` + A1+A3+A4 rules |
| 2C | Backfill broken attr_lines on 6 cabinets | `migrations/19.0.1.2.0/post-migrate.py` | ORM-level write-or-create |
| 2D/2E/2H | `catalog_expansion.py` non-destructive reconcile | `addons/southbrook_configurator_ux/models/catalog_expansion.py` | preserve attr_line row IDs → preserve gating-rule FKs |
| 2F | Add A2/A6/A7 rules | `data/config_rules.xml` | 21 more `ruleA*` records |
| 2I | A5 + soft-close + `rule_completion` scoping fix | `data/config_rules.xml`, `data/product_templates.xml`, `addons/southbrook_configurator_ux/models/rule_completion.py`, `catalog_expansion.py` | A5=8 rules, `default_val`, sequence-scoped unlink |
| 2J | A8 finish-by-species | `data/config_rules.xml` | 3 new domains + 30 rules |
| 2K/2L | 4-tab wizard layout | `data/config_steps.xml`, `__manifest__.py`, `catalog_expansion.py` | 4 `product.config.step` + 40 `step_line` records + per-expanded-cabinet seeding |
| 2M | Pricing pass | `addons/southbrook_configurator_ux/models/tactical_price_seed.py` | 62 new `(attr, value) → (price_extra, weight_extra)` deltas |
| 2N | Catalog parity test | `tests/test_audit_phase2.py`, `data/config_steps.xml`, `catalog_expansion.py` | Adds SB-ACCESSORY + SB-WORKTOP step lines; "Accessory Type" in step map |

## The gating-rule pattern (how to add one safely)

Every audit-class rule is **one `product.config.line`** restricting one
attribute on one template, gated by one `product.config.domain`.

```xml
<record id="domain_species_is_maple" model="product.config.domain">
  <field name="name">Species is Maple</field>
</record>
<record id="domain_species_is_maple_line" model="product.config.domain.line">
  <field name="domain_id" ref="domain_species_is_maple"/>
  <field name="attribute_id" ref="attr_wood_species"/>
  <field name="condition">in</field>
  <field name="operator">and</field>
  <field name="value_ids" eval="[(6, 0, [ref('value_species_maple')])]"/>
</record>

<record id="ruleA8_base_1dr_maple_stain_by_species" model="product.config.line">
  <field name="product_tmpl_id" ref="base_1dr"/>
  <field name="attribute_line_id" ref="attr_line_base_1dr_finish"/>
  <field name="value_ids" eval="[(6, 0, [ref('value_finish_maple_stain')])]"/>
  <field name="domain_id" ref="domain_species_is_maple"/>
  <field name="sequence">47000</field>
</record>
```

**OCA's per-value AND semantic** is the rule that catches people: for
each attribute *value* V, OCA finds every `config.line` that mentions V
in its `value_ids`, ANDs all their `domain_id`s together, and shows V
only if the combined domain matches current picks. So:

- A value mentioned in ONE rule with domain D → available only when D
  is satisfied. (Most cases.)
- A value mentioned in MULTIPLE rules with domains D1, D2 → available
  only when **both** are satisfied. (Rare, often a bug.)
- A value mentioned in ZERO rules → always available.

When in doubt, write **one rule per (template × value)** with the
combined domain expressed as a single `condition=in` with a value
list — never two rules for the same value.

## Sequence-range convention

| Range | Owner | Purpose |
|---|---|---|
| `10–99` | `rule1_*` (Series → Door Style, original) | OCA expects sequence on read |
| `20000–20999` | `rule_completion.complete_rules()` | per-value "Series allows V" pattern (sequence 20000 for box, 20010 for door) |
| `40000–47999` | static `config_rules.xml` audit rules | A1=40000, A3=41000, A4=42000, A5=43000, A8=47000, etc. |

**Don't write rules at sequence 20000 or 20010** — `rule_completion`
will delete them on the next install. That's the Phase 2I gotcha.

## Two silent-killer gotchas

### 1. `rule_completion.complete_rules()` will delete your rule

`southbrook_configurator_ux/models/rule_completion.py` was built to
rewrite the broken seed "Contractor → box_material allowed = [...]"
pattern into per-value `config.line` records. Its rewrite **deletes
all existing `config.line` records on the `Box Material` and `Door
Style` attribute_lines** before recreating its own.

The Phase 2I fix narrowed the delete to `sequence IN (20000, 20010)` —
so audit rules at sequence 4xxxx survive. **If you add a rule at
sequence 20000 or 20010, it will be silently wiped.** If you need to
restrict `Box Material` or `Door Style` with a new audit rule, pick a
sequence in 4xxxx.

### 2. `catalog_expansion.py` rebuilds attribute_lines every install

`southbrook_configurator_ux/models/catalog_expansion.py` walks the
catalog and reconciles each template's `attribute_line_ids` to match
the `_ATTRS_*` constants. The original implementation called `.unlink()`
on existing attribute_lines before recreating them — which **cascade-
deleted every `config.line` that referenced those attribute_lines**,
including audit rules.

Phase 2H switched to a non-destructive write-or-create pattern:

```python
existing = AttrLine.search([
    ("product_tmpl_id", "=", tmpl.id),
    ("attribute_id", "=", attr.id),
], limit=1)
if existing:
    if set(existing.value_ids.ids) != set(desired_value_ids):
        existing.write({"value_ids": [(6, 0, desired_value_ids)]})
    line = existing
else:
    line = AttrLine.create({...})
```

**Don't go back to `.unlink()` + `.create()`.** Audit gating rules
have foreign keys to `attribute_line_id`; preserving the row IDs is
what keeps them bound.

## Tested by

| Risk | Test |
|---|---|
| Rule got silently deleted | `TestAuditPhase2Rules.test_01_audit_rule_total` — asserts `ruleA*` count |
| Soft-Close default lost | `TestAuditPhase2SoftClose.test_01_all_q8_cabinets_default_soft_close` |
| Step membership drifted | `TestAuditPhase2WizardSteps.test_03_step_lines_partition_all_attribute_lines` |
| Premium attr value at $0 | `TestAuditPhase2PriceExtras.test_02_premium_audit_values_carry_non_zero_price_extra` |
| Catalog-expanded SKU lost shape | `TestAuditPhase2CatalogExpansion.test_01_every_catalog_cabinet_has_some_step_lines` |
| Attribute name drifted in `_AUDIT_STEPS` | `TestAuditPhase2CatalogExpansion.test_03_q8_and_extended_cabinets_share_step_shape` |

Run with:

```sh
./scripts/deploy_to_qnap.sh southbrook_estimating  # rsync + upgrade
# Or directly with tests:
ssh admin@<qnap> '/share/.../system-docker exec southbrook-odoo \
  odoo -u southbrook_estimating -d southbrook --stop-after-init \
  --no-http --test-enable --test-tags=southbrook'
```

## Where things live (file index)

```
addons/
  southbrook_estimating/
    data/attributes.xml          ← 10 audit attrs + 6 new door styles
    data/product_templates.xml   ← attr_lines per Q8 cabinet, soft-close default_val
    data/config_rules.xml        ← 85 ruleA* gating rules + their domains
    data/config_steps.xml        ← 4 wizard steps + step_lines for 12 Q8 cabinets
    migrations/19.0.1.2.0/post-migrate.py   ← Phase 2C backfill
    migrations/19.0.1.3.0/pre-migrate.py    ← Phase 2G orphan-xml_id cleanup
    tests/test_audit_phase2.py   ← 23 regression tests
  southbrook_configurator_ux/
    models/catalog_expansion.py  ← non-destructive reconcile + _AUDIT_STEPS + soft-close
    models/rule_completion.py    ← sequence-scoped unlink (don't widen)
    models/tactical_price_seed.py ← 108 demo-grade price/weight deltas

scripts/deploy_to_qnap.sh        ← rsync + odoo -u; encodes system-docker quirk
e2e/                             ← Playwright suite (needs SB_ADMIN_PASSWORD)
docs/configurator_audit_2026_06.md ← this file
```

---

*Implementation completed 2026-06-10. Live on QNAP southbrook stack
at `southbrook_estimating == 19.0.1.7.0`. 23/23 audit regression
tests green.*

## Visual confirmation

The full wizard walkthrough captured via Playwright drives the live
QNAP and walks SB-BASE-1DR through every step. The screenshots are
committed in `docs/screenshots/`:

| Step | What the screenshot proves |
|---|---|
| `walkthrough_01_select_template.png` | All four audit step labels appear in the statusbar in order |
| `walkthrough_02_construction.png` | Construction & Sizing shows Width / Series / Box Material / Door Count / Family / **Frame Style** (Phase 1) |
| `walkthrough_03_door_finish.png` | Door & Finish shows Door Style / Finish / **Door Overlay** / **Wood Species** / **Door Edge Profile** (all Phase 1) |
| `walkthrough_04_hardware.png` | Hardware & Sides shows Hinge Side / Finished Sides / Gables / Handle / **Pull Finish** (Phase 1) |
| `walkthrough_05_interior.png` | Interior & Accessories shows **Soft-Close ( +15.00 ) pre-selected** — Phase 2I default + Phase 2M price in the same field |

To regenerate after a UI change:

```sh
cd e2e/
echo 'SB_ADMIN_PASSWORD=<password>' > .env
set -a && source .env && set +a
npx playwright test --grep walkthrough
```

The test writes new screenshots into `docs/screenshots/walkthrough_*.png`.
