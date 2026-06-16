---
slug: 03_attributes
title: Configuration Attributes
source: canonical
version: 1
audience: [trade_partner, sales_rep]
last_reviewed: 2026-06-16
related_generated: [03_attributes.generated.md]
---

# Configuration Attributes

Every cabinet template carries up to 16 configurable dimensions. The
live enumeration of values per attribute is maintained in
`03_attributes.generated.md`, rebuilt from `product.attribute` and the
`product.config.line` restriction rules.

## The 16 attributes

| Attribute | What it controls |
|---|---|
| Family | Which catalog family (Base, Wall, Tall, Vanity, Accessory). |
| Width | Cabinet width in inches. Snaps to a per-template enumeration. |
| Series | Quality and lead-time tier (Contractor, Contemporary, Elegance, Signature). |
| Box material | Carcass material (White Melamine, Maple). |
| Door style | Slab, Shaker, Raised Panel, Five-Piece, Custom, Beadboard, Mullion, V-Groove, Reeded, Thermofoil. |
| Finish | Surface treatment (White, Maple Stain, Cherry, Walnut, Custom). |
| Hinge side | LH, RH, or N/A. |
| Finished sides | None, Left, Right, Both. |
| Gables | Standard, Finished, Decorative. |
| Handle | Bar Pull, Knob, Cup Pull, Integrated, None. |
| Accessories | Soft-Close, Drawer Organizer, Pull-Outs (multi-select). |
| Door count | 1 or 2 (driven by width on most families). |
| Frame style | Framed (Traditional) or Frameless. |
| Door overlay | Full Overlay, Partial Overlay, Full Inset, Beaded Inset. |
| Wood species | Maple, Cherry, Red Oak, White Oak, Walnut, Alder, Hickory, MDF (Painted). |
| Pull finish | Polished Chrome, Brushed Nickel, Matte Black, Antique Bronze, Brushed Gold, Oil-Rubbed Bronze, Champagne Bronze, Polished Brass. |
| Door edge profile | Square (Eased) or Eased. |

## Series — the primary tier signal

- **Contractor** — entry-level, highest volume, shortest lead time.
  White Melamine box mandatory. Limited door styles (no Five-Piece).
- **Contemporary** — mid-range. Broader door style options. Both
  box materials available.
- **Elegance** — upper-mid. Full door style range. Soft-close standard.
- **Signature** — premium. Solid-wood frames, soft-close, lifetime finish
  warranty, flat-pack shipped. Maple box mandatory. Longest lead time.
  Full attribute range unlocked.

## Restriction rules (enforced by `product.config.line` rules, never Python)

1. Door Style = Thermofoil ⇒ Series must be Contractor.
2. Door Style = Five-Piece ⇒ Series must be Elegance.
3. Box Material = White Melamine ⇒ Series is Contractor (or any series
   that explicitly allows White Melamine).
4. Box Material = Maple ⇒ Series is Signature.
5. Width 9–21" ⇒ Door Count = 1; Width 24–36" ⇒ Door Count = 2.
6. Family = Bi-fold Corner ⇒ Soft-Close option is hidden.

When a configuration violates a rule, the offending option is
**unselectable** in both the customer and sales-rep UIs.
