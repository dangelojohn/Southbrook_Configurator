{
    "name": "Southbrook Production Media",
    "version": "19.0.1.0.1",
    "summary": "Photos/videos organized by Product, Manufacturing Order, and Shipping; QC media bridge on DMS.",
    "license": "LGPL-3",
    "author": "Southbrook Cabinetry",
    # mrp_shop_floor_control is listed to make override order DETERMINISTIC,
    # not because this module calls into it. Both modules override
    # mrp.production.button_mark_done() — ours checks required media, theirs
    # guards that work orders are scheduled and closed. Without an explicit
    # dependency the MRO between the two is undefined, so which guard reports
    # first could differ between environments. Declaring it pins our override
    # OUTERMOST: the media check runs first, then super() reaches the
    # shop-floor-control guards. Both call super() correctly either way, so
    # this is about predictable messaging, not correctness.
    "depends": ["dms", "dms_field", "product", "mrp", "stock",
                "mrp_shop_floor_control"],
    "data": [
        "security/production_media_security.xml",
        "security/ir.model.access.csv",
        "data/storage_data.xml",
        "data/dms_field_template_data.xml",
        "views/production_media_menus.xml",
        "views/product_template_views.xml",
        "views/mrp_production_views.xml",
        "views/stock_picking_views.xml",
    ],
    "installable": True,
    "application": False,
}
