# Southbrook OS v1.0 — Canonical Content Seed

> **Purpose.** Companion to `2026-06-16-southbrook-os-v1.md`. Provides the
> verbatim initial content for `addons/southbrook_os/canonical/*.md` so the
> implementer doesn't have to invent it. Each section below is one file —
> copy as-is.
>
> **Source.** Derived from the 63-step Southbrook Cabinetry OS narrative
> supplied in the 2026-06-16 brainstorm session, condensed and split into
> agent-friendly markdown sections with YAML frontmatter.

---

## File 1 — `canonical/00_charter.md`

```markdown
---
slug: 00_charter
title: Southbrook Cabinetry — Charter
source: canonical
version: 1
audience: [trade_partner, sales_rep, mfg_manager, public]
last_reviewed: 2026-06-16
---

# Southbrook Cabinetry — Charter

Southbrook Cabinetry is a configure-to-order, make-to-order cabinet
manufacturer that sells through an approved trade partner network
(contractors, designers, Tier 3 tradespersons), accepts orders exclusively
through its online Trade Portal, and manufactures each kitchen to exact
customer specifications through a linear production line from CNC nesting
to packing.

## Who we are

- A configure-to-order cabinet manufacturer.
- A trade-only seller — we never sell direct to the public.
- A vertically integrated shop — design, engineering, manufacturing, and
  install support all live under one roof.

## What we do not do

- We do not stock SKUs. Every cabinet is built to the customer's spec.
- We do not run a public e-commerce catalog. The catalog exists, but it
  is accessed only through an approved partner's portal session.
- We do not handle financing or refacing as a standalone business in v1
  of the Operating System scope.

## What this OS is for

This document is the canonical, version-controlled description of how
Southbrook works as a business. It is the source of truth for:

- **Hermes**, our AI assistant, which grounds every answer in this OS.
- **New employees**, who use it as the onboarding read.
- **Trade partners**, who use it (through the public viewer) as the
  reference for what we offer and how we work.
- **Investors and auditors**, who use the dated publications as the
  documented record of how the business operated at any point.

Changes to this OS go through OS Revision Orders (OSROs) — the same kind
of governed change process we apply to our Bills of Materials and Cut
Specifications.
```

---

## File 2 — `canonical/02_catalog.md`

```markdown
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
```

---

## File 3 — `canonical/03_attributes.md`

```markdown
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
```

---

## File 4 — `canonical/04_lifecycle.md`

```markdown
---
slug: 04_lifecycle
title: Order Lifecycle
source: canonical
version: 1
audience: [trade_partner, sales_rep, mfg_manager]
last_reviewed: 2026-06-16
---

# Order Lifecycle

Every order travels through eight defined stages.

## Stages

| # | Stage | What it means |
|---|---|---|
| 1 | Draft | Partner is actively configuring. No commitment. |
| 2 | Estimating | Partner clicked "Send to Production." Southbrook's estimating team reviews and validates. |
| 3 | Approval | Internal sign-off. CAD and cutlist must be approved. BoM confirmed. |
| 4 | Confirmed | Locked. Manufacturing Orders are generated. Work Orders assigned. |
| 5 | In Production | Active manufacturing. Real-time tracking via Kitchen Job Command Center. |
| 6 | Quality Control | Final QC. |
| 7 | Delivery | Packed by project/room, shipped flat-pack. |
| 8 | Install | On-site install support if contracted. |

## What a partner can change at each stage

| Stage | Attribute changes | Quantity changes | Door/finish swaps | Cancellation |
|---|---|---|---|---|
| Draft | yes | yes | yes | yes |
| Estimating | yes — produces v2 | yes | yes | yes (no fee) |
| Approval | rep-mediated | rep-mediated | rep-mediated | yes (no fee) |
| Confirmed | request only — via OSRO-like flow | request only | request only | yes (with cancellation fee) |
| In Production | no — production has started | no | no | yes (with fee + may be partial) |
| QC / Delivery / Install | no | no | no | only by full return |

## Order Builder data structure

Each order in the portal is a `sale.order` record carrying:

- Order number (`S0XXXX`).
- Customer + version (`v1`, `v2`, `v3` after revisions).
- Invoice address / delivery address.
- Quotation date / expiration date / payment terms.
- Pricing channel (Retail or Channel).
- Retail subtotal / channel total / savings / lead time.
- Order lines grouped by zone (Base Run, Wall Run, etc.).

Each order has six visible tabs: **Order Lines**, **3D Kitchen**, **BOM
Preview**, **Validation**, **History**, **Customer Print**.

## Standard lead time

Two weeks from confirmation for Contractor / Contemporary / Elegance
series. Signature series adds two weeks. Maple box on any series adds
two weeks. These are rules of thumb — the live lead-time computation in
the Order Builder is authoritative.
```

