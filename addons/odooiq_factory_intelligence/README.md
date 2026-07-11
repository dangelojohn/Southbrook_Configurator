# OdooIQ Factory Intelligence

A machine-agnostic **manufacturing intelligence layer** for Odoo 19 Community.
It turns any shop's standard MRP data into a delivery-confidence, explanation and
data-health product — without mutating a single MRP record (read-only observer).

> *Odoo tells you what exists. OdooIQ tells you what will happen and what to do next.*

## Status — Step 1 of the build sequence

This build ships the **Factory Intelligence Audit + Readiness engine** (the
acquisition wedge):

- `oiq.factory.audit` / `oiq.factory.audit.finding` — a point-in-time data-health
  run and its line-item findings.
- `oiq.scheduling.intelligence` — the engine service seam. `analyze(company)`
  computes the structural signals **S1–S7** (routing coverage, work-center
  assignment, time realism, calendars, capacity, **date authenticity**, overload)
  and the behavioral signals **B1–B4** (locked until history accrues), then
  reports a **Readiness Level 1–5** (Blind → Structured → Observed → Calibrated →
  Predictive).

Output framing rule: never a bare "42%" — always a Readiness Level plus the top
fixes and their expected improvement.

Later steps (per the full spec) add the shadow scheduler, calibration engine
(the moat), delivery-confidence ranges and the AI advisor — all behind the same
`oiq.scheduling.intelligence` service seam.

## Design invariants

- **Read-only vs MRP** — never writes `mrp.production` / `mrp.workorder` / `mrp.workcenter`.
- **Machine-agnostic** — depends only on `mrp`; soft-detects and enriches from
  Southbrook models when present, but never requires them.
- **CE-native, LGPL-3** — no OPL-1 vendor dependency.

## Tests

```bash
odoo -d <db> -u odooiq_factory_intelligence --test-enable \
  --test-tags=/odooiq_factory_intelligence --stop-after-init
```

Canonical design docs: `OdooIQ_Factory_Intelligence_Engine_Full_Spec.md`.
