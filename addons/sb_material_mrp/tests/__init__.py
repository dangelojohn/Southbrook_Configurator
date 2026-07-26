# SPDX-License-Identifier: LGPL-3.0-only
from . import test_cost_cascade
from . import test_material_demand_qty
from . import test_material_thickness
from . import test_panel_volume
from . import test_production_totals
from . import test_weight_line
from . import test_weight_rollup_multilevel
# Repair Wave 3 — end-to-end money test: template material_id fallback.
from . import test_component_material_fallback_e2e
# Phase-2 Task 4 — suggested_purchase_qty assist number.
from . import test_suggested_purchase_qty
# Phase-2 Task 5 — Buy-route helper button.
from . import test_route_buy_helper
# Cutlist Precision Task 2 — exact per-line panel-role volume helpers.
from . import test_cutlist_exact
# Final whole-branch review (2026-07-26), M-3 — N-same-material split, door
# role, weight/demand agreement, I-2 rollup-equals-sum.
from . import test_cutlist_precision_review_fixes
# Phase-2b Task 1 — mrp.bom.line._sb_demand_qty_in_uom wrapper.
from . import test_demand_qty_uom_conversion
