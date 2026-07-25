# OpenValue OPL-1 Modules — Legal Hold Memo

> # ⚠️ WITHDRAWN — 2026-07-25
>
> **This hold is lifted. Do not act on the original memo below.**
>
> **Basis for withdrawal:** the Southbrook principal (John D'Angelo) has
> confirmed he is **one of the owners of OpenValue, with full rights** to
> the modules listed here. The premise of the original memo — that the
> modules were "operating without a confirmed commercial agreement on file
> with the publisher" — was incorrect. Southbrook is not a third-party
> licensee of an external publisher in the sense the memo assumed.
>
> **Consequences of the withdrawal:**
> - There is **no licensing constraint** on redistribution, forking,
>   modification, multi-tenant hosting, or a SaaS / peer-manufacturer
>   offering built on these modules.
> - The "hold the pitch" instruction (original item 3) is **rescinded**.
> - Original item 2(b) — "replace these 23 modules with LGPL/AGPL
>   alternatives" — is **no longer required on legal grounds.** Any
>   consolidation of OpenValue into the Southbrook stack is now a purely
>   architectural decision, judged on maintainability and coherence, not
>   on licence exposure.
> - The `OPL-1` headers in the module manifests are retained as-is; they
>   describe the licence the code is published under, and are not evidence
>   of an unresolved third-party obligation.
>
> **Why this memo is amended rather than deleted:** it was cited as
> authoritative in at least one downstream analysis and shaped a
> replacement strategy. Deleting it would leave that reasoning
> unexplained. The original text is preserved verbatim below for the
> record.
>
> Related: `~/Downloads/OpenValue Compare with SB/` (comparison and
> revised recommendations, 2026-07-25).

---
---

## ORIGINAL MEMO — SUPERSEDED, RETAINED FOR RECORD

**Date:** 2026-06-15
**Status:** ~~REQUIRED before external peer-manufacturer offering~~ **WITHDRAWN 2026-07-25**
**Owner:** Southbrook Cabinetry — Engineering / Legal
**Distribution:** Internal use only

---

### Scope

The Southbrook Odoo 19 CE production stack currently runs **23 OpenValue
modules** licensed under the **Odoo Proprietary License v1.0 (OPL-1)**.
These were installed during the Phase-0 MRP buildout and are operating
without a confirmed commercial agreement on file with the publisher.

> **Correction (2026-07-25):** the final clause is factually wrong.
> Ownership is held by the Southbrook principal. See withdrawal notice above.

#### The 23 OPL-1 modules (verified live 2026-06-15)

1. `mrp_product_costing`
2. `mrp_sfc_availability_check`
3. `mrp_sfc_bom_comparison`
4. `mrp_sfc_bom_component_substitution`
5. `mrp_sfc_external_op_costing`
6. `mrp_sfc_external_operation`
7. `mrp_sfc_scheduling_engine`
8. `mrp_sfc_substitution_costing`
9. `mrp_shop_floor_control`
10. `openvalue_interwarehouse_transfer`
11. `openvalue_mro_maintenance`
12. `openvalue_mro_mrp_integration`
13. `openvalue_mrp_planning_capacity_load`
14. `openvalue_mrp_planning_demand`
15. `openvalue_mrp_planning_engine`
16. `openvalue_mrp_planning_mto`
17. `openvalue_mrp_planning_multilevel`
18. `openvalue_mrp_planning_subcontracting`
19. `openvalue_purchase_monitor`
20. `openvalue_purchase_order_type`
21. `openvalue_stock_inventory_turnover_report`
22. `openvalue_stock_kpi`
23. `openvalue_stock_product_overview`

Publisher: OpenValue — https://www.openvalue.cloud

> **Note (2026-07-25):** this list remains accurate and useful as an
> inventory. An independent count on 2026-07-25 confirmed all 23 installed,
> plus `southbrook_schedule_whatif` (LGPL-3) installed the same day,
> bringing the OpenValue repo to 24/24 deployed.

### What OPL-1 means

OPL-1 is a **per-deployment commercial license** issued by the publisher.
Odoo Community Edition does **not** validate it technically — modules
install and run regardless. The obligation lives entirely in **contract
law**, outside Odoo's runtime. Redistribution, multi-tenant hosting, and
SaaS shapes are explicitly carved out of the default OPL-1 grant and
require separate written authorisation.

> **Correction (2026-07-25):** accurate as a general description of OPL-1,
> but inapplicable here — these carve-outs bind licensees against a
> publisher, and Southbrook's principal is on the ownership side.

### Actions required (in order) — ALL RESCINDED 2026-07-25

1. ~~**Contact OpenValue** to confirm contract status.~~ Not required.
2. ~~**Choose a path:** (a) redistribution agreement, or (b) replace the
   23 modules with LGPL/AGPL alternatives.~~ Not required on legal
   grounds; consolidation is now an architectural choice only.
3. ~~**Hold the pitch.**~~ Rescinded — no licensing bar to an external
   offering.

### Risk — NO LONGER APPLICABLE

~~Redistributing OPL-1 modules without authorisation creates contract and
copyright liability for Southbrook and any tenant running the shared
stack. The exposure is uncapped under default OPL-1 terms.~~

### Conclusion — SUPERSEDED

~~No external offering proceeds without item #1 confirmed in writing.~~

**Current position:** no licensing obstacle exists. External offerings,
forks and multi-tenant deployments may proceed on their technical and
commercial merits.
