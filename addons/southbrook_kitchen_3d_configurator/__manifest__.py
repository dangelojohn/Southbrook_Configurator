{
    "name": "Southbrook Kitchen 3D Configurator",
    "summary": (
        "Isometric Three.js kitchen room configurator backed by "
        "live Odoo cabinet inventory — design, save, and quote."
    ),
    "version": "19.0.4.2.0",
    "category": "Manufacturing/Product Configurator",
    "author": "OdooIQ / REAL Partners Ltd.",
    "website": "https://odooiq.com",
    "license": "LGPL-3",
    "depends": [
        "web", "product", "sale_management", "stock", "mrp",
        # 2026-06-28 Tier-A — depend on southbrook_estimating so the
        # vendored r160 Three.js + the channel-pricelist resolver
        # (sale.order._resolve_channel_pricelist) are available. Drops
        # the CDN three@0.128 and unblocks dealer/contractor pricing
        # on the configurator's "Create Quotation" action.
        "southbrook_estimating",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/product_template_views.xml",
        "views/kitchen_design_views.xml",
        "views/kitchen_configurator_views.xml",
        "data/demo_cabinets.xml",
    ],
    "assets": {
        "web.assets_backend": [
            # 2026-06-28 Tier-A — vendor r160 Three.js (UMD, air-gapped)
            # from southbrook_estimating's catalog. Must load FIRST so
            # window.THREE is populated before kitchen_configurator.js
            # references it. Replaces the previous three@0.128 CDN load.
            "southbrook_estimating/static/lib/three/three.min.js",
            # 2026-06-28 D1 — OrbitControls UMD shim (decorates window.THREE
            # with THREE.OrbitControls). Required by the Perspective view's
            # free-camera mode and zoom dolly.
            "southbrook_estimating/static/lib/three/OrbitControls.js",
            "southbrook_kitchen_3d_configurator/static/src/scss/kitchen_configurator.scss",
            "southbrook_kitchen_3d_configurator/static/src/js/kitchen_configurator.js",
        ],
    },
    "application": True,
    "installable": True,
    "auto_install": False,
}
