# SPDX-License-Identifier: LGPL-3.0-only
"""Common-category kitchen cabinet catalog expansion.

Builds ~35 industry-standard kitchen cabinet product templates with full
OCA product_configurator wiring (attribute_lines + value subsets + the
right southbrook_category / icon for the configurator UX badge).

Categories covered:
  - Base cabinets: 1-door, 2-door, 3/4-drawer, sink, cooktop, dishwasher
    panel, microwave drawer, wine rack
  - Corner cabinets: lazy-susan, blind, diagonal
  - Pull-out base: trash, spice, tray divider, mixer lift
  - Wall cabinets: 1-door, 2-door, glass-door, open-shelf, microwave,
    range hood, refrigerator bridge, corner wall
  - Tall cabinets: pantry, pull-out pantry, oven tower, broom/utility,
    refrigerator enclosure
  - Vanity cabinets: 1-door, 2-door, drawer bank
  - Accessories: filler strips, end panels, crown molding, light rail,
    toe kick

This expands the locked-12 template set (CLAUDE.md Q8) to ~47 templates
so the configurator UX can demo against a realistic catalog. The Q8
twelve remain untouched. Each new template carries config_ok=True and
is wired to the same attribute pool as the Q8 base/wall/tall set,
using width subsets appropriate to the cabinet's size range.

Pricing is anchor-only (representative list_price per cabinet at its
middle width). The tactical price_extra deltas in tactical_price_seed.py
still drive LIVE recalc; this file just sets the base.
"""
from odoo import api, models


# =====================================================================
# Width subsets — used to filter which Width values each template offers.
# =====================================================================

# Narrow base/wall — for single-door cabinets and small pulls.
_W_NARROW = ["9 in", "12 in", "15 in", "18 in", "21 in"]
# Wide base/wall — for double-door, sink, drawer banks at upper end.
_W_WIDE = ["24 in", "27 in", "30 in", "33 in", "36 in"]
# Full base/wall range — for accessories and shelves that span the whole catalog.
_W_FULL = ["9 in", "12 in", "15 in", "18 in", "21 in",
           "24 in", "27 in", "30 in", "33 in", "36 in"]
# Drawer bank — 12-30 the typical drawer-stack range.
_W_DRAWER = ["12 in", "15 in", "18 in", "21 in", "24 in", "27 in", "30 in"]
# Spice / tray — sub-narrow.
_W_TINY = ["9 in", "12 in"]
# Sink / cooktop — only wide enough.
_W_SINK = ["30 in", "33 in", "36 in"]
# Corner / wide-corner — large.
_W_CORNER = ["33 in", "36 in"]
# Vanity — bath sizes (use same width values).
_W_VANITY_SMALL = ["12 in", "15 in", "18 in", "21 in", "24 in"]
_W_VANITY_LARGE = ["24 in", "27 in", "30 in", "33 in", "36 in"]

# Attribute presence flags — controls which attribute_lines get attached.
# Every doored cabinet gets the full door bundle; drawer banks skip Door
# Style / Hinge / Door Count and add specific drawer attributes (none yet
# in the seed, so we just leave them off).
_ATTRS_DOORED = (
    "Family", "Width", "Series", "Box Material", "Door Style",
    "Finish", "Hinge Side", "Finished Sides", "Gables", "Handle",
    "Accessories", "Door Count",
)
_ATTRS_DOUBLEDOOR = (
    "Family", "Width", "Series", "Box Material", "Door Style",
    "Finish", "Finished Sides", "Gables", "Handle", "Accessories",
    "Door Count",
)
_ATTRS_DRAWER_BANK = (
    "Family", "Width", "Series", "Box Material", "Door Style",
    "Finish", "Finished Sides", "Gables", "Handle", "Accessories",
)
_ATTRS_OPEN_SHELF = (
    "Family", "Width", "Series", "Box Material", "Finish",
    "Finished Sides", "Gables",
)
_ATTRS_ACCESSORY = (
    "Family", "Series", "Box Material", "Finish",
)
_ATTRS_CORNER = (
    "Family", "Width", "Series", "Box Material", "Door Style",
    "Finish", "Hinge Side", "Gables", "Handle", "Accessories",
)
_ATTRS_TALL = (
    "Family", "Width", "Series", "Box Material", "Door Style",
    "Finish", "Hinge Side", "Finished Sides", "Gables", "Handle",
    "Accessories",
)

