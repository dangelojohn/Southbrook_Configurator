# SPDX-License-Identifier: LGPL-3.0-only
# W034 (R4.W5, 2026-06-27) — Engineering raise-ECO from WorkOrder.
from . import southbrook_wo_raise_eco_wizard
# W040 (R2.4, 2026-06-27) — Report-a-Problem one-screen wizard
# (scrap + defect + downtime in one transaction).
from . import southbrook_report_problem_wizard
# W066 (R3.9, 2026-06-27) — Subcontract Decision wizard. Diverts an
# over-capacity WO operation to a qualified pg.vendor via a
# subcontract pg.rfq, without mutating the canonical BOM routing.
from . import southbrook_subcontract_decision_wizard