---

## File 5 — `canonical/07_partner_faq.md`

```markdown
---
slug: 07_partner_faq
title: Partner FAQ
source: canonical
version: 1
audience: [trade_partner]
last_reviewed: 2026-06-16
---

# Partner FAQ

Twenty common partner questions and the canonical answer. Hermes will
match against these to keep its tone consistent.

## Where is my kitchen?

Look at the order's PM Phase in the Kitchen Job Command Center.
The phases are Design & Quote → Cutting & Machining → Assembly →
Finishing → Delivery & Install. For confirmed orders, the Kitchen Job
also surfaces a Manufacturing Reality line ("6 Confirmed; 47 WOs / 39
not scheduled") and a current bottleneck work center. Hermes can read
all of this and translate it to plain language on request.

## What's blocking my install?

The Kitchen Job's "Top Blocker" field carries this directly. Common
blockers: CAD approval pending, cutlist not validated, components not
available, doors back-ordered, finished panels not yet finished.

## Can I still change the door finish on a confirmed order?

Confirmed orders are technically locked, but a request to change a
finish goes through the recommendation flow — Hermes can draft the
request and your sales rep approves it. Whether the change is actually
possible depends on whether your kitchen has cleared the Finishing stage.
If it has, the change becomes a partial remake at additional cost.

## When will my install be ready?

The Kitchen Job carries `install_due`. The risk flag (`On Track`, `At
Risk`, `Blocked`) tells you whether that date is currently believable.
"At Risk" means the install date is in the calendar but at least one
upstream blocker exists that would have to clear immediately to hold it.

## What does Series=Signature mean for my order?

Signature is our premium tier. It mandates a Maple box, ships flat-pack,
adds 2 weeks of lead time over our standard 2 weeks, and unlocks the
full attribute range (all door styles, all finishes, all wood species).
Pricing is roughly 1.4–1.6× Contractor for the same shape.

## Why is Cherry costing more than Maple on my Signature?

Wood species pricing scales with material cost. Cherry, Walnut, and
White Oak typically run 15–25% above Maple. The Order Builder shows
the per-line uplift; your dealer pricelist may bury some of it under a
channel discount.

## I selected Five-Piece doors but the configurator now says I need
Elegance series. Why?

Rule R2: Five-Piece doors are only manufactured on the Elegance series.
Switching series will re-price your line. The configurator blocks the
combination so you can't accidentally promise a customer something we
can't make.

## Where do I see the BoM for my order?

Order Builder → BOM Preview tab. The BoM updates live as you change
attributes. It shows the carcass panel list, the door schedule, and
the hardware pick list. It's also what the shop floor will use to cut
your panels — so what you see is what gets manufactured.

## Can I get a PDF of the spec sheet to send my customer?

Order Builder → Customer Print. There are two prints: a customer-friendly
"Signature Series" PDF, and a separate Door Order print for production.
Hermes can resend either to your own email via `send_spec_pdf_email`.

## My customer wants to reschedule install — what do I do?

Hermes can draft a reschedule request from any Confirmed-or-later order.
The request goes to your sales rep, then to manufacturing. If the new
date is achievable (work-center capacity + dispatch slots), it gets
approved without you doing anything else.

## Why did you cancel my draft revision?

Drafts auto-expire after 30 days if not approved. If you want to revive
one, your sales rep can duplicate it as a new v2.

## What does "Carcass Assembly" mean in the Kitchen Job?

It's the work center where the cabinet box (carcass) is built from the
panels we cut at CNC. It's the most common bottleneck in our shop, so
Kitchen Jobs often surface it as the Top Blocker even when other
stations are also behind.

## What if I disagree with the price?

The price is computed from the live pricelist + channel discount +
attribute uplifts. If it looks wrong, contact your sales rep — they can
see the breakdown and adjust if there's an error. Hermes will not
negotiate pricing.

## Can I add a custom cabinet outside the catalog?

Not directly through the configurator. Request a Custom line through
your sales rep. Custom lines route through Engineering before pricing.

## My quote expired — does that mean I lost the design?

No. Configurations are saved as `product.config.session` records and
the quote can be re-issued as a new version. Your sales rep can
duplicate-as-draft.

## How do I know if a configuration violates a rule?

The Validation tab in the Order Builder. Hard violations are blocking
(red); soft suggestions are advisory (yellow). Hermes can list current
violations via `get_order_line` and explain which rule was hit.

## What's the difference between Retail and Channel pricing?

Retail is list price. Channel is your dealer-specific pricelist (Dealer
−50%, Contractor tier-discount, etc.). The Order Builder shows both
side-by-side with a Savings column.

## When do I owe payment?

Payment terms are set on the order header. Standard is 50% deposit
on Confirmation, 50% on Delivery. Some channels (Big-Box wholesale)
have different terms.

## Can I see my orders from last year?

Yes — list filter on the My Orders page, or ask Hermes to list. Hermes
can summarize trends ("you confirmed 14 orders last quarter, average
deal $28K").

## Why is my Kitchen Job showing 39 unscheduled work orders?

That means manufacturing has confirmed the MOs but hasn't yet pinned
each Work Order to a specific time slot. This is normal in the first
few days post-confirmation; the scheduling cron runs nightly to lay
them out. If the count doesn't drop within 3 business days, that's a
real bottleneck signal — Hermes can flag it via the Kitchen Job's
`unscheduled_wos` field.
```

