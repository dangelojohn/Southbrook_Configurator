---
course: 17
chapter: 17.13
title: Design — Add a New SKU to the Catalog
duration: 4
audience: Designer / product manager adding a new cabinet template or accessory
jtbd: add a new SKU to the catalog
department: Design / Engineering
custom_modules: southbrook_estimating, product_configurator, southbrook_hardware_catalog
---

# Design — Add a New SKU to the Catalog

## When you use this

A new cabinet template (e.g. an island variant) or a hardware accessory
that doesn't exist in the current catalog. The Order Builder relies on
these `product.template` records; nothing else needs editing for the new
SKU to appear.

## The 5-step flow

1. **Decide: cabinet or accessory.** Cabinets get a `product.template`
   with the 11 attributes wired in. Accessories use
   `southbrook_hardware_catalog` (Marathon catalog).
2. **For cabinets:** *Inventory → Products → New*. Use the *Southbrook
   Series* tab (added by `southbrook_estimating`). Fill family, default
   dimensions, default series, declare which of the 11 attributes
   apply.
3. **For accessories:** *Inventory → Products → Hardware Catalog → New*.
   Fill brand (Marathon, Blum, etc.), SKU code, MSRP, your cost.
4. **Pricelist seeding.** Auto-creates pricelist items at retail; channel
   pricelists derive from retail via formula. Verify by opening *Sales →
   Configuration → Pricelists*.
5. **Demo the new SKU.** Open the Order Builder, try to configure it. If
   exclusions fire incorrectly, edit `data/config_rules.xml` (see
   declarative rules audit).

## What you should NOT do

- Don't write Python overrides for the new SKU. Rules go in
  `product.config.line` records, declaratively.
- Don't add the new SKU to a pricelist by editing pricelist XML — use
  the pricelist UI so it picks up the audit chatter.
- Don't skip the 11-attribute declaration — the Order Builder hides
  cabinets without it.

## Common gotchas

- **New cabinet doesn't appear in Order Builder** — check that
  `is_published=True` on `product.template` and that the family is in the
  Order Builder's family filter.
- **New cabinet appears but configurator wizard skips half the
  attributes** — the missing attributes weren't enabled on the template.
- **Hardware item shows wrong vendor price** — Marathon CSV import may
  have lagged; *Inventory → Configuration → Hardware Catalog → Re-import*.

## Deep dive

→ Course 11 *Creating a New Product End-to-End* — all 8 lessons
→ Course 5 lesson 5.3 *Hardware Catalog*
