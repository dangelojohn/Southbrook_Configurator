# SPDX-License-Identifier: LGPL-3.0-only
"""CSV import wizard for the Marathon Hardware catalog.

The shipped seed (~30 SKUs) is a placeholder. Once the Marathon
trade-account workbook lands, an admin uses this wizard to upload the
full ~179-row CSV; the wizard validates the row shape, creates or
updates product.product records, and reports per-row results.

CSV schema (header row required, column order flexible)::

    marathon_sku        — vendor SKU (string, required, unique key)
    name                — display name (string, required)
    brand_code          — southbrook.hardware.brand.code (string, required)
    category            — one of HARDWARE_CATEGORIES (string, required)
    default_code        — internal Odoo reference (string, optional —
                          defaults to marathon_sku)
    list_price          — list price (float, optional — leaves the
                          existing value if absent)
    standard_price      — cost (float, optional)
    description         — long description (string, optional)
    pricing_pending     — "true"/"false" (string, optional — defaults
                          to true if list_price is blank)

Mode is always upsert: existing rows are matched by ``x_marathon_sku``;
missing rows are created; the wizard never deletes.
"""
from __future__ import annotations

import base64
import csv
import io
import logging
from typing import Any

from psycopg2 import IntegrityError

from odoo import _, fields, models
from odoo.exceptions import UserError, ValidationError

from ..models.product_product import HARDWARE_CATEGORIES

_logger = logging.getLogger(__name__)


REQUIRED_COLS = ("marathon_sku", "name", "brand_code", "category")
# Derive from the model's single source of truth so the wizard never drifts
# out of sync (it previously hard-coded a stale set missing end_panel/filler/
# corner_mech, and rejected those valid categories on import).
HARDWARE_CATEGORY_KEYS = {key for key, _label in HARDWARE_CATEGORIES}

# Guard against a pathological multi-MB upload materialising every row in
# memory. Manager-gated, so this is defense-in-depth, not a hard threat.
MAX_IMPORT_ROWS = 20000


def _to_bool(val: str | None) -> bool:
    if val is None:
        return False
    return val.strip().lower() in {"1", "true", "yes", "y", "t"}


