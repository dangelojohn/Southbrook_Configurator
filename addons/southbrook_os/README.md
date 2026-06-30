# Southbrook OS

The canonical, version-controlled, governed knowledge layer of the
Southbrook platform. See `docs/superpowers/specs/2026-06-16-southbrook-os-and-hermes-platform-design.md`
for the design and `docs/superpowers/plans/2026-06-16-southbrook-os-v1.md`
for the v1.0 build plan.

Hand-curated content lives under `canonical/`. Odoo-generated content lives
under `generated/`. Governance happens through `southbrook.os.revision`
records (OSROs); dated snapshots live in `southbrook.os.publication`.

Public read endpoint: `GET /southbrook/os.json`.