# Subset overrides — when a cabinet exposes only a specific values from a
# multi-value attribute. Keyed by (sku_default_code, attribute_name) →
# list of value names. Anything not listed gets the full attribute value
# set (filtered by width subset for Width).
_VALUE_SUBSETS = {
    # Single-door cabinets only have Door Count = 1.
    ("SB-BASE-1DR", "Door Count"): ["1"],
    ("SB-WALL-1DR", "Door Count"): ["1"],
    ("SB-VAN-1DR", "Door Count"): ["1"],
    # Double-door: Door Count = 2.
    ("SB-BASE-2DR", "Door Count"): ["2"],
    ("SB-WALL-2DR", "Door Count"): ["2"],
    ("SB-VAN-2DR", "Door Count"): ["2"],
    # Glass door — only premium series + door style.
    ("SB-WALL-GLASS", "Series"): ["Elegance", "Signature"],
    ("SB-WALL-GLASS", "Door Style"): ["Custom (Signature)"],
    # Accessories — use the Accessory family.
    ("SB-ACC-FILLER", "Family"): ["Accessory"],
    ("SB-ACC-ENDPANEL-B", "Family"): ["Accessory"],
    ("SB-ACC-ENDPANEL-T", "Family"): ["Accessory"],
    ("SB-ACC-CROWN", "Family"): ["Accessory"],
    ("SB-ACC-LIGHTRAIL", "Family"): ["Accessory"],
    ("SB-ACC-TOEKICK", "Family"): ["Accessory"],
}


# =====================================================================
# Catalog table — the heart of this module.
#   (default_code, name, family_value_name, category_badge, icon_key,
#    list_price, attribute_keys_tuple, width_subset)
# =====================================================================

