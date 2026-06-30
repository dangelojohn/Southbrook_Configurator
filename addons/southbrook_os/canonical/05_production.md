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
