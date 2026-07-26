# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).
from odoo import fields, models


class DmsDirectory(models.Model):
    _inherit = "dms.directory"

    sb_dir_kind = fields.Selection(
        [
            ("product", "Product"),
            ("mo", "Manufacturing Order"),
            ("shipping", "Shipping"),
            ("structural", "Structural"),
        ],
        string="Southbrook Directory Kind",
        help="""Classifies auto-created Southbrook production-media
        directories: the record's own directory (product/mo/shipping) versus
        a purely organisational subfolder (structural, e.g. "Orders").""",
    )
