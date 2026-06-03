# SPDX-License-Identifier: LGPL-3.0-only
"""Tactical demo-grade price_extra + weight_extra backfill.

The configurator's LIVE price + weight badges showed $295 / 0.0 kg for
every combination because the seed data in southbrook_estimating
created product.attribute.value records with default_extra_price=0
and no weight info. The recalc pipeline (POST /select → session.
update_config → price/weight on the response) was firing correctly —
it was summing zeros.

The "right" fix is to populate price_extra per attribute value from
Southbrook_Consolidated_Dataset.xlsx Price Master in
southbrook_estimating/data/attribute_values.xml. That's a larger
data-modelling job (the workbook is the canonical source and decisions
about per-template overrides need product-owner input).

This module exists to unblock sales-rep demos in the meantime. It
holds a representative deltas table that produces visibly-different
prices + weights across the dimensions users will click during demos.
The numbers are NOT authoritative — they are demo-grade approximations
chosen to make the LIVE badge tell the truth. Once the real seed lands
in southbrook_estimating, this file should be deleted (and the data
file calling it removed from __manifest__.py).
"""
from odoo import api, models


# Demo-grade deltas. Keyed by (attribute_name, value_name) → (price_extra, weight_extra_kg).
# Names must match product_attribute.name / product_attribute_value.name as
# seeded in southbrook_estimating/data/attributes.xml exactly (the live names
# were confirmed by SELECT from the southbrook DB on 2026-06-03).
_DEMO_DELTAS = {
    # Width — biggest single driver, scales linearly-ish.
    ("Width", "9 in"):  (-30.0, -2.5),
    ("Width", "12 in"): (-15.0, -1.0),
    ("Width", "15 in"): (0.0, 0.0),
    ("Width", "18 in"): (25.0, 1.5),
    ("Width", "21 in"): (45.0, 3.0),
    ("Width", "24 in"): (75.0, 4.5),
    ("Width", "27 in"): (105.0, 6.0),
    ("Width", "30 in"): (135.0, 7.5),
    ("Width", "33 in"): (160.0, 9.0),
    ("Width", "36 in"): (180.0, 10.5),

    # Series — Contractor is the budget tier; Signature the premium.
    ("Series", "Contractor Series"): (0.0, 0.0),
    ("Series", "Contemporary"): (45.0, 0.5),
    ("Series", "Elegance"): (95.0, 1.0),
    ("Series", "Signature"): (145.0, 1.5),

    # Box Material — Maple +10% (Mapping §3.4 rule) approximated as flat $30.
    ("Box Material", "White Melamine"): (0.0, 0.0),
    ("Box Material", "Maple"): (30.0, 1.0),

    # Door Style — slab cheapest, custom dearest.
    ("Door Style", "Thermofoil Slab — White"): (0.0, 0.0),
    ("Door Style", "Five-Piece Woodgrain"): (35.0, 0.5),
    ("Door Style", "Custom (Signature)"): (95.0, 0.8),

    # Finish — small premium for stains, big for custom.
    ("Finish", "White"): (0.0, 0.0),
    ("Finish", "Maple Stain"): (15.0, 0.0),
    ("Finish", "Cherry Stain"): (20.0, 0.0),
    ("Finish", "Walnut Stain"): (25.0, 0.0),
    ("Finish", "Custom"): (75.0, 0.0),

    # Handle — small hardware cost.
    ("Handle", "None"): (0.0, 0.0),
    ("Handle", "Knob"): (0.0, 0.0),
    ("Handle", "Bar Pull"): (5.0, 0.0),
    ("Handle", "Cup Pull"): (8.0, 0.0),
    ("Handle", "Integrated"): (25.0, 0.0),

    # Accessories — soft-close is the cheap upgrade demo target.
    ("Accessories", "Soft-Close"): (15.0, 0.0),
    ("Accessories", "Pull-Outs"): (45.0, 1.0),
    ("Accessories", "Drawer Organisers"): (35.0, 0.5),

    # Finished Sides — finished panel adds cost.
    ("Finished Sides", "None"): (0.0, 0.0),
    ("Finished Sides", "Left"): (20.0, 0.0),
    ("Finished Sides", "Right"): (20.0, 0.0),
    ("Finished Sides", "Both"): (35.0, 0.0),

    # Gables.
    ("Gables", "Standard"): (0.0, 0.0),
    ("Gables", "Finished"): (15.0, 0.0),
    ("Gables", "Decorative"): (30.0, 0.0),

    # Hinge Side — typically free; symmetric.
    ("Hinge Side", "LH (Left Hand)"): (0.0, 0.0),
    ("Hinge Side", "RH (Right Hand)"): (0.0, 0.0),
    ("Hinge Side", "N/A"): (0.0, 0.0),
}


class TacticalPriceSeed(models.AbstractModel):
    _name = "southbrook.configurator_ux.tactical_seed"
    _description = "Demo-grade price_extra/weight_extra backfill for live recalc"

    @api.model
    def backfill_demo_price_extras(self):
        # Search by underlying attribute_value name + attribute name, then
        # write to the per-template PTAV records. One global value can map
        # to many PTAVs (one per template that uses it), so each delta
        # affects every cabinet that exposes that value.
        ptav = self.env["product.template.attribute.value"]
        attr_val = self.env["product.attribute.value"]
        updated = 0
        skipped_missing = []
        for (attr_name, val_name), (price, weight) in _DEMO_DELTAS.items():
            value = attr_val.search([
                ("attribute_id.name", "=", attr_name),
                ("name", "=", val_name),
            ], limit=1)
            if not value:
                skipped_missing.append(f"{attr_name}/{val_name}")
                continue
            ptavs = ptav.search([
                ("product_attribute_value_id", "=", value.id),
            ])
            if ptavs:
                ptavs.write({"price_extra": price, "weight_extra": weight})
                updated += len(ptavs)
        if skipped_missing:
            # noqa — info, not warning, since the table covers Q22 derived
            # attributes that are intentionally absent on most templates.
            self.env["ir.logging"].sudo().create({
                "name": "southbrook.configurator_ux.tactical_seed",
                "type": "server",
                "level": "INFO",
                "dbname": self.env.cr.dbname,
                "message": (f"backfill skipped {len(skipped_missing)} "
                            f"missing combinations: "
                            f"{', '.join(skipped_missing[:5])}"
                            + ("…" if len(skipped_missing) > 5 else "")),
                "path": __file__,
                "func": "backfill_demo_price_extras",
                "line": "0",
            })
        return updated
