# SPDX-License-Identifier: LGPL-3.0-only
{
    "name": "Southbrook Hardware Catalog",
    "summary": "Marathon Hardware catalog + per-carcass hardware-resolution "
               "method that the FreeCAD bridge calls post-render to append "
               "hardware lines to the BoM.",
    "description": """
Southbrook Hardware Catalog (Module 3)
=======================================

Models:

* ``southbrook.hardware.brand`` — Blum, Salice, Hettich, Marathon-branded,
  ~19 brands total per Marathon's catalog.
* Extensions on ``product.product``:
  ``x_hardware_category`` (selection: hinge | slide | pin | screw | handle |
  leveler | cam_lock | bumper | other),
  ``x_hardware_brand_id`` (m2o to southbrook.hardware.brand),
  ``x_marathon_sku`` (the SKU as listed in Marathon's workbook),
  ``x_pricing_pending`` (boolean — set when cost requires trade-account
  login that we don't have yet).

Data:

* ``data/res_partner_marathon.xml`` — the Marathon vendor partner.
* ``data/southbrook_hardware_brands.xml`` — 19 brand records.
* ``data/southbrook_hardware_seed.xml`` — ~20 representative SKUs (the
  real 179-row catalog import is gated on the trade-account workbook).
* ``data/hardware_map.json`` — JSON mapping driven by cabinet-config
  attributes, used by the resolution method.

Resolution:

* ``southbrook.hardware.catalog::resolve(cabinet_type, door_count,
  drawer_count, shelf_count, soft_close=True)`` returns a list of
  ``(product.product, qty)`` tuples that the bridge appends to the BoM
  post-render (and that the configurator can preview via a smart button
  on the cabinet template).

Outstanding:

* The 179-row Marathon workbook is not yet on disk in this repo. When
  it lands, replace ``data/southbrook_hardware_seed.xml`` with the full
  workbook conversion. The resolution method and tests already work
  against the seed; bigger data only changes the catalog, not the API.
""",
    "author": "Southbrook Kitchens / OdooIQ",
    "license": "LGPL-3",
    "category": "Manufacturing",
    "version": "19.0.0.9.0",
    "depends": [
        "product",
        "purchase",
        "southbrook_estimating",
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/res_partner_marathon.xml",
        "data/southbrook_hardware_brands.xml",
        "data/southbrook_hardware_seed.xml",
        # Tier 1.2 (2026-06-10) - 5 Marathon knob templates with
        # finish variants (20 distinct Marathon finishes). Must load
        # AFTER southbrook_hardware_brands.xml since each template
        # references brand_marathon.
        "data/marathon_knob_seed.xml",
        # Tier 2.2-extension (2026-06-10) - 20 more Marathon products
        # from the noisier ~/marathon_browser_20 scrape. Clean fields
        # only (SKU, name, brand, category, primary image URL).
        # Per-finish variants will follow once a Path B catalog file
        # lands and lets us reconstruct the variant axes confidently.
        "data/marathon_browser20_seed.xml",
        "views/southbrook_hardware_brand_views.xml",
        "views/product_template_views.xml",
        "wizards/southbrook_hardware_import_views.xml",
        "views/southbrook_hardware_menus.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