---

## File 6 — `canonical/01_company.md` (stub for v1.0)

```markdown
---
slug: 01_company
title: Customers, Tiers, and Partner Network
source: canonical
version: 1
audience: [trade_partner, sales_rep]
status: stub
last_reviewed: 2026-06-16
---

# Customers, Tiers, and Partner Network

> **Status: stub.** This section is scheduled for an expanded OSRO in
> v1.1. v1.0 ships the high-level structure so Hermes has a section to
> point at when partners ask about their tier.

Southbrook operates an approved trade partner network. The portal is
not open to the public. Three customer types exist:

- **Retail (List Price)** — direct trade partners at full retail.
- **Channel** — approved dealers with negotiated channel discount.
- **Tier 3 Tradesperson** — entry-level partners on the tradesperson
  channel with tier-graduated discounts.

CRM pipeline: New → Qualified → Proposition → Won / Lost.

OSRO needed to populate: tier graduation criteria, partner onboarding
flow, channel pricelist matrix, dealer agreement summary.
```

---

## File 7 — `canonical/05_production.md` (stub for v1.0)

```markdown
---
slug: 05_production
title: Manufacturing and Production Control
source: canonical
version: 1
audience: [trade_partner, sales_rep, mfg_manager]
status: stub
last_reviewed: 2026-06-16
related_generated: [08_work_centers.generated.md]
---

# Manufacturing and Production Control

> **Status: stub.** This section will be expanded by OSRO before v1.2
> (manufacturing-manager Hermes surface) ships. v1.0 ships the
> high-level taxonomy so Hermes can mention bottlenecks meaningfully
> to trade partners.

A confirmed order generates Manufacturing Orders (one per distinct SKU
line). Each MO references the SKU's Canonical BOM. Work Orders are
generated from the Kitchen Operation Templates (15 routing steps from
Design Review to Packing), each assigned to its appropriate Work Center.

The Kitchen Job Command Center aggregates all MOs and WOs for a single
customer order into one management surface, exposing:

- PM Phase, Manufacturing Reality, Readiness Decision (Blocked / At
  Risk / On Track), Readiness Score (0–100), Top Blocker, Next Best
  Action.
- Current Bottleneck Work Center, Cabinet Mix, CAD Status, Components.
- MO references and counts.

The most common system bottleneck is Carcass Assembly. The live work
center status is in `08_work_centers.generated.md`.
```

---

## File 8 — `canonical/06_plm.md` (stub for v1.0)

```markdown
---
slug: 06_plm
title: PLM and Change Management
source: canonical
version: 1
audience: [sales_rep, mfg_manager]
status: stub
last_reviewed: 2026-06-16
---

# PLM and Change Management

> **Status: stub.** v1.0 ships the ECO taxonomy so Hermes can mention
> ECOs in conversation. The full Engineering OSRO will populate the
> rest before v1.3.

Southbrook's PLM covers four kinds of Engineering Change Orders:

- **Template BoM Revision** — changes to a Canonical BOM.
- **Cut-Geometry Revision** — changes to the parametric Cut Specification.
- **Construction-Rule Change** — changes to configuration restriction rules.
- **Parametric Cut Spec** — specific dimensional parameter changes.

ECO stages: Draft → Under Review → Approved → Applied → Rejected.

When an ECO is Applied, the ProductGraph sidecar (if linked) is
auto-released. Cut-Geometry Revisions affect only orders confirmed
after the apply — in-flight orders are pinned via the cut-spec snapshot
on `sale.order.line`.
```

