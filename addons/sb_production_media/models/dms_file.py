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

    def _sb_scoped_metadata_write(self, vals):
        """Write metadata-only ``vals`` (``qc_status``/``annotation_data``)
        gated on the *anchored business record*'s write access, so any
        ordinary internal user who can edit the anchored MO/product/picking
        (``base.group_user`` alone -- not necessarily ``group_dms_user`` or
        ``group_media_manager``) can annotate/QC its media, mirroring the
        access gate ``production.media.upload_media()`` already uses
        (``anchor_record.check_access("write")``). Never touches the binary
        ``content`` field -- callers pass only ``qc_status``/
        ``annotation_data``.

        If the anchor's write-access check passes, the actual field write
        runs under ``sudo()`` (metadata-only) so it is not itself blocked by
        ``dms.file``'s own restrictive ACL (``base.group_user`` has
        ``perm_write=0`` on ``dms.file`` upstream; only ``group_dms_user``/
        ``group_media_manager`` do). If the file has no resolvable anchor
        (a purely structural/unanchored file), fall back to a normal,
        non-sudo write, so structural files still require direct ``dms``
        write rights.

        KNOWN LIMITATION (accepted for v1, see
        task-C10-security-verify.md): this does not enforce internal-user
        cross-record isolation -- i.e. it does not stop an internal user who
        can write to *some* anchor record from also passing this same gate
        for a *different* record's media, because the check is scoped to
        "does this file's own anchor record grant write" rather than a
        blanket internal-vs-internal boundary. That is a deliberate, decided
        v1 scope (see task brief); the portal/public leak this task closes
        is the ACL-layer override in ``security/ir.model.access.csv``, which
        is unaffected by and unrelated to this limitation.
        """
        self.ensure_one()
        anchor = self._sb_get_anchor_record()
        if anchor:
            anchor.check_access("write")  # raises AccessError if not permitted
            self.sudo().write(vals)
        else:
            self.write(vals)

    def action_set_qc_status(self, status):
        """Set ``qc_status`` on each file and post a chatter audit note on
        each file's anchored record (skipped gracefully when there is none).
        """
        for record in self:
            record._sb_scoped_metadata_write({"qc_status": status})
            record._sb_post_audit_note(
                _("QC status set to \"%s\"", dict(record._fields["qc_status"].selection).get(status, status))
            )

    def action_save_annotation(self, annotation_json):
        """Store the annotation JSON (non-destructive: never touches the
        binary ``content``) and post a chatter audit note on each file's
        anchored record (skipped gracefully when there is none).
        """
        for record in self:
            record._sb_scoped_metadata_write({"annotation_data": annotation_json})
            record._sb_post_audit_note(_("Annotation saved"))
