# SPDX-License-Identifier: LGPL-3.0-only
"""Marathon CSV import wizard tests."""
import base64

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged


SAMPLE_CSV = (
    b"marathon_sku,name,brand_code,category,default_code,list_price,"
    b"standard_price,description,pricing_pending\n"
    b"TEST-IMPORT-001,Test Hinge One,blum,hinge,TEST-001,12.50,5.20,"
    b"Imported test hinge,false\n"
    b"TEST-IMPORT-002,Test Slide Two,hettich,slide,TEST-002,,,"
    b"Pricing pending slide,true\n"
)

BAD_CSV_MISSING_COLS = (
    b"marathon_sku,name\nTEST-X,X name\n"
)

BAD_CSV_BAD_CATEGORY = (
    b"marathon_sku,name,brand_code,category\n"
    b"TEST-BAD-1,Test,blum,not_a_category\n"
)

BAD_CSV_BAD_BRAND = (
    b"marathon_sku,name,brand_code,category\n"
    b"TEST-BAD-2,Test,no_such_brand,hinge\n"
)


@tagged("post_install", "-at_install", "southbrook_hardware_catalog")
class TestMarathonCsvImport(TransactionCase):

    def _make_wizard(self, csv_bytes, dry_run=False):
        return self.env["southbrook.hardware.import.wizard"].create({
            "csv_file": base64.b64encode(csv_bytes),
            "csv_filename": "marathon.csv",
            "dry_run": dry_run,
        })

    # ──────────────────────────────────────────────────────────────────
    # Happy path
    # ──────────────────────────────────────────────────────────────────
    def test_import_creates_products(self):
        wiz = self._make_wizard(SAMPLE_CSV, dry_run=False)
        wiz.action_import()
        self.assertEqual(wiz.created_count, 2)
        self.assertEqual(wiz.error_count, 0)
        p1 = self.env["product.product"].search([
            ("x_marathon_sku", "=", "TEST-IMPORT-001")
        ])
        self.assertEqual(len(p1), 1)
        self.assertEqual(p1.x_hardware_category, "hinge")
        self.assertEqual(p1.list_price, 12.50)
        self.assertFalse(p1.x_pricing_pending)
        p2 = self.env["product.product"].search([
            ("x_marathon_sku", "=", "TEST-IMPORT-002")
        ])
        self.assertEqual(p2.x_hardware_category, "slide")
        self.assertTrue(p2.x_pricing_pending)

    def test_re_import_updates(self):
        self._make_wizard(SAMPLE_CSV, dry_run=False).action_import()
        wiz2 = self._make_wizard(SAMPLE_CSV, dry_run=False)
        wiz2.action_import()
        # Second run sees both rows as already-present and updates them.
        self.assertEqual(wiz2.updated_count, 2)
        self.assertEqual(wiz2.created_count, 0)

    def test_dry_run_creates_nothing(self):
        wiz = self._make_wizard(SAMPLE_CSV, dry_run=True)
        wiz.action_import()
        # Dry run counts what WOULD happen but writes nothing.
        self.assertEqual(wiz.error_count, 0)
        # Nothing was actually persisted.
        p1 = self.env["product.product"].search([
            ("x_marathon_sku", "=", "TEST-IMPORT-001")
        ])
        self.assertFalse(p1)

    # ──────────────────────────────────────────────────────────────────
    # Validation failures
    # ──────────────────────────────────────────────────────────────────
    def test_missing_required_columns_raises(self):
        wiz = self._make_wizard(BAD_CSV_MISSING_COLS, dry_run=False)
        with self.assertRaises(UserError):
            wiz.action_import()

    def test_bad_category_reports_row_error(self):
        wiz = self._make_wizard(BAD_CSV_BAD_CATEGORY, dry_run=False)
        wiz.action_import()
        # The bad row is logged as an error but doesn't abort the wizard.
        self.assertEqual(wiz.error_count, 1)
        self.assertIn("category", wiz.result_log.lower())

    def test_bad_brand_reports_row_error(self):
        wiz = self._make_wizard(BAD_CSV_BAD_BRAND, dry_run=False)
        wiz.action_import()
        self.assertEqual(wiz.error_count, 1)
        self.assertIn("brand_code", wiz.result_log)
