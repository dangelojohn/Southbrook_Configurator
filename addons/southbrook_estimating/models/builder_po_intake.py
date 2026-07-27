# SPDX-License-Identifier: LGPL-3.0-only
"""southbrook.builder.po.intake — builder PO intake stub (SAMI PRD #16).

Foundation for the Mattamy / Great Gulf / Brookfield builder workflow.
Per the production plan §16: CSV-first interim ingestion until full
EDI 850/856/810 middleware is deployed in Phase 4. This module ships
the model + form + action_apply flow that:

  1. Accepts a builder PO via file upload (CSV) or pasted JSON
  2. Parses into per-cabinet line entries
  3. Resolves customer + product mappings
  4. Creates a draft sale.order with sale.order.line per row

The same model carries the EDI envelope shape once middleware lands:
intake_method='edi_850', raw_payload holds the X12 segment dump,
parser switches on intake_method to use the EDI tokenizer instead of
the CSV reader.

Expected CSV columns (case-insensitive, header row required):
  unit_number       Mattamy / builder unit identifier (e.g. 'M-4521')
  cabinet_code      Cabinet SKU or product default_code
  qty               Quantity (int / float)
  due_date          ISO-8601 YYYY-MM-DD (optional; falls back to SO due)
  notes             Free-text remark (optional)

Empty rows are skipped silently. Bad rows (qty=0, missing cabinet code,
unresolvable product) accumulate into a per-line error_message field
so the operator can fix in-form without re-uploading.
"""
import base64
import csv
import io
import json

from odoo import _, api, fields, models
from odoo.exceptions import UserError


INTAKE_METHODS = [
    ("csv", "CSV Upload"),
    ("json", "JSON Paste"),
    ("api", "API Push"),
    ("edi_850", "EDI 850 (future)"),
]


INTAKE_STATES = [
    ("draft", "Draft"),
    ("parsed", "Parsed"),
    ("applied", "Applied"),
    ("error", "Error"),
    ("cancelled", "Cancelled"),
]


