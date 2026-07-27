# SPDX-License-Identifier: LGPL-3.0-only
from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    x_onshape_cad_url = fields.Char(
        string="Onshape CAD URL",
        copy=True,
        help=(
            "Onshape document URL for this cabinet product. When set, "
            "the product page shows an Open in Onshape CAD button linking "
            "to this URL in a new tab. Leave blank to hide the button."
        ),
    )