_CATALOG = [
    # ----- BASE cabinets -----
    ("SB-BASE-1DR",  "Base Cabinet · Single Door",  "Base",  "Base",  "base1",  295.00, _ATTRS_DOORED,      _W_NARROW),
    ("SB-BASE-2DR",  "Base Cabinet · Double Door",  "Base",  "Base",  "base2",  395.00, _ATTRS_DOUBLEDOOR,  _W_WIDE),
    ("SB-BASE-3DRW", "Base Cabinet · 3-Drawer Stack","Drawer Bank","Drawer","drawer", 475.00, _ATTRS_DRAWER_BANK, _W_DRAWER),
    ("SB-BASE-4DRW", "Base Cabinet · 4-Drawer Pot", "Drawer Bank","Drawer","drawer", 545.00, _ATTRS_DRAWER_BANK, ["18 in", "24 in", "30 in"]),
    ("SB-BASE-SINK", "Sink Base · Single Bowl",     "Sink",  "Base",  "sink",   385.00, _ATTRS_DOUBLEDOOR,  _W_SINK),
    ("SB-BASE-SINK-DBL", "Sink Base · Double Bowl", "Sink",  "Base",  "sink",   445.00, _ATTRS_DOUBLEDOOR,  ["33 in", "36 in"]),
    ("SB-BASE-COOKTOP","Cooktop Base",              "Base",  "Base",  "base2",  365.00, _ATTRS_DOUBLEDOOR,  _W_SINK),
    ("SB-BASE-DISHWASH","Dishwasher End Panel Base","Accessory","Base","base1",185.00, _ATTRS_ACCESSORY,   None),
    ("SB-BASE-MICRO","Microwave Drawer Base",       "Base",  "Base",  "base2",  595.00, _ATTRS_DOUBLEDOOR,  ["30 in"]),
    ("SB-BASE-WINE", "Wine Rack Base",              "Base",  "Base",  "base1",  295.00, _ATTRS_OPEN_SHELF,  ["12 in", "18 in"]),

    # ----- CORNER cabinets -----
    ("SB-CORNER-LSUSAN","Corner Base · Lazy-Susan", "Corner","Base",  "corner", 625.00, _ATTRS_CORNER,      _W_CORNER),
    ("SB-CORNER-BLIND","Corner Base · Blind",       "Corner","Base",  "corner", 545.00, _ATTRS_CORNER,      _W_CORNER),
    ("SB-CORNER-DIAG","Corner Base · Diagonal",     "Corner","Base",  "corner", 685.00, _ATTRS_CORNER,      _W_CORNER),

    # ----- PULL-OUT base cabinets -----
    ("SB-BASE-PO-TRASH","Pull-Out Trash Base",      "Base",  "Base",  "base1",  325.00, _ATTRS_DOORED,      ["15 in", "18 in"]),
    ("SB-BASE-PO-SPICE","Pull-Out Spice Base",      "Base",  "Base",  "base1",  185.00, _ATTRS_DOORED,      _W_TINY),
    ("SB-BASE-PO-TRAY","Tray Divider Base",         "Base",  "Base",  "base1",  225.00, _ATTRS_DOORED,      _W_TINY),
    ("SB-BASE-PO-MIXER","Mixer Lift Base",          "Base",  "Base",  "base1",  475.00, _ATTRS_DOORED,      ["15 in", "18 in"]),

    # ----- WALL cabinets -----
    ("SB-WALL-1DR",  "Wall Cabinet · Single Door",  "Wall",  "Wall",  "wall1",  245.00, _ATTRS_DOORED,      _W_NARROW),
    ("SB-WALL-2DR",  "Wall Cabinet · Double Door",  "Wall",  "Wall",  "wall2",  325.00, _ATTRS_DOUBLEDOOR,  _W_WIDE),
    ("SB-WALL-GLASS","Wall Cabinet · Glass Door",   "Wall",  "Wall",  "wall2",  445.00, _ATTRS_DOUBLEDOOR,  ["18 in", "24 in", "30 in", "36 in"]),
    ("SB-WALL-OPEN", "Wall Cabinet · Open Shelf",   "Wall",  "Wall",  "wall1",  185.00, _ATTRS_OPEN_SHELF,  _W_FULL),
    ("SB-WALL-MICRO","Wall Microwave Cabinet",      "Wall",  "Wall",  "wall2",  395.00, _ATTRS_DOUBLEDOOR,  ["24 in", "30 in"]),
    ("SB-WALL-RANGEH","Range Hood Wall Cabinet",    "Wall",  "Wall",  "wall2",  365.00, _ATTRS_DOUBLEDOOR,  ["30 in", "36 in"]),
    ("SB-WALL-FRIDGE","Wall Refrigerator Bridge",   "Wall",  "Wall",  "wall2",  285.00, _ATTRS_DOUBLEDOOR,  _W_SINK),
    ("SB-WALL-CORNER","Corner Wall Cabinet",        "Corner","Wall",  "wall1",  295.00, _ATTRS_DOORED,      ["24 in", "27 in"]),

    # ----- TALL cabinets -----
    ("SB-TALL-PANTRY","Tall Pantry",                "Tall",  "Tall",  "pantry", 895.00, _ATTRS_TALL,        ["18 in", "24 in"]),
    ("SB-TALL-PANTRY-PO","Pull-Out Pantry",         "Tall",  "Tall",  "pantry", 1245.00, _ATTRS_TALL,       ["12 in", "15 in", "18 in"]),
    ("SB-TALL-OVEN", "Oven Tower",                  "Tall",  "Tall",  "oven",   1095.00, _ATTRS_TALL,       ["30 in", "33 in"]),
    ("SB-TALL-BROOM","Tall Broom / Utility",        "Tall",  "Tall",  "pantry", 695.00, _ATTRS_TALL,        ["18 in", "24 in"]),
    ("SB-TALL-FRIDGE","Tall Refrigerator Enclosure","Tall",  "Tall",  "oven",   985.00, _ATTRS_TALL,        ["33 in", "36 in"]),

    # ----- VANITY cabinets -----
    ("SB-VAN-1DR",   "Vanity · Single Door",        "Vanity","Vanity","vanity", 345.00, _ATTRS_DOORED,      _W_VANITY_SMALL),
    ("SB-VAN-2DR",   "Vanity · Double Door",        "Vanity","Vanity","vanity", 475.00, _ATTRS_DOUBLEDOOR,  _W_VANITY_LARGE),
    ("SB-VAN-DRW",   "Vanity · Drawer Bank",        "Vanity","Vanity","vanity", 525.00, _ATTRS_DRAWER_BANK, ["24 in", "30 in"]),

    # ----- ACCESSORIES -----
    ("SB-ACC-FILLER","Filler Strip · 3in",          "Accessory","Extras","extra", 28.00, _ATTRS_ACCESSORY,  None),
    ("SB-ACC-FILLER-6","Filler Strip · 6in",        "Accessory","Extras","extra", 38.00, _ATTRS_ACCESSORY,  None),
    ("SB-ACC-ENDPANEL-B","End Panel · Base 24x34",  "Accessory","Extras","extra", 85.00, _ATTRS_ACCESSORY,  None),
    ("SB-ACC-ENDPANEL-T","End Panel · Tall 24x84",  "Accessory","Extras","extra", 145.00, _ATTRS_ACCESSORY, None),
    ("SB-ACC-CROWN", "Crown Molding · 96in",        "Accessory","Extras","extra", 85.00, _ATTRS_ACCESSORY,  None),
    ("SB-ACC-LIGHTRAIL","Light Rail · 96in",        "Accessory","Extras","extra", 65.00, _ATTRS_ACCESSORY,  None),
    ("SB-ACC-TOEKICK","Toe Kick · 96in",            "Accessory","Extras","extra", 45.00, _ATTRS_ACCESSORY,  None),
]


