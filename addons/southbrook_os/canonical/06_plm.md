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
