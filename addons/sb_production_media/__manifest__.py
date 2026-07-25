{
    "name": "Southbrook Production Media",
    "version": "19.0.1.0.0",
    "summary": "Photos/videos organized by Product, Manufacturing Order, and Shipping; QC media bridge on DMS.",
    "license": "LGPL-3",
    "author": "Southbrook Cabinetry",
    "depends": ["dms", "dms_field", "product", "mrp", "stock"],
    "data": [
        "data/storage_data.xml",
        "data/dms_field_template_data.xml",
        "views/production_media_menus.xml",
    ],
    "installable": True,
    "application": False,
}
