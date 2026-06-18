# SPDX-License-Identifier: LGPL-3.0-only
"""P2 — Brand-aware Drawer Slide attribute.

The audit found that the configurator's "Soft-Close" was a flat +$15 checkbox
bound to no real product, while King Slide KS-K2832-21 (and the three other
slide brands the company stocks) sat in the hardware catalog unreachable.

This module:

  1. Seeds a real ``product.attribute`` named "Drawer Slide" with five
     selectable values, one per brand the catalog already carries.
  2. Maps each value to its real ``x_marathon_sku`` so the resolver can
     bind the variant into the BoM at qty = drawer_count.
  3. Marks each value's ``is_soft_close`` so the UI can render
     "Soft-Close" as a *derived badge* (not as a separately-priced
     accessory). The badge derivation happens in
     :func:`is_soft_close_slide_picked` which the configurator state
     endpoint consults; the legacy +$15 Accessories→Soft-Close pick is
     silently suppressed from the price calc when a soft-close slide is
     chosen, preventing the double-charge the audit called out.
  4. Backfills ``price_extra`` + ``weight_extra`` on the per-template
     attribute-value rows so the live recalc reflects the chosen brand.

Idempotent: re-running the seed function never duplicates the attribute,
values, or template attribute lines. The function is wired through
``data/p2_drawer_slide.xml`` to fire on install / ``-u`` of this addon.

Acceptance criteria (P2):

  * Selecting "King Slide K2832 21\" Soft-Close" causes the resolved BoM
    to contain ``KS-K2832-21`` at qty = drawer_count (3 for the audit
    sample 3-drawer base cabinet).
  * "Soft-Close" auto-derives as a read-only badge.
  * Live price reflects the slide's price_extra, not a hardcoded $15.
"""
from odoo import api, models

# (value_name, x_marathon_sku, is_soft_close, demo_price_extra, weight_extra_kg).
# price_extra numbers are demo-grade — same convention as
# tactical_price_seed.py; the company's authoritative slide pricing lives
# in the Hardware Catalog product cards and the resolver binds the real
# product at the BoM stage, which is what the audit's load-bearing
# acceptance criterion (BoM contains product 458 ×3) tests against.
DRAWER_SLIDE_OPTIONS = [
    # (display_name, sku, is_soft_close, price_extra, weight_extra)
    ("King Slide K2832 21\" Soft-Close",  "KS-K2832-21",   True,  35.0, 0.3),
    ("King Slide 3032 18\" Ball-Bearing", "KS-3032-18",    False, 18.0, 0.25),
    ("Blum MOVENTO 450",                  "BLM-MOV-450",   True,  65.0, 0.4),
    ("Hettich Actro 5D 500",              "HET-ACTRO-500", True,  55.0, 0.35),
    ("Salice Progressa+ (PR-602728)",     "PR-602728",     False, 28.0, 0.3),
]

DRAWER_SLIDE_ATTR_NAME = "Drawer Slide"
SOFT_CLOSE_VALUE_NAME = "Soft-Close"          # legacy Accessories pick
SOFT_CLOSE_ACCESSORY_ATTR_NAME = "Accessories"  # parent attr for the legacy pick


def is_soft_close_slide(value_name):
    """True if the named Drawer Slide value is a soft-close model."""
    if not value_name:
        return False
    for name, _sku, is_sc, _p, _w in DRAWER_SLIDE_OPTIONS:
        if name == value_name:
            return is_sc
    return False


def slide_sku_for_value_name(value_name):
    """Return the Marathon SKU bound to the named Drawer Slide value."""
    if not value_name:
        return None
    for name, sku, _is_sc, _p, _w in DRAWER_SLIDE_OPTIONS:
        if name == value_name:
            return sku
    return None


class DrawerSlideSeed(models.AbstractModel):
    _name = "southbrook.configurator_ux.drawer_slide_seed"
    _description = "P2 — Drawer Slide attribute + values + per-template wiring"

    @api.model
    def seed_drawer_slide_attribute(self):
        """Idempotent seed for the P2 Drawer Slide attribute.

        Returns the seeded ``product.attribute`` record. Wires the
        attribute to every template that already exposes a
        "Drawer Construction" attribute (those are the drawer cabinets
        whose BoM benefits from a brand-aware slide pick).
        """
        Attribute = self.env["product.attribute"]
        AttributeValue = self.env["product.attribute.value"]
        TmplAttrLine = self.env["product.template.attribute.line"]
        PTAV = self.env["product.template.attribute.value"]

        attribute = Attribute.search(
            [("name", "=", DRAWER_SLIDE_ATTR_NAME)], limit=1)
        if not attribute:
            attribute = Attribute.create({
                "name": DRAWER_SLIDE_ATTR_NAME,
                "display_type": "radio",
                "create_variant": "no_variant",
            })

        # Idempotent value creation (lookup-by-name).
        values_by_name = {}
        sequence = 10
        for name, _sku, _is_sc, _price, _weight in DRAWER_SLIDE_OPTIONS:
            v = AttributeValue.search([
                ("attribute_id", "=", attribute.id),
                ("name", "=", name),
            ], limit=1)
            if not v:
                v = AttributeValue.create({
                    "attribute_id": attribute.id,
                    "name": name,
                    "sequence": sequence,
                })
            values_by_name[name] = v
            sequence += 10

        # Wire the attribute to every template that exposes Drawer Construction.
        # That's the canonical "this template has drawers" signal in the
        # Southbrook seed — see catalog_expansion.xml.
        construction_attr = Attribute.search(
            [("name", "=", "Drawer Construction")], limit=1)
        if construction_attr:
            templates_with_drawers = TmplAttrLine.search(
                [("attribute_id", "=", construction_attr.id)],
            ).mapped("product_tmpl_id")
            for tmpl in templates_with_drawers:
                existing_line = TmplAttrLine.search([
                    ("product_tmpl_id", "=", tmpl.id),
                    ("attribute_id", "=", attribute.id),
                ], limit=1)
                if existing_line:
                    # Ensure all our values are linked.
                    existing_line.value_ids = [
                        (4, v.id) for v in values_by_name.values()
                    ]
                    continue
                TmplAttrLine.create({
                    "product_tmpl_id": tmpl.id,
                    "attribute_id": attribute.id,
                    "value_ids": [(6, 0, [v.id for v in values_by_name.values()])],
                })

        # Backfill price/weight on the per-template attribute values.
        for name, _sku, _is_sc, price, weight in DRAWER_SLIDE_OPTIONS:
            v = values_by_name[name]
            ptavs = PTAV.search([("product_attribute_value_id", "=", v.id)])
            if ptavs:
                ptavs.write({"price_extra": price, "weight_extra": weight})

        return attribute

    @api.model
    def is_soft_close_slide_picked(self, value_ids):
        """Given a session's value_ids recordset (product.attribute.value),
        return True iff one of them is a Drawer Slide value whose
        ``is_soft_close`` is True. Backbone for the derived badge.
        """
        if not value_ids:
            return False
        for v in value_ids:
            if v.attribute_id.name == DRAWER_SLIDE_ATTR_NAME:
                if is_soft_close_slide(v.name):
                    return True
        return False

    @api.model
    def slide_sku_from_session(self, session):
        """Return the SKU of the slide picked in this OCA config session,
        or None when no Drawer Slide pick is present.
        """
        if not session:
            return None
        for v in session.value_ids:
            if v.attribute_id.name == DRAWER_SLIDE_ATTR_NAME:
                return slide_sku_for_value_name(v.name)
        return None
