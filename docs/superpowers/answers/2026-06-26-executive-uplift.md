# Phase 0 Scoping Answers — Executive Uplift to ≥7/10

**Date:** 2026-06-26
**Source:** chat with project owner (John D'Angelo)

| ID | Question | Answer | Implication |
|---|---|---|---|
| Q-01 | Edition: CE or EE | **Odoo 19 CE** | Phase 3/4 take CE path. No Enterprise-only modules (account_accountant, l10n_ca_hr_payroll, etc.). |
| Q-02 | Time/budget envelope | **Now — start immediately** | Aggressive cadence, parallel agents OK. |
| Q-03 | Target customer | **B — positioning for SAMI-class licensee** (Mattamy/Tridel/Brookfield) | Executive demo polish weights higher than internal tooling. Mobile GM dashboard, Bottleneck Report, Canadian compliance are top-priority. |
| Q-04 | Hosting model | **Stay on current QNAP for now; production will move to large VPS + RAG + self-hosted Qwen + MCP-into-Odoo** | Phase 9 Ops hardening targets the QNAP for the demo; the VPS migration is a separate post-uplift workstream. MCP scaffolding lands in Phase 5. |
| Q-05 | Live DB vs dev DB | **Build straight on live `southbrook` DB with backup safety net** | Every destructive step preceded by a fresh `backup-odoo.sh`. |
| Q-06 | Mattamy / builder EDI | **Skip — deferred post-deployment** | Phase 5 EDI work descoped. |
| Q-07 | Azure AD SSO | **Skip — deferred** | Phase 5 SSO work descoped. |
| Q-08 | Homag iX present | **NO — simulate data + scenarios** | Build a Homag *simulator* sidecar; bidirectional surface stays buildable + testable. |
| Q-09 | CSA A277 in scope | **Skip — not now** | Phase 2 stays cabinetry-only. As-built record (W-08) becomes a v2 line item. |
| Q-10 | frePPLe? | **No frePPLe** | MRP/MPS uplift uses native Odoo MPS + work-center capacity hard-block. |
| Q-11 | Pre-existing l10n_ca data | **Default: greenfield seed** (not specified by user; will confirm at first Phase 4 step) | Clean CoA install; no migration tasks. |
| Q-12 | Final acceptance authority | **Default: self-attested via 3-agent re-score** (not specified) | Phase 10 gate is automated; final scorecard delivered to John for review. |

## Rebalanced Pillar Coverage Given Descopes

| Pillar | Originally relied on | Now lifted by |
|---|---|---|
| Integrations (3 → 7) | Azure AD SSO + EDI + Homag + 3PL + IoT | **Homag simulator + 3PL ASN + MCP-server-into-Odoo + IoT label printer config + REST `southbrook_api` polish** |
| HR/Payroll (3 → 7) | EE `l10n_ca_hr_payroll` | **OCA `payroll_canada` (or hand-rolled CE rule set) + WSIB calc model + cert expiry tracking** |
| Finance (4 → 7) | EE `account_accountant` | **CE `l10n_ca` CoA + HST/GST taxes + manual WIP report + CCA on `account.asset` (native CE) + budget tile on MI engine** |
| Quality (3 → 7) | EE `quality_control` | If installable on CE → use it. If not → custom `southbrook_quality` addon with NCR + SPC + FPY |
| MRP/MPS (5 → 7) | frePPLe sidecar | **Native `mrp_mps` (CE) + work-center capacity hard-block via `mrp.workcenter` + finite-look-ahead computation in MI engine** |

## Future-State Architecture Note (post-uplift)

The Q-04 production target is a large VPS hosting:
1. Odoo 19 CE (migrated from QNAP)
2. A RAG sidecar (knowledge retrieval)
3. Self-hosted Qwen LLM
4. **MCP server bridging Qwen ↔ Odoo southbrookcabinetry**

Phase 5 lands the MCP scaffolding (tools + manifests + auth) on the QNAP instance so it migrates cleanly. The Qwen + RAG hosts are out of scope for this uplift but the integration surface is built now.

---

**Phase 0 status: COMPLETE. Phase 1 unblocked.**
