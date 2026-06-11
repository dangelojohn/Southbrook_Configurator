# SPDX-License-Identifier: LGPL-3.0-only
{
    "name": "Southbrook Kitchen Work Centers",
    "summary": "Realistic kitchen-cabinet manufacturing work-center "
               "configuration on top of Odoo 19 CE MRP.",
    "description": """
Southbrook Kitchen Work Centers
================================

Extends the Southbrook MRP stack with kitchen-cabinet-specific work-center
configuration, master data (materials / finishes / skills), and a station-type
taxonomy that lets operation templates and routing decisions reason about
the shop floor in the same vocabulary a planner uses.

Phase M1 ships:
  * Master data — Materials (10) + Finishes (9) lightweight CE-safe models
  * mrp.workcenter extension with x_sbk_* configuration fields:
    station_type, machine_code, machine_brand, supported_material_ids,
    supported_finish_ids, required_skill_ids (reuses hr.skill),
    max_panel_length_mm / width_mm, default_setup_time_min,
    changeover_time_min, allows_parallel_jobs, is_bottleneck,
    oee_target, planning_notes, shop_floor_notes, quality_notes,
    active_for_kitchen
  * 2 new work centers seeded — ENG01 (Design Review / Production
    Engineering) and CNC02 (Backup CNC Router)
  * station_type assigned to the 12 existing Southbrook work centers
    via no-noupdate post-load applies

Subsequent phases (M2-M4) layer in operation templates with dynamic
duration formulas, quality + rework + downtime, project/room/cabinet
fields on mrp.production, costing extensions, demo data, and views.

Built strictly for Odoo 19 CE — no Enterprise dependencies. Extends
existing Southbrook modules (southbrook_kitchen_mrp,
southbrook_manufacturing_intelligence, southbrook_mrp_pm,
southbrook_kitchen_workspace) without duplicating their models.
""",
    "version": "19.0.2.0.0",
    "license": "LGPL-3",
    "author": "Southbrook Cabinetry",
    "maintainers": ["southbrook"],
    "website": "https://southbrookcabinetry.space",
    "category": "Manufacturing",
    "depends": [
        # Odoo CE core.
        "mrp",
        "mrp_account",
        "stock",
        "hr_skills",
        # Southbrook upstream — extend, never duplicate.
        "southbrook_mrp_pm",
        "southbrook_manufacturing_intelligence",
        "southbrook_kitchen_mrp",
    ],
    "data": [
        "security/ir.model.access.csv",
        # Master data — materials + finishes the work-center fields
        # reference. Must load BEFORE the workcenter seed.
        "data/southbrook_kitchen_materials.xml",
        "data/southbrook_kitchen_finishes.xml",
        # Workcenter seeds: 2 new + station_type apply to 12 existing.
        "data/mrp_workcenter_seed.xml",
        # M2: 15 operation templates with duration formulas. Must load
        # AFTER workcenter seed since templates reference work centers.
        "data/southbrook_kitchen_operation_template.xml",
        # Views.
        "views/southbrook_kitchen_material_views.xml",
        "views/southbrook_kitchen_finish_views.xml",
        "views/southbrook_kitchen_operation_template_views.xml",
        "views/mrp_workcenter_views.xml",
        "views/southbrook_kitchen_menus.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