---

## File 9 — `canonical/20_systems_topology.md` (stub for v1.0)

```markdown
---
slug: 20_systems_topology
title: Systems Topology
source: canonical
version: 1
audience: [mfg_manager, overseer]
status: stub
last_reviewed: 2026-06-16
---

# Systems Topology

> **Status: stub.** Populated in v1.x when the Overseer Hermes ships.
> v1.0 includes only the bare topology so the section exists.

Southbrook runs on a QNAP-hosted Odoo 19 CE stack:

- `southbrook-odoo` container, on the `alfacore-caddy` shared network.
- `southbrook-postgres` companion (postgres:16).
- Cloudflare tunnel fronts the public site at
  `southbrookcabinetry.space`.
- Deploys via `scripts/deploy_to_qnap.sh` (LAN or cloudflared tunnel).

Multi-tenant context: Southbrook is one of seven Odoo tenants on the
QNAP. Others: Porterly, Sapienzium, Tribancs, OdooIQ, Quattroporte,
OdooAI, AlfaCore. Each tenant is structurally isolated; the Hermes
sidecar (and the Overseer, when it ships) route by `tenant` claim.
```

---

## File 10 — `canonical/99_glossary.md`

```markdown
---
slug: 99_glossary
title: Glossary
source: canonical
version: 1
audience: [trade_partner, sales_rep, mfg_manager]
last_reviewed: 2026-06-16
---

# Glossary

Authoritative definitions for terms used across Southbrook.

- **BoM (Bill of Materials)** — the structured component list for a
  configured cabinet. Generated per variant by
  `product_configurator_mrp` from the Canonical BoM template.

- **Canonical BoM** — the master BoM record per SKU, named
  `[SKU]-Canonical: [Full Product Name]`. Referenced by every
  Manufacturing Order built from that SKU.

- **Cut Specification (Cut Spec)** — the parametric document that
  governs all cabinet dimensions: box thickness, back-panel thickness,
  rabbet depth, door thickness, door reveal, shelf tolerance, vent
  gap, toe-kick height. Active version is the one production cuts to.

- **ECO (Engineering Change Order)** — a governed change request
  against a BoM, a Cut Spec, a Construction Rule, or a document.
  Stages: Draft → Under Review → Approved → Applied.

- **Kitchen Job** — a `project.task` record that aggregates all MOs
  and WOs for a single customer order. The shop-floor management view.

- **MO (Manufacturing Order)** — `mrp.production` record. Created
  automatically when a sale order is confirmed. References the
  Canonical BoM.

- **OSRO (OS Revision Order)** — governed change to the canonical OS
  narrative. Same state machine as ECO. Bumps the OS section version
  on apply.

- **Order Builder** — the portal SPA at
  `/my/southbrook/order-builder/<id>` where trade partners configure
  and submit orders.

- **Publication** — a dated snapshot of the entire OS. Identified by
  a calendar string (e.g., `2026-06`) plus a build hash. A confirmed
  sale order pins to one.

- **Series** — the primary tier signal: Contractor, Contemporary,
  Elegance, Signature.

- **Tier (partner)** — partner-network level: Tier 1 (top-volume
  dealers), Tier 2, Tier 3 (entry tradesperson).

- **WO (Work Order)** — `mrp.workorder` record. Generated from
  Kitchen Operation Templates when an MO is created. Each WO is
  assigned to one Work Center.

- **Work Center** — `mrp.workcenter` record representing a station
  on the production line (Panel Saw, CNC Boring, Edge Bander, Carcass
  Assembly, Door Hanging, Hardware Fitting, Paint Booth, QC, Pack &
  Label, etc.).

- **Zone** — selection field on `sale.order.line` grouping lines by
  kitchen area: `BASE_RUN`, `WALL`, `TALL`, `ISLAND`, `ACCESSORY`,
  `OTHER`. Drives the Order Builder grid layout.
```
