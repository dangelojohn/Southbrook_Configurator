# SPDX-License-Identifier: LGPL-3.0-only
{
    "name": "Southbrook Configuration Engine",
    "summary": "Cabinet-placement rules engine. Reads a confirmed room + "
               "appliance set + theme; produces a placement plan the "
               "manufacturing pipeline can act on.",
    "description": """
Southbrook Configuration Engine (Module 7 — platform critical path)
====================================================================

Implements docs/config_engine_spec.md (G4). The brain of the platform.

Inputs (read ONLY when sb.kitchen.project.is_ready_for_config_engine()
returns True — the GAP-02 gate stays closed otherwise):
* Wall topology + dimensions from confirmed sb.kitchen.ai.analysis
* Appliance positions + dims from confirmed sb.kitchen.appliance records
* Theme from sb.kitchen.project.theme
* Available cabinet widths (DimensionEnvelope.items per template)
* Hardware-resolution service from Module 3

Output:
* JSON conforming to schema 'southbrook.config_engine.v1' stored on
  sb.kitchen.design.option.placement_data_json. Runs + cabinets +
  appliance slots + warnings + errors.

Four constraint classes (priority order C1 > C2 > C3 > C4):
  C1 — Appliance clearances (hard)
  C2 — Width fit ±1 mm (hard)
  C3 — Configurator rules from Excel→Odoo Mapping §3.4 (hard)
  C4 — Theme preferences (soft — warnings only)

Rule storage: sb.placement.rule records (not hardcoded — per init-doc
anti-pattern list). Three rule kinds shipped: clearance, width_pref,
corner_pref. Seed file populates the per-theme + per-appliance defaults
from the G4 spec.
""",
    "author": "Southbrook Kitchens / OdooIQ",
    "license": "LGPL-3",
    "category": "Manufacturing",
    "version": "19.0.0.1.0",
    "depends": [
        "southbrook_kitchen_workspace",
        "southbrook_estimating",
        "southbrook_hardware_catalog",
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/placement_rules.xml",
        "views/sb_placement_rule_views.xml",
        "views/southbrook_config_engine_menus.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