class SouthbrookHardwareImport(models.TransientModel):
    _name = "southbrook.hardware.import.wizard"
    _description = "Marathon Hardware CSV Import"

    csv_file = fields.Binary(string="CSV File", required=True)
    csv_filename = fields.Char(string="Filename")
    dry_run = fields.Boolean(
        string="Dry Run",
        default=True,
        help="Parse + validate only; do not write any records.",
    )

    # Result fields populated by action_import.
    created_count = fields.Integer(string="Created", readonly=True)
    updated_count = fields.Integer(string="Updated", readonly=True)
    error_count = fields.Integer(string="Errors", readonly=True)
    result_log = fields.Text(string="Result Log", readonly=True)

    # ──────────────────────────────────────────────────────────────────
    # Action
    # ──────────────────────────────────────────────────────────────────
    def action_import(self):
        self.ensure_one()
        if not self.csv_file:
            raise UserError(_("Please attach a CSV file."))
        try:
            raw = base64.b64decode(self.csv_file)
            text = raw.decode("utf-8-sig")  # tolerate BOM from Excel
        except Exception as exc:
            raise UserError(_("Could not decode CSV: %s") % exc)

        reader = csv.DictReader(io.StringIO(text))
        if not reader.fieldnames:
            raise UserError(_("CSV is empty."))
        missing = [c for c in REQUIRED_COLS if c not in reader.fieldnames]
        if missing:
            raise UserError(
                _("CSV is missing required columns: %s") % ", ".join(missing)
            )

        rows = list(reader)
        if not rows:
            raise UserError(_("CSV has a header but no data rows."))
        if len(rows) > MAX_IMPORT_ROWS:
            raise UserError(_(
                "CSV has %(n)d data rows; the import is capped at %(max)d. "
                "Split the file and import in batches.")
                % {"n": len(rows), "max": MAX_IMPORT_ROWS})

        created = updated = errors = 0
        log_lines: list[str] = []

        Brand = self.env["southbrook.hardware.brand"]
        Product = self.env["product.product"]

        # Preload brands by code so we don't search per row.
        brand_by_code = {b.code: b for b in Brand.search([])}

        # Per-row processing wrapped in a REAL savepoint so a single bad row
        # rolls back only itself, not the whole import. Without it, a DB-level
        # error (IntegrityError from a constraint / duplicate default_code) at
        # create() aborts the whole transaction AND poisons the cursor, so
        # every subsequent row also fails ("transaction is aborted"). The
        # broadened except catches that DB error too — the savepoint rollback
        # restores a usable cursor before we continue.
        for idx, row in enumerate(rows, start=2):  # row 1 is the header
            sku = (row.get("marathon_sku") or "").strip()
            try:
                with self.env.cr.savepoint():
                    # _process_row does the single existence search and
                    # returns "created"/"updated" — no separate pre-search.
                    status = self._process_row(
                        row, brand_by_code, Product, idx, dry_run=self.dry_run)
                if status == "created":
                    created += 1
                    log_lines.append(f"row {idx}: created {sku}")
                else:
                    updated += 1
                    log_lines.append(f"row {idx}: updated {sku}")
            except (UserError, ValidationError, KeyError, ValueError,
                    IntegrityError) as exc:
                errors += 1
                log_lines.append(f"row {idx} ERROR: {exc}")
                _logger.warning("Hardware import row %d failed: %s", idx, exc)

        self.write({
            "created_count": created,
            "updated_count": updated,
            "error_count": errors,
            "result_log": "\n".join(log_lines[:500]),  # cap log size
        })

        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    def _process_row(self, row, brand_by_code, Product, line_no, dry_run):
        sku = (row.get("marathon_sku") or "").strip()
        if not sku:
            raise ValidationError(
                _("Row %d: marathon_sku is required.") % line_no)
        name = (row.get("name") or "").strip()
        if not name:
            raise ValidationError(
                _("Row %d: name is required.") % line_no)
        brand_code = (row.get("brand_code") or "").strip()
        brand = brand_by_code.get(brand_code)
        if not brand:
            raise ValidationError(
                _("Row %d: unknown brand_code '%s'.") % (line_no, brand_code))
        category = (row.get("category") or "").strip().lower()
        if category not in HARDWARE_CATEGORY_KEYS:
            raise ValidationError(
                _("Row %d: category '%s' is not a HARDWARE_CATEGORY.")
                % (line_no, category))
        default_code = (row.get("default_code") or sku).strip()
        description = (row.get("description") or "").strip() or False
        pricing_pending = _to_bool(row.get("pricing_pending"))

        vals: dict[str, Any] = {
            "name": name,
            "default_code": default_code,
            "x_marathon_sku": sku,
            "x_hardware_category": category,
            "x_hardware_brand_id": brand.id,
            "x_pricing_pending": pricing_pending,
        }
        if description:
            vals["description"] = description

        list_price = row.get("list_price")
        if list_price not in (None, ""):
            try:
                vals["list_price"] = float(list_price)
                vals["x_pricing_pending"] = False
            except ValueError:
                raise ValidationError(
                    _("Row %d: list_price '%s' is not numeric.")
                    % (line_no, list_price))
        std = row.get("standard_price")
        if std not in (None, ""):
            try:
                vals["standard_price"] = float(std)
            except ValueError:
                raise ValidationError(
                    _("Row %d: standard_price '%s' is not numeric.")
                    % (line_no, std))

        # Single existence search (was duplicated in the caller). Done before
        # the dry-run return so dry-run reports created-vs-updated accurately.
        existing = Product.search(
            [("x_marathon_sku", "=", sku)], limit=1)
        if dry_run:
            return "updated" if existing else "created"
        if existing:
            existing.write(vals)
            return "updated"
        # Defaults for a fresh placeholder product matching the seed.
        vals.update({
            "type": "consu",
            "is_storable": True,
        })
        Product.create(vals)
        return "created"
