# OpenValue OPL-1 Modules — Legal Hold Memo

**Date:** 2026-06-15
**Status:** REQUIRED before external peer-manufacturer offering
**Owner:** Southbrook Cabinetry — Engineering / Legal
**Distribution:** Internal use only

---

## Scope

The Southbrook Odoo 19 CE production stack currently runs **23 OpenValue
modules** licensed under the **Odoo Proprietary License v1.0 (OPL-1)**.
These were installed during the Phase-0 MRP buildout and are operating
without a confirmed commercial agreement on file with the publisher.

### The 23 OPL-1 modules (verified live 2026-06-15)

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

## What OPL-1 means

OPL-1 is a **per-deployment commercial license** issued by the publisher.
Odoo Community Edition does **not** validate it technically — modules
install and run regardless. The obligation lives entirely in **contract
law**, outside Odoo's runtime. Redistribution, multi-tenant hosting, and
SaaS shapes are explicitly carved out of the default OPL-1 grant and
require separate written authorisation.

## Actions required (in order)

1. **Contact OpenValue.** Email `hello@openvalue.cloud` or use the
   contact form on openvalue.cloud to confirm the current contract
   status for the Southbrook deployment. Reference each module by
   technical name.
2. **Choose a path:**
   - **(a)** Obtain a written redistribution agreement that explicitly
     covers the planned peer-manufacturer SaaS / multi-tenant shape, or
   - **(b)** Replace these 23 modules with LGPL/AGPL-licensed
     alternatives and rewrite the affected business logic
     (shop-floor-control, planning engine, costing, KPI dashboards).
3. **Hold the pitch.** Until (1) is confirmed in writing, **do not**
   pitch the Southbrook platform externally as a SaaS, fork, or
   hosted-for-third-parties package.

## Risk

Redistributing OPL-1 modules without authorisation creates **contract
and copyright liability** for Southbrook **and any tenant** running the
shared stack. The exposure is uncapped under default OPL-1 terms.

## Conclusion

> **No external offering proceeds without item #1 confirmed in writing.**
