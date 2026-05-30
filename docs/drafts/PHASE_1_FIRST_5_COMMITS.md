# Phase 1 · First 6 Commits — Pre-staged Plan

> **2026-05-29 amendment:** expanded from 5 to 6 commits to fold the
> `southbrook.order.analytics` companion model (NF1 from Build Spec §8) and
> the conservative override stub for `product_config.py:1500` (NF2 from
> Build Spec §9.1) into the sequence. See PUNCHLIST for NF1/NF2 details.

> Per `CLAUDE.md` §10 step 5: scaffold the manifest, then post this list to
> John, then wait for ack before proceeding past commit 1.
>
> Status: **pre-staged**. Posts the moment artifacts #2 + #5 + amended CLAUDE.md
> are all in place and no new ambiguities surface. Adjustments expected after
> reading #2 (architecture confirmation) and #5 (real $-values).

---

## Commit cadence

Per Q20 locked decision: **per-phase ack, intra-phase autonomous**. So the 5
commits below get posted as a plan once; John acks once; the 5 commits land
sequentially without per-commit pause. Written commit-log summary at end of
the scaffold session. Architecture-touching surprises break the cadence and
raise to John mid-phase.

---

## Commit 1 · Manifest + module skeleton

```
chore(southbrook_estimating): scaffold v19.0.1.0.0 manifest + directory tree

- __manifest__.py with dependency list:
  product_configurator
  product_configurator_mrp
  product_configurator_sale
  + Odoo core: sale_management, mrp, account, stock, contacts
- Empty __init__.py at root + models/
- security/ir.model.access.csv stub (no rules yet)
- README.md pointing to ~/southbrook-v19cr/CLAUDE.md + the SAMI build spec
  as canonical design docs (per CLAUDE.md §9 acceptance criterion)
- Same skeleton for southbrook_estimating_website (depends on
  southbrook_estimating + website_product_configurator + portal)
```

**What it does NOT include:** no models yet, no data, no views. Pure skeleton.
Validates that `odoo-bin -i southbrook_estimating,southbrook_estimating_website
--stop-after-init` installs cleanly on a fresh 19.0 CE database with the four
OCA modules.

**Files:** 8 (2 manifests, 2 root __init__, 2 models/__init__, 2 README.md).

---

## Commit 2 · res.partner channel + tradesperson_tier fields

```
feat(southbrook_estimating): add res.partner.channel + tradesperson_tier fields

- models/res_partner.py: channel selection (6 values per Q1/Q5/Q21)
  retail / dealer / tradesperson / kd / bigbox / refacing
- tradesperson_tier selection (1/2/3), visible only when
  channel = tradesperson
- views/res_partner_views.xml: surface both fields in the Partner form
- security ACLs extended (read for portal user, write for manager)
- tests/test_partner_channel.py covers the channel + tier field roundtrip
```

**Why second:** the pricelist resolution (commit 4) reads from these fields.
Need them in place first. Tiny commit — 4 files, ~80 LoC.

---

## Commit 3 · The 11 (+2) attributes

```
feat(southbrook_estimating): seed 11 configurator attributes + 13 values

- data/attributes.xml: 11 user-facing + 2 derived per Q2/Q22/Q23
  - 11 user-facing per Mapping §3.3
  - door_count (Q22 assumption (a) — hidden, drives BoM)
  - family_subtype (Q23 assumption (b) — scoped to family=corner)
- All attributes use create_variant='dynamic' per Q6
- value_inches + value_mm on width values: COMMENTED placeholder until the
  Q3 product_attribute_value extension lands (commit 5)
- tests/test_attributes.py: every attribute creates, every value resolves,
  display_type renders
```

**Promotion from `docs/drafts/attributes_DRAFT.xml`** — mechanical copy after
ack. The draft is parse-validated (58 records).

**Adjustments after #5 lands:** finish values populated, handle values populated,
real $-on-maple price_extra figure.

---

## Commit 4 · The 6 channel pricelists

```
feat(southbrook_estimating): seed 6 channel pricelists per Q1/Q5

- data/pricelists.xml: 6 product.pricelist records
  southbrook.pricelist.retail (base, list ×1.00)
  southbrook.pricelist.dealer (list ×0.50)
  southbrook.pricelist.tradesperson (cost ×1.05, tier-driven discount)
  southbrook.pricelist.kd (~46% of retail, component-only)
  southbrook.pricelist.bigbox (fixed $65 cost / $98 retail)
  southbrook.pricelist.refacing (35% margin-target computed)
- models/sale_order.py: _resolve_channel_pricelist override (custom routine
  #3 from Mapping §5) — partner.channel → pricelist
- models/product_pricelist.py: _compute_refacing_price computed field
  (custom routine #2)
- tests/test_pricelist_resolution.py: assigning res.partner.channel
  resolves to the correct pricelist on sale.order creation
- tests/test_refacing_margin.py: refacing channel hits 35% margin target
```

**Adjustments after #5 lands:** real per-SKU $-values for the bigbox channel,
real margin-target inputs for refacing.

---

## Commit 5 · The four declarative config rules + lead_time_extra + override stub

