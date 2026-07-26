# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).
"""Narrow server RPC surface for the Process Explorer QC media panel (Part D).

``production.media`` is a generic (res_model, res_id) facade over the DMS
bridge built in C1-C8: it does not know about kitchens, cabinets, or any
Southbrook-specific model -- callers name any business record that carries
the ``dms.field.mixin`` (product/MO/picking today, more later) and this
model resolves its directory, lists/creates files in it, and delegates QC
status / annotation writes to the C7 ``dms.file`` methods.

DEGRADE PATTERN (mirrors ``material.explorer.get_data()`` in
mrp_process_explorer_material_provider/material_explorer.py): reads are
wrapped in ``.sudo()`` with an explicit access check and a try/except that
degrades to an honest empty payload rather than a 500. Writes are the
opposite -- they must enforce access, so ``upload_media`` explicitly checks
write access on the target business record (raising ``AccessError`` for a
caller who lacks it) before using ``sudo()`` internally to perform the DMS
housekeeping (creating the directory / file) that the caller may not have
direct DMS-group access to. ``set_qc_status``/``save_annotation`` delegate
straight to ``dms.file``'s own methods (no ``sudo()``), so ``dms.file``'s
native access checks apply.
"""
from odoo import _, api, models
from odoo.exceptions import AccessError, UserError


class ProductionMedia(models.AbstractModel):
    _name = "production.media"
    _description = "Production Media RPC surface (Process Explorer QC panel)"

    @api.model
    def _sb_resolve_directory(self, res_model, res_id, create_if_missing=False):
        """Return the ``dms.directory`` anchored to ``(res_model, res_id)``.

        LANDMINE (see dms_field_bridge.py): ``dms_directory_ids`` is a
        One2many keyed on a plain ``(res_model, res_id)`` domain rather than
        a true inverse Many2one, so the ORM does not auto-invalidate a
        cached empty value once a directory is created earlier in the same
        transaction. Always invalidate before reading.

        When ``create_if_missing`` is set and no directory exists yet, drive
        ``dms.field.template.create_dms_directory()`` directly instead of
        relying on ``dms.field.mixin.create()`` picking it up automatically
        -- that auto-creation is itself gated off during
        ``--test-enable`` runs unless the ``test_dms_field`` context flag is
        set (see dms_field/models/dms_field_mixin.py), so callers that
        upload media right after creating a record in a test must not
        depend on it having already run.
        """
        record = self.env[res_model].sudo().browse(res_id)
        record.invalidate_recordset(["dms_directory_ids"])
        directory = record.dms_directory_ids[:1]
        if directory or not create_if_missing:
            return directory
        self.env["dms.field.template"].sudo().with_context(
            res_model=res_model, res_id=res_id
        ).create_dms_directory()
        record.invalidate_recordset(["dms_directory_ids"])
        return record.dms_directory_ids[:1]

    @api.model
    def get_node_media(self, res_model, res_id):
        """Read-only payload for the QC panel.

        Degrades to ``{"files": [], "can_write": False}`` on any failure
        (unknown model, missing record, AccessError, a model without the
        DMS mixin, ...) instead of raising -- never a 500 for the panel.
        """
        empty = {"files": [], "can_write": False}
        try:
            if res_model not in self.env:
                return empty
            record = self.env[res_model].browse(res_id)
            if not record.exists():
                return empty
            try:
                record.check_access("read")
            except AccessError:
                return empty
            try:
                record.check_access("write")
                can_write = True
            except AccessError:
                can_write = False

            directory = self._sb_resolve_directory(res_model, res_id)
            if not directory:
                return {"files": [], "can_write": can_write}

            files = (
                self.env["dms.file"]
                .sudo()
                .search([("directory_id", "child_of", directory.ids)])
            )
            payload = []
            for f in files:
                mimetype = f.mimetype or ""
                payload.append(
                    {
                        "id": f.id,
                        "name": f.name,
                        "mimetype": mimetype,
                        "is_video": mimetype.startswith("video/"),
                        "qc_status": f.qc_status,
                        "annotation_data": f.annotation_data,
                        "url": "/web/content/%s" % f.id,
                    }
                )
            return {"files": payload, "can_write": can_write}
        except Exception:  # noqa: BLE001 - degrade, never 500 for the panel
            return empty

    @api.model
    def upload_media(self, res_model, res_id, filename, datas_b64, mimetype):
        """Create a ``dms.file`` in the record's directory and return its id.

        Enforces access: raises ``AccessError`` if the calling user cannot
        write to the target business record. Directory resolution/creation
        and the actual file creation run under ``sudo()`` -- the caller is
        authorized via the *business record*, not necessarily via direct
        DMS group membership on its directory.
        """
        if res_model not in self.env:
            raise AccessError(_("Unknown model: %s", res_model))
        record = self.env[res_model].browse(res_id)
        if not record.exists():
            raise AccessError(_("Record not found or not accessible."))
        record.check_access("write")  # raises AccessError if not permitted

        directory = self._sb_resolve_directory(res_model, res_id, create_if_missing=True)
        if not directory:
            raise UserError(
                _("Could not resolve or create a media directory for this record.")
            )
        dms_file = (
            self.env["dms.file"]
            .sudo()
            .create(
                {
                    "name": filename,
                    "directory_id": directory[:1].id,
                    "content": datas_b64,
                    "mimetype": mimetype,
                }
            )
        )
        return dms_file.id

    @api.model
    def save_annotation(self, file_id, annotation_json):
        """Delegate to ``dms.file.action_save_annotation`` (no ``sudo()`` --
        the file's own access rules apply)."""
        self.env["dms.file"].browse(file_id).action_save_annotation(annotation_json)
        return True

    @api.model
    def set_qc_status(self, file_id, status):
        """Delegate to ``dms.file.action_set_qc_status`` (no ``sudo()`` --
        the file's own access rules apply)."""
        self.env["dms.file"].browse(file_id).action_set_qc_status(status)
        return True
