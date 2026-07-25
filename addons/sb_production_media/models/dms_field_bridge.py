# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).
from odoo import _, api, fields, models

ORDERS_SUBDIR_NAME = "Orders"

# LANDMINE (confirmed C3/C4/C6): dms_directory_ids is a One2many keyed on a
# plain (res_model, res_id) domain rather than a true inverse Many2one, so the
# ORM does NOT auto-invalidate the cached value once dms.field.mixin.create()
# creates the linked dms.directory after the record insert (same
# transaction), nor after the compute itself re-reads it on a stale cache.
# Every read site (classify-on-create, the smart-button count, the "open
# media" action) must invalidate first.


class ProductTemplate(models.Model):
    _name = "product.template"
    _inherit = ["product.template", "dms.field.mixin"]

    sb_media_file_count = fields.Integer(
        string="Photos/Videos",
        compute="_compute_sb_media_file_count",
    )

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._sb_classify_dms_directory()
        return records

    def _sb_classify_dms_directory(self):
        """Tag each record's auto-created directory as ``sb_dir_kind='product'``.

        LANDMINE: ``dms_directory_ids`` is a One2many keyed on a plain
        ``(res_model, res_id)`` domain rather than a true inverse Many2one, so
        the ORM does NOT auto-invalidate the (empty) cached value once
        ``dms.field.mixin.create()`` creates the linked ``dms.directory`` after
        the record insert, in the same transaction. Invalidate first so the
        read below reliably finds the just-created directory.
        """
        self.invalidate_recordset(["dms_directory_ids"])
        for record in self:
            directory = record.dms_directory_ids[:1]
            if directory:
                directory.sudo().sb_dir_kind = "product"

    def _compute_sb_media_file_count(self):
        """Count files across the record's directory subtree (0 pre-create).

        See LANDMINE note above: invalidate before reading
        ``dms_directory_ids``, otherwise a record whose directory was just
        created earlier in this same transaction reads an empty cache.
        """
        self.invalidate_recordset(["dms_directory_ids"])
        for record in self:
            directories = record.dms_directory_ids
            record.sb_media_file_count = sum(directories.mapped("count_total_files"))

    def action_sb_open_media(self):
        """Open the files in this record's DMS directory (and subdirs)."""
        self.ensure_one()
        self.invalidate_recordset(["dms_directory_ids"])
        directories = self.dms_directory_ids
        return {
            "type": "ir.actions.act_window",
            "name": _("Photos/Videos"),
            "res_model": "dms.file",
            "view_mode": "kanban,list,form",
            "domain": [("directory_id", "child_of", directories.ids)],
            "context": {"default_directory_id": directories[:1].id},
        }


class MrpProduction(models.Model):
    _name = "mrp.production"
    _inherit = ["mrp.production", "dms.field.mixin"]

    sb_media_file_count = fields.Integer(
        string="Photos/Videos",
        compute="_compute_sb_media_file_count",
    )

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._sb_classify_dms_directory()
        return records

    def _sb_classify_dms_directory(self):
        """Tag the MO's auto-created directory as ``sb_dir_kind='mo'`` and
        re-parent it under a get-or-created "Orders" subdirectory of the
        MO's product's own directory, instead of leaving it flat under
        ``dir_root_products`` (where the ``dms.field.template`` puts it).

        Same cache-invalidation landmine as ``ProductTemplate`` above applies
        both to this recordset's ``dms_directory_ids`` and to the product
        template's (its directory may have been created/read earlier in the
        very same transaction, e.g. a product created right before its MO).
        """
        self.invalidate_recordset(["dms_directory_ids"])
        for record in self:
            mo_dir = record.dms_directory_ids[:1]
            if not mo_dir:
                continue
            mo_dir.sudo().sb_dir_kind = "mo"
            product_tmpl = record.product_id.product_tmpl_id
            if not product_tmpl:
                continue
            product_tmpl.invalidate_recordset(["dms_directory_ids"])
            product_dir = product_tmpl.dms_directory_ids[:1]
            if not product_dir:
                continue
            orders_dir = self._get_or_create_orders_subdir(product_dir)
            mo_dir.sudo().parent_id = orders_dir.id

    def _get_or_create_orders_subdir(self, product_dir):
        """Return the "Orders" child directory of ``product_dir``, creating
        it (classified ``sb_dir_kind='structural'``) if it doesn't exist yet.
        """
        directory_model = self.env["dms.directory"].sudo()
        orders_dir = directory_model.search(
            [
                ("parent_id", "=", product_dir.id),
                ("name", "=", ORDERS_SUBDIR_NAME),
            ],
            limit=1,
        )
        if not orders_dir:
            orders_dir = directory_model.create(
                {
                    "name": ORDERS_SUBDIR_NAME,
                    "parent_id": product_dir.id,
                    "storage_id": product_dir.storage_id.id,
                    "sb_dir_kind": "structural",
                }
            )
        return orders_dir

    def _compute_sb_media_file_count(self):
        """Count files across the MO's directory subtree (0 pre-create).

        Same cache-invalidation landmine as ``ProductTemplate`` above.
        """
        self.invalidate_recordset(["dms_directory_ids"])
        for record in self:
            directories = record.dms_directory_ids
            record.sb_media_file_count = sum(directories.mapped("count_total_files"))

    def action_sb_open_media(self):
        """Open the files in this MO's DMS directory (and subdirs)."""
        self.ensure_one()
        self.invalidate_recordset(["dms_directory_ids"])
        directories = self.dms_directory_ids
        return {
            "type": "ir.actions.act_window",
            "name": _("Photos/Videos"),
            "res_model": "dms.file",
            "view_mode": "kanban,list,form",
            "domain": [("directory_id", "child_of", directories.ids)],
            "context": {"default_directory_id": directories[:1].id},
        }


class StockPicking(models.Model):
    _name = "stock.picking"
    _inherit = ["stock.picking", "dms.field.mixin"]

    sb_media_file_count = fields.Integer(
        string="Photos/Videos",
        compute="_compute_sb_media_file_count",
    )

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._sb_classify_dms_directory()
        return records

    def _sb_classify_dms_directory(self):
        """Tag each record's auto-created directory as ``sb_dir_kind='shipping'``.
        Same cache-invalidation landmine as ``ProductTemplate`` above.
        """
        self.invalidate_recordset(["dms_directory_ids"])
        for record in self:
            directory = record.dms_directory_ids[:1]
            if directory:
                directory.sudo().sb_dir_kind = "shipping"

    def _compute_sb_media_file_count(self):
        """Count files across the picking's directory subtree (0 pre-create).

        Same cache-invalidation landmine as ``ProductTemplate`` above.
        """
        self.invalidate_recordset(["dms_directory_ids"])
        for record in self:
            directories = record.dms_directory_ids
            record.sb_media_file_count = sum(directories.mapped("count_total_files"))

    def action_sb_open_media(self):
        """Open the files in this picking's DMS directory (and subdirs)."""
        self.ensure_one()
        self.invalidate_recordset(["dms_directory_ids"])
        directories = self.dms_directory_ids
        return {
            "type": "ir.actions.act_window",
            "name": _("Photos/Videos"),
            "res_model": "dms.file",
            "view_mode": "kanban,list,form",
            "domain": [("directory_id", "child_of", directories.ids)],
            "context": {"default_directory_id": directories[:1].id},
        }