```
feat(southbrook_estimating): seed 4 config rules + lead_time_extra + override stub

- data/config_rules.xml: ~65 records implementing the four rules per
  Mapping §3.4 (Q22(a) + Q23(b) draft assumptions):
  - Rule 1: Series → door style (20 records: 10 templates × 2 series)
  - Rule 2: Box material → series (24 records: 12 templates × 2 series)
  - Rule 3: Width → door count (20 records, hidden attribute pattern Q22(a))
  - Rule 4: Family → soft-close (1 record, accessory restriction)
- models/product_attribute_value.py: lead_time_extra Float field
  (custom routine #4 per Build Spec §4 / PUNCHLIST Q3)
- models/mrp_bom.py: lead_time_extra rollup into produce_delay
  (stub for commit 6's _compute_panel_dimensions)
- models/product_config_line.py: ConfigurationError override STUB
  (NF2 — Build Spec §9.1). Returns the upstream dict-format unchanged
  today; positioned for raise-with-reason if OCA upstream switches.
  Zero functional change in Phase 1; safety hatch per CLAUDE.md §7.7.
- tests/test_config_rules.py: every rule fires on the correct trigger,
  blocks the correct combinations; reason exposed via the
  validate_configuration return-dict
```

**Promotion from `docs/drafts/config_rules_DRAFT.xml`** — currently 19 records
showing the pattern for `wall_1dr`; promotion expands to ~65 records covering
all 10/12 templates.

**Generation strategy:** macro-style expansion via short Python script (~20
LoC) that emits `data/config_rules.xml` from a 4-row data file. Hand-authored
XML for 65 records is grep-friendly but error-prone; a generator avoids
copy-paste drift. Decision deferred to commit-author moment — depends on
how readable the hand-authored 19-record draft looks to John.

---

## Commit 6 · `southbrook.order.analytics` companion model

```
feat(southbrook_estimating): add southbrook.order.analytics companion record

- models/southbrook_order_analytics.py: 9-field model per Build Spec §8
  (channel, series, tradesperson_tier, dealer_id, quoted_at, confirmed_at,
  production_start_at, production_end_at, cabinet_count, panel_count,
  door_count, nest_yield_pct)
- 1:1 relation to sale.order via sale_order_id Many2one
- models/sale_order.py: _inherit on action_confirm writes the analytic
  record at confirm-time. Field values rolled up from existing
  res.partner + sale.order.line.product_id + mrp.production fields —
  no new business rule
- tests/test_analytics_capture.py: confirming a sale.order writes the
  expected analytic tags

NF1 — surfaces ack question: does this thin model count as routine 8?
My read: NO (data capture, not logic). If John acks YES, the
register-grows-to-8 entry goes in PUNCHLIST with justification per
Build Spec §4 boundary rule.
```

**Why commit 6, not earlier:** the analytic capture hook reads from
`sale.order.line.product_id` which only resolves once templates exist (commit 7
in the original plan, now shifted to commit 7+). Commits 1-5 don't need
analytics. Adding it after commit 5 means the analytic record is in place
before the smoke-test order in commit 10, satisfying §2.1's "captured from day
one" requirement.

---

## What's NOT in the first 6

Deferred to commits 7-N (still Phase 1, but later in the sequence):

- **Commit 7 · The 12 cabinet templates** with attribute_line bindings per Q8
- **Commit 8 · `_compute_panel_dimensions`** (custom routine #1) + parametric
  BoM rollup tests
- **Commit 9 · Order Builder views** (multi-zone grid, inline config drawer,
  BoM preview tab, validation tab, stage pipeline) per Brief §2.2
- **Commit 10 · The Phase-1 smoke test** (Mapping §6 step 1-10 codified as
  `tests/test_phase1_smoke.py`)
- **Commit 11 · Demo data** (Richwood + Demo Tradesperson partners, 9-line
  reference order)

Phase 1 gate (Brief §8) reached at commit 10. John reviews on live Odoo 19 CE
instance → ack → Phase 2 begins.

---

## Acceptance evidence I'll capture per commit

Each commit's PR description (or commit message body if no PR) carries:

- [ ] Files changed / created / deleted
- [ ] `pre-commit run -a` clean output
- [ ] `odoo-bin -i southbrook_estimating --test-enable --stop-after-init`
      exit code 0 + test count
- [ ] PUNCHLIST Q-numbers exercised (e.g. "Encodes Q1, Q5, Q21")
- [ ] Any new ambiguities surfaced (none expected in commits 1-5; surface
      otherwise)

---

## What I need from John before commit 1 ships

1. **Artifact #2** — SAMI Build Spec, to confirm dependency list (manifest)
   and any architecture I've inferred but not seen
2. **Artifact #5** — Consolidated Dataset xlsx, for the real $-values in
   commits 3 (price_extra on maple) and 4 (pricelist multipliers)
3. **Amended CLAUDE.md** with Q1/Q2/Q3/Q5 corrections folded
4. **Q22 ack** — door_count as hidden attribute (a) vs computed BoM field (b)
5. **Q23 ack** — family_subtype sub-attribute (b) vs family value split (a)

Items 1-3 unblock the scaffold; items 4-5 confirm or flip the draft
assumptions in `attributes_DRAFT.xml` and `config_rules_DRAFT.xml`.
