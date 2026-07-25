# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).
from odoo import _, fields, models


class DmsFile(models.Model):
    _inherit = "dms.file"

    qc_status = fields.Selection(
        [
            ("unreviewed", "Unreviewed"),
            ("pass", "Pass"),
            ("flag", "Flag"),
        ],
        string="QC Status",
        default="unreviewed",
        help="Quality-control review status for this media file.",
    )

    annotation_data = fields.Text(
        string="Annotation Data",
        help="""JSON-serialized annotation strokes/markup overlaid on this
        file. Strictly non-destructive: the underlying binary ``content`` is
        never modified by annotation; this field only stores the overlay
        data alongside it.""",
    )

    def _sb_get_anchor_record(self):
        """Resolve the business record this file's directory is anchored to.

        Reads ``res_model``/``res_id`` directly off ``directory_id`` (the
        file's own directory, not a parent walk-up). Returns an empty
        recordset if the directory has no anchor (e.g. a purely structural
        subfolder such as "Orders"), so callers can skip the chatter post
        gracefully instead of crashing.
        """
        self.ensure_one()
        directory = self.directory_id
        res_model = directory.res_model
        res_id = directory.res_id
        if not res_model or not res_id:
            return self.env[self._name].browse()
        if res_model not in self.env:
            return self.env[self._name].browse()
        record = self.env[res_model].browse(res_id).exists()
        return record

    def _sb_post_audit_note(self, body):
        """Post a timestamped, user-attributed chatter note on the anchored
        record, if one can be resolved. No-op (no crash) otherwise.
        """
        self.ensure_one()
        record = self._sb_get_anchor_record()
        if not record or not hasattr(record, "message_post"):
            return
        timestamp = fields.Datetime.now()
        user_name = self.env.user.display_name
        record.message_post(
            body=_(
                "%(user)s (%(timestamp)s) — %(body)s [file: %(file)s]",
                user=user_name,
                timestamp=timestamp,
                body=body,
                file=self.name,
            )
        )

    def action_set_qc_status(self, status):
        """Set ``qc_status`` on each file and post a chatter audit note on
        each file's anchored record (skipped gracefully when there is none).
        """
        for record in self:
            record.qc_status = status
            record._sb_post_audit_note(
                _("QC status set to \"%s\"", dict(record._fields["qc_status"].selection).get(status, status))
            )

    def action_save_annotation(self, annotation_json):
        """Store the annotation JSON (non-destructive: never touches the
        binary ``content``) and post a chatter audit note on each file's
        anchored record (skipped gracefully when there is none).
        """
        for record in self:
            record.annotation_data = annotation_json
            record._sb_post_audit_note(_("Annotation saved"))
