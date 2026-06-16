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
