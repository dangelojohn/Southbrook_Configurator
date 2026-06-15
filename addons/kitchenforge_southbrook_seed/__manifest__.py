# SPDX-License-Identifier: LGPL-3.0-only
{
    "name": "KitchenForge — Southbrook Seed Zones",
    "summary": "Bridge addon: fills the 4 KitchenForge template projects with "
               "real cabinet zones referencing southbrook_estimating's 12 "
               "locked cabinet templates. Installs against the Southbrook "
               "flagship instance to skip the manual zone seeding step.",
    "description": """
Without this bridge, the seed templates shipped by `kitchenforge_core` are
empty shells — instantiation produces a project + sale order with zero
lines. This addon populates them with realistic zone layouts drawn from
the Southbrook product catalog:

* Full Kitchen Build — 10 zones (3 wall + 3 base + sink base + drawer bank +
  tall pantry + corner)
* Partial Renovation — 4 zones (2 wall + base + sink base)
* Single Custom Cabinet — 1 zone (base_2dr placeholder)
* Vanity — 2 zones (vanity + drawer bank)

References the locked `southbrook_estimating` xml_ids per CLAUDE.md §10.
Install order: `kitchenforge_core` and `southbrook_estimating` first, then
this addon picks up both side-effects automatically.
""",
    "version": "19.0.1.0.0",
    "license": "LGPL-3",
    "author": "Southbrook Cabinetry / OdooIQ",
    "category": "Manufacturing/Project",
    "depends": [
        "kitchenforge_core",
        "southbrook_estimating",
    ],
    "data": [
        "data/template_zones.xml",
    ],
    "installable": True,
    "application": False,
}