class BuilderPoIntake(models.Model):
    _name = "southbrook.builder.po.intake"
    _description = "Southbrook Builder PO Intake"
    _inherit = ["mail.thread", "mail.activity.mixin", "southbrook.qr.mixin"]
    _order = "create_date desc"
    _qr_kind = "intake"

    name = fields.Char(
        default=lambda self: _("New"),
        required=True, copy=False, readonly=True, index=True,
    )
    state = fields.Selection(
        INTAKE_STATES, default="draft", required=True,
        tracking=True, index=True,
    )
    intake_method = fields.Selection(
        INTAKE_METHODS, default="csv", required=True, tracking=True,
    )
    partner_id = fields.Many2one(
        "res.partner", string="Builder",
        required=True, tracking=True, index=True,
        help="The builder (Mattamy / Great Gulf / Brookfield) "
             "submitting this PO.",
    )
    customer_po_number = fields.Char(
        string="Customer PO #", tracking=True,
        help="The builder's reference for this PO.",
    )
    file_data = fields.Binary(string="CSV File")
    file_name = fields.Char(string="File Name")
    raw_payload = fields.Text(
        string="Raw Payload",
        help="For JSON / API / EDI 850: paste or POST the original "
             "envelope here. Parser switches on intake_method.",
    )
    notes = fields.Text()

    line_ids = fields.One2many(
        "southbrook.builder.po.intake.line",
        "intake_id", string="Parsed Lines",
    )
    line_count = fields.Integer(
        compute="_compute_line_counts", store=True)
    error_line_count = fields.Integer(
        compute="_compute_line_counts", store=True)

    sale_order_id = fields.Many2one(
        "sale.order", string="Generated SO",
        readonly=True, copy=False,
    )

    @api.depends("line_ids", "line_ids.error_message")
    def _compute_line_counts(self):
        for rec in self:
            rec.line_count = len(rec.line_ids)
            rec.error_line_count = len(rec.line_ids.filtered(
                lambda l: l.error_message))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", _("New")) == _("New"):
                vals["name"] = self.env["ir.sequence"].next_by_code(
                    "southbrook.builder.po.intake") or _("BPO/New")
        return super().create(vals_list)

    # ------------------------------------------------------------------
    # Parsing
    # ------------------------------------------------------------------
    def action_parse(self):
        """Read file_data / raw_payload and create line_ids."""
        for rec in self:
            rec.line_ids.unlink()
            if rec.intake_method == "csv":
                rec._parse_csv()
            elif rec.intake_method == "json":
                rec._parse_json()
            else:
                raise UserError(_(
                    "Intake method '%s' is not implemented yet — for "
                    "now only CSV and JSON. EDI 850 lands in Phase 4."
                ) % rec.intake_method)
            rec.state = "parsed" if rec.line_count else "error"

    def _parse_csv(self):
        self.ensure_one()
        if not self.file_data:
            raise UserError(_("Upload a CSV file before parsing."))
        try:
            decoded = base64.b64decode(self.file_data).decode("utf-8")
        except (TypeError, ValueError, UnicodeDecodeError) as exc:
            raise UserError(_("Cannot decode the CSV file: %s") % exc)
        reader = csv.DictReader(io.StringIO(decoded))
        Line = self.env["southbrook.builder.po.intake.line"]
        vals_list = []
        for raw_row in reader:
            row = {k.strip().lower(): (v or "").strip()
                   for k, v in raw_row.items() if k}
            if not row.get("cabinet_code") and not row.get("unit_number"):
                continue  # blank row
            vals_list.append({
                "intake_id": self.id,
                "unit_number": row.get("unit_number", ""),
                "cabinet_code": row.get("cabinet_code", ""),
                "qty": _safe_float(row.get("qty", "1")),
                "due_date": _safe_date(row.get("due_date")),
                "notes": row.get("notes", ""),
            })
        if vals_list:
            Line.create(vals_list)

    def _parse_json(self):
        self.ensure_one()
        if not self.raw_payload:
            raise UserError(_(
                "Paste a JSON payload before parsing."))
        try:
            payload = json.loads(self.raw_payload)
        except json.JSONDecodeError as exc:
            raise UserError(_("Invalid JSON payload: %s") % exc)
        if not isinstance(payload, list):
            payload = payload.get("lines") or []
        Line = self.env["southbrook.builder.po.intake.line"]
        vals_list = []
        for entry in payload:
            if not isinstance(entry, dict):
                continue
            vals_list.append({
                "intake_id": self.id,
                "unit_number": str(entry.get("unit_number", ""))[:64],
                "cabinet_code": str(entry.get("cabinet_code", ""))[:64],
                "qty": _safe_float(entry.get("qty", 1.0)),
                "due_date": _safe_date(entry.get("due_date")),
                "notes": str(entry.get("notes", ""))[:255],
            })
        if vals_list:
            Line.create(vals_list)

    # ------------------------------------------------------------------
    # Sale order creation
    # ------------------------------------------------------------------
    def action_apply(self):
        """Create a draft sale.order from the parsed lines."""
        self.ensure_one()
        if self.state not in ("parsed", "error"):
            raise UserError(_(
                "Parse the file first — current state is %s.") % self.state)
        if self.sale_order_id:
            raise UserError(_(
                "This intake has already generated SO %s. Cancel + "
                "duplicate to re-apply.") % self.sale_order_id.name)
        if not self.partner_id:
            raise UserError(_("Builder partner is required."))
        valid_lines = self.line_ids.filtered(lambda l: not l.error_message)
        if not valid_lines:
            raise UserError(_(
                "No valid lines to apply — fix the errors first."))
        # Re-resolve product for each line in case the operator
        # edited cabinet_code in-form.
        for line in valid_lines:
            line._resolve_product()
        bad = valid_lines.filtered(lambda l: l.error_message)
        if bad:
            raise UserError(_(
                "Some lines still have errors after re-resolve — fix "
                "or unflag before applying."))
        SO = self.env["sale.order"]
        so = SO.create({
            "partner_id": self.partner_id.id,
            "client_order_ref": self.customer_po_number or self.name,
            "origin": self.name,
        })
        SOLine = self.env["sale.order.line"]
        SOLine.create([
            {
                "order_id": so.id,
                "product_id": line.product_id.id,
                "product_uom_qty": line.qty,
                "name": _("Unit %(u)s — %(p)s%(note)s",
                          u=line.unit_number or "?",
                          p=line.product_id.display_name,
                          note=(f" ({line.notes})" if line.notes else "")),
            }
            for line in valid_lines
        ])
        self.sale_order_id = so.id
        self.state = "applied"
        self.message_post(
            body=_("Builder PO applied — created %s with %d line(s).")
            % (so.name, len(valid_lines)))
        return {
            "type": "ir.actions.act_window",
            "name": _("Generated Sale Order"),
            "res_model": "sale.order",
            "res_id": so.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_cancel(self):
        for rec in self:
            rec.state = "cancelled"


class BuilderPoIntakeLine(models.Model):
    _name = "southbrook.builder.po.intake.line"
    _description = "Southbrook Builder PO Intake Line"
    _order = "intake_id, sequence, id"

    intake_id = fields.Many2one(
        "southbrook.builder.po.intake",
        required=True, ondelete="cascade", index=True,
    )
    sequence = fields.Integer(default=10)
    unit_number = fields.Char(string="Unit #")
    cabinet_code = fields.Char(string="Cabinet Code")
    qty = fields.Float(string="Qty", default=1.0)
    due_date = fields.Date(string="Due")
    notes = fields.Char()
    product_id = fields.Many2one(
        "product.product",
        string="Resolved Product",
        compute="_compute_product",
        store=True,
    )
    error_message = fields.Char(
        string="Error",
        compute="_compute_product", store=True,
    )

    @api.depends("cabinet_code", "qty")
    def _compute_product(self):
        for rec in self:
            rec._resolve_product()

    def _resolve_product(self):
        self.ensure_one()
        if not self.cabinet_code:
            self.product_id = False
            self.error_message = _("Missing cabinet_code")
            return
        if self.qty <= 0:
            self.product_id = False
            self.error_message = _("Qty must be > 0 (got %s)") % self.qty
            return
        # Resolve by default_code first, then by name fallback.
        Product = self.env["product.product"]
        product = Product.search(
            [("default_code", "=", self.cabinet_code)], limit=1)
        if not product:
            product = Product.search(
                [("name", "=", self.cabinet_code)], limit=1)
        if not product:
            self.product_id = False
            self.error_message = _(
                "No product matches code '%s'") % self.cabinet_code
            return
        self.product_id = product.id
        self.error_message = False


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------
def _safe_float(value):
    try:
        return float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return 0.0


def _safe_date(value):
    if not value:
        return False
    try:
        return fields.Date.from_string(str(value).strip())
    except Exception:  # noqa: BLE001
        return False
