# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).
from odoo import _, fields, models
from odoo.exceptions import UserError


class MrpProduction(models.Model):
    _inherit = "mrp.production"

    media_required = fields.Boolean(
        string="Media Required",
        help="If set, this manufacturing order cannot be marked done until "
        "at least one photo/video exists in its DMS directory subtree.",
    )

    def _sb_check_required_media(self):
        """Raise UserError if media_required is set and no files exist yet.

        Reuses ``sb_media_file_count`` (defined in dms_field_bridge.py),
        whose compute already invalidates the ``dms_directory_ids`` cache
        before counting -- see the LANDMINE note there. We deliberately do
        not re-derive the count/invalidation here.
        """
        for record in self:
            if record.media_required and not record.sb_media_file_count:
                raise UserError(
                    _(
                        "%(record)s requires at least one photo or video "
                        "before it can be marked done.",
                        record=record.display_name,
                    )
                )

    def button_mark_done(self):
        self._sb_check_required_media()
        return super().button_mark_done()