class CatalogExpansion(models.AbstractModel):
    _name = "southbrook.configurator_ux.catalog_expansion"
    _description = "Common-category kitchen cabinet catalog expansion"

    @api.model
    def build_catalog(self):
        Template = self.env["product.template"]
        Attr = self.env["product.attribute"]
        AttrVal = self.env["product.attribute.value"]
        AttrLine = self.env["product.template.attribute.line"]
        Category = self.env["product.category"]

        # Vocab caches.
        attrs_by_name = {a.name: a for a in Attr.search([])}
        vals_by_attr_name = {}
        for v in AttrVal.search([]):
            vals_by_attr_name.setdefault(v.attribute_id.id, {})[v.name] = v
        goods = Category.search([("name", "=", "Goods")], limit=1) or \
                Category.search([], limit=1)
        uom_units = self.env["uom.uom"].search(
            [("name", "=", "Units"), ("active", "=", True)], limit=1)

        created, updated, skipped = 0, 0, 0
        details = []

        for (sku, name, family_val, category_badge, icon_key, price,
             attr_keys, width_subset) in _CATALOG:
            # Look up by default_code, OR by name as fallback (covers
            # re-runs after a prior build wrote the template but lost
            # default_code through variant recompute — see SKU-fix note
            # below).
            existing = (
                Template.search([("default_code", "=", sku)], limit=1)
                or Template.search([("name", "=", name)], limit=1)
            )
            # NB: default_code is set in TWO places (template-level AND
            # variant-level) because Odoo's product.template.default_code
            # is a related-store field reading from product.product. With
            # create_variant='dynamic' on these attributes, the variant
            # gets recreated whenever attribute_lines change — and the
            # newly-spawned variant loses any default_code we wrote at
            # template-creation time. So we write it once up-front (so
            # the search-by-default_code lookup keeps working on re-runs)
            # and then again AFTER attribute_lines are wired (so the
            # post-recompute variant carries it through to the public-
            # facing SKU display in the configurator response).
            vals = {
                "name": name,
                "default_code": sku,
                "type": "consu",
                "categ_id": goods.id,
                "uom_id": uom_units.id if uom_units else False,
                "list_price": price,
                "is_published": True,
                "config_ok": True,
                "southbrook_category": category_badge,
                "southbrook_icon_key": icon_key,
            }
            if existing:
                existing.write(vals)
                tmpl = existing
                updated += 1
                # Wipe existing lines so the rebuild matches the catalog
                # spec — this is idempotent.
                tmpl.attribute_line_ids.unlink()
            else:
                tmpl = Template.create(vals)
                created += 1

            # Wire attribute_lines.
            for attr_name in attr_keys:
                attr = attrs_by_name.get(attr_name)
                if not attr:
                    details.append(f"{sku}: attr '{attr_name}' missing")
                    continue
                attr_vals = vals_by_attr_name.get(attr.id, {})
                # Determine which values to attach.
                subset_key = (sku, attr_name)
                if subset_key in _VALUE_SUBSETS:
                    chosen_names = _VALUE_SUBSETS[subset_key]
                elif attr_name == "Width" and width_subset is not None:
                    chosen_names = width_subset
                elif attr_name == "Family":
                    chosen_names = [family_val]
                else:
                    chosen_names = list(attr_vals.keys())
                value_ids = [attr_vals[n].id for n in chosen_names
                             if n in attr_vals]
                if not value_ids:
                    details.append(f"{sku}: no values for {attr_name} "
                                   f"({chosen_names})")
                    continue
                AttrLine.create({
                    "product_tmpl_id": tmpl.id,
                    "attribute_id": attr.id,
                    "value_ids": [(6, 0, value_ids)],
                })

            # POST-attribute-line write of default_code. The variant
            # recompute triggered by attribute_line creation discarded
            # the default_code we set in vals; re-write it now so it
            # survives on the freshly-spawned variant(s). Touch every
            # variant directly since the template-level write doesn't
            # always cascade to all variants when there are multiple.
            tmpl.write({"default_code": sku})
            for variant in tmpl.product_variant_ids:
                if not variant.default_code:
                    variant.default_code = sku

        # After templates are created, the tactical price_extras seed
        # should be re-run so the new PTAVs get their deltas.
        self.env["southbrook.configurator_ux.tactical_seed"
                ].backfill_demo_price_extras()

        # Log result for visibility.
        self.env["ir.logging"].sudo().create({
            "name": "southbrook.configurator_ux.catalog_expansion",
            "type": "server",
            "level": "INFO",
            "dbname": self.env.cr.dbname,
            "message": (f"catalog build: {created} created, {updated} "
                        f"updated. Issues: {len(details)}: "
                        f"{'; '.join(details[:5])}"
                        + ("…" if len(details) > 5 else "")),
            "path": __file__,
            "func": "build_catalog",
            "line": "0",
        })
        return {"created": created, "updated": updated,
                "issues": len(details)}
