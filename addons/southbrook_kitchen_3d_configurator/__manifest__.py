{
    "name": "Southbrook Kitchen 3D Configurator",
    "summary": (
        "Isometric Three.js kitchen room configurator backed by "
        "live Odoo cabinet inventory — design, save, and quote."
    ),
    "version": "19.0.2.0.3",
    "category": "Manufacturing/Product Configurator",
    "author": "OdooIQ / REAL Partners Ltd.",
    "website": "https://odooiq.com",
    "license": "LGPL-3",
    "depends": ["web", "product", "sale_management", "stock", "mrp"],
    "data": [
        "security/ir.model.access.csv",
        "views/product_template_views.xml",
        "views/kitchen_design_views.xml",
        "views/kitchen_configurator_views.xml",
        "data/demo_cabinets.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "southbrook_kitchen_3d_configurator/static/src/scss/kitchen_configurator.scss",
            "southbrook_kitchen_3d_configurator/static/src/js/kitchen_configurator.js",
        ],
    },
    "application": True,
    "installable": True,
    "auto_install": False,
}
