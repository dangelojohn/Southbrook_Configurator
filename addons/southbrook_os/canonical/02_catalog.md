---
slug: 02_catalog
title: Cabinet Catalog
source: canonical
version: 1
audience: [trade_partner, sales_rep]
last_reviewed: 2026-06-16
related_generated: [02_catalog.generated.md]
---

# Cabinet Catalog

Every Southbrook cabinet is a configurable template. The catalog is
organized into five families. The live SKU list and price master are
maintained in `02_catalog.generated.md`, which is rebuilt nightly from
the Odoo `product.template` records.

## Families

### Base cabinets

Floor-standing, counter-height units. The workhorse of the kitchen.
Includes single-door, double-door, drawer banks, sink bases, and
specialty bases (cooktop, tray divider, wine rack, pull-out trash,
pull-out spice).

### Wall cabinets

Upper, wall-mounted units. Single-door, double-door, glass-door, open
shelf, microwave, refrigerator bridge, range hood.

### Tall cabinets

Full-height pantry and specialty. Includes the pull-out pantry and the
broom/utility tall.

### Vanity cabinets

Bathroom-specific. Single-door, double-door, drawer bank variants.

### Pull-outs & specialty

Worktops, toe kicks, accessories, decorative end panels.

## How a partner picks

Selection happens in the Order Builder (`/my/southbrook/order-builder/<id>`)
via the five-step configurator wizard:

1. Pick a template (e.g., `SB-BASE-2DR`).
2. Set construction and sizing (width, series, box material).
3. Choose door and finish (door style, finish).
4. Set hardware and sides (hinge side, finished sides, gables, handle).
5. Pick accessories (soft-close, drawer organizer, pull-outs).

The 3D Kitchen Preview updates live. Validation runs silently in the
background. The order line is added to the appropriate zone (Base Run,
Wall Run, Tall Run, Island, Accessory, Other) with a retail price and an
optional channel price.
