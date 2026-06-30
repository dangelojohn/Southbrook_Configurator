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
