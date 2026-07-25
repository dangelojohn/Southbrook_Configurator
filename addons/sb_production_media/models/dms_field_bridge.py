# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).
from odoo import models


class ProductTemplate(models.Model):
    _name = "product.template"
    _inherit = ["product.template", "dms.field.mixin"]


class MrpProduction(models.Model):
    _name = "mrp.production"
    _inherit = ["mrp.production", "dms.field.mixin"]


class StockPicking(models.Model):
    _name = "stock.picking"
    _inherit = ["stock.picking", "dms.field.mixin"]
