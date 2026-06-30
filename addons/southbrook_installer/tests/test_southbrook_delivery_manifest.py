# SPDX-License-Identifier: LGPL-3.0-only
"""Phase 1.2 acceptance tests:

  test_03_barcode_scan_matches_product
  test_04_blocking_damage_creates_po_and_blocks_job
  test_05_resolving_blocking_flag_clears_is_blocked
  test_06_manifest_signoff_creates_damage_flags
  test_07_barcode_scan_falls_back_to_lot_then_default_code
  test_08_auto_po_picks_lowest_sequence_active_seller

All tests live in this file (vs splitting per model) because the
manifest + damage flag are tightly coupled — the manifest's sign-off
spawns the flags, and the job's is_blocked computes off the flags.
"""
from datetime import datetime, timedelta

from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook_installer", "manifest")
class TestDeliveryManifestAndDamageFlag(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Job = cls.env["southbrook.installer.job"]
        cls.Manifest = cls.env["southbrook.delivery.manifest"]
        cls.Line = cls.env["southbrook.delivery.manifest.line"]
        cls.Flag = cls.env["southbrook.damage.flag"]
        cls.Att = cls.env["ir.attachment"]

        # Builder project + lead installer + builder partner
        cls.partner = cls.env["res.partner"].create({
            "name": "Test Builder — 1.2",
            "phone": "555-0200",
        })
        cls.project = cls.env["project.project"].create({
            "name": "Phase 1.2 Test Project",
        })
        cls.installer = cls.env["hr.employee"].create({
            "name": "Test Lead — 1.2",
        })

        # Vendor + products with barcodes for scan tests
        cls.vendor = cls.env["res.partner"].create({
            "name": "Test Vendor — Hardware Supply Co",
            "supplier_rank": 1,
        })
        cls.vendor2 = cls.env["res.partner"].create({
            "name": "Test Vendor — Backup Supply",
            "supplier_rank": 1,
        })

        cls.product_a = cls.env["product.product"].create({
            "name": "Test Base Cab B30",
            "type": "consu",
            "barcode": "TEST-B30-001",
            "default_code": "SB-B30",
            "seller_ids": [
                (0, 0, {
                    "partner_id": cls.vendor.id,
                    "min_qty": 1.0,
                    "price": 250.0,
                    "sequence": 10,
                }),
                (0, 0, {
                    "partner_id": cls.vendor2.id,
                    "min_qty": 1.0,
                    "price": 280.0,
                    "sequence": 20,
                }),
            ],
        })
        cls.product_b = cls.env["product.product"].create({
            "name": "Test Upper Cab W2430",
            "type": "consu",
            "barcode": "TEST-W2430-002",
            "default_code": "SB-W2430",
            "seller_ids": [
                (0, 0, {
                    "partner_id": cls.vendor.id,
                    "min_qty": 1.0,
                    "price": 180.0,
                    "sequence": 10,
                }),
            ],
        })
        cls.product_no_vendor = cls.env["product.product"].create({
            "name": "Test Orphan SKU",
            "type": "consu",
            "barcode": "TEST-ORPH-003",
            "default_code": "SB-ORPH",
        })

    def _make_job(self, **overrides):
        vals = {
            "project_id": self.project.id,
            "unit_number": "T-12",
            "site_address": "12 Test Lane",
            "builder_contact_id": self.partner.id,
            "lead_installer_id": self.installer.id,
            "scheduled_date": datetime.now() + timedelta(days=1),
        }
        vals.update(overrides)
        return self.Job.create(vals)

    def _make_manifest(self, job, lines):
        """lines = list of (product, qty)"""
        manifest = self.Manifest.create({
            "job_id": job.id,
            "state": "open",
        })
        for i, (product, qty) in enumerate(lines, start=1):
            self.Line.create({
                "manifest_id": manifest.id,
                "sequence": i * 10,
                "product_id": product.id,
                "qty_expected": qty,
            })
        return manifest

    def _photo(self, name="p.jpg"):
        return self.Att.create({
            "name": name,
            "datas": "Zm9v",
            "mimetype": "image/jpeg",
        })

    # ==================================================================
    # test_03 — barcode scan resolves a line by product.barcode
    # ==================================================================
    def test_03_barcode_scan_matches_product(self):
        job = self._make_job()
        manifest = self._make_manifest(job, [
            (self.product_a, 2.0),
            (self.product_b, 1.0),
        ])

        # Hit product_a by barcode
        result = self.Line.scan_barcode_on_manifest(
            manifest.id, "TEST-B30-001",
        )
        self.assertEqual(result["status"], "ok",
                         f"Expected ok, got {result}")
        # display_name includes the default_code prefix like '[SB-B30]'
        self.assertIn("Test Base Cab B30", result["product_name"])

        line_a = manifest.line_ids.filtered(
            lambda l: l.product_id == self.product_a
        )
        self.assertEqual(line_a.status, "ok")
        self.assertTrue(line_a.scanned_by_barcode)
        self.assertEqual(line_a.qty_received_ok, 2.0)

        # Re-scanning an already-OK line returns 'already_confirmed'
        result2 = self.Line.scan_barcode_on_manifest(
            manifest.id, "TEST-B30-001",
        )
        self.assertEqual(result2["status"], "already_confirmed")

        # Unknown barcode
        result3 = self.Line.scan_barcode_on_manifest(
            manifest.id, "NOT-A-REAL-BARCODE",
        )
        self.assertEqual(result3["status"], "not_found")

    # ==================================================================
    # test_04 — blocking damage flag creates PO and blocks job
    # ==================================================================
    def test_04_blocking_damage_creates_po_and_blocks_job(self):
        job = self._make_job()
        self.assertFalse(
            job.is_blocked,
            "Fresh job should not be blocked.",
        )
        self.assertEqual(job.open_damage_count, 0)

        flag = self.Flag.create({
            "job_id": job.id,
            "product_id": self.product_a.id,
            "issue_type": "damaged_transit",
            "urgency": "blocking",
            "qty_affected": 2.0,
            "description": "Cab arrived with cracked front face.",
        })

        # Auto-PO created
        self.assertTrue(
            flag.replacement_po_id,
            "Blocking damaged_transit flag should auto-create PO.",
        )
        po = flag.replacement_po_id
        self.assertEqual(po.partner_id, self.vendor,
                         "Should pick the lowest-sequence active seller.")
        self.assertEqual(po.order_line.product_id, self.product_a)
        self.assertEqual(po.order_line.product_qty, 2.0)
        self.assertEqual(po.priority, "1")
        self.assertIn(job.name, po.origin)
        self.assertIn(flag.name, po.origin)

        # Flag state moved to reorder_pending
        self.assertEqual(flag.state, "reorder_pending")

        # Job is now blocked + has open damage count
        # Need to invalidate cache to pick up the compute
        job.invalidate_recordset()
        self.assertTrue(
            job.is_blocked,
            "Job with blocking open flag should be is_blocked=True.",
        )
        self.assertEqual(job.open_damage_count, 1)
        self.assertEqual(job.blocking_damage_count, 1)

    # ==================================================================
    # test_05 — resolving the blocking flag clears is_blocked
    # ==================================================================
    def test_05_resolving_blocking_flag_clears_is_blocked(self):
        job = self._make_job()
        # Attach a photo before creating so the resolve transition's
        # photo-required constraint is satisfied.
        photo = self._photo("damage.jpg")
        flag = self.Flag.create({
            "job_id": job.id,
            "product_id": self.product_a.id,
            "issue_type": "damaged_transit",
            "urgency": "blocking",
            "qty_affected": 1.0,
            "description": "Cracked corner.",
            "photo_ids": [(4, photo.id)],
        })
        job.invalidate_recordset()
        self.assertTrue(job.is_blocked)

        # Walk the workflow: vendor → received → resolve
        # State transitions also require photos on the destination
        # state (constraint).
        flag.action_confirm_vendor()  # reorder_pending → reorder_confirmed
        self.assertEqual(flag.state, "reorder_confirmed")

        # Mark replacement received needs another photo
        replacement_photo = self._photo("replacement.jpg")
        flag.write({"photo_ids": [(4, replacement_photo.id)]})
        flag.action_confirm_replacement_delivery()
        self.assertEqual(flag.state, "delivered")

        flag.action_resolve()
        self.assertEqual(flag.state, "resolved")

        job.invalidate_recordset()
        self.assertFalse(
            job.is_blocked,
            "Resolving the only blocking flag should clear is_blocked.",
        )
        self.assertEqual(job.open_damage_count, 0)

    # ==================================================================
    # test_06 — manifest sign-off creates damage flags
    # ==================================================================
    def test_06_manifest_signoff_creates_damage_flags(self):
        job = self._make_job()
        manifest = self._make_manifest(job, [
            (self.product_a, 1.0),
            (self.product_b, 1.0),
        ])

        # Line 1: OK
        line_a = manifest.line_ids.filtered(
            lambda l: l.product_id == self.product_a
        )
        line_a.action_set_ok()

        # Line 2: damaged + photo required
        line_b = manifest.line_ids.filtered(
            lambda l: l.product_id == self.product_b
        )
        line_photo = self._photo("line_b.jpg")
        line_b.write({
            "status": "damaged",
            "damage_type": "transit",
            "damage_description": "Wrap was torn, face dinged.",
            "photo_ids": [(4, line_photo.id)],
        })

        # Confirm with a delivery photo
        manifest.write({
            "delivery_photo_ids": [(4, self._photo("truck.jpg").id)],
        })
        manifest.action_sign_off()

        self.assertEqual(manifest.state, "discrepancy")
        # Damage flag spawned for the damaged line
        flag = self.Flag.search([
            ("manifest_line_id", "=", line_b.id),
        ], limit=1)
        self.assertTrue(flag, "Manifest sign-off must spawn a flag for "
                        "damaged lines.")
        self.assertEqual(flag.issue_type, "damaged_transit")
        # Non-missing transit damage defaults to non-blocking
        self.assertEqual(flag.urgency, "non_blocking")
        self.assertEqual(flag.product_id, self.product_b)

        # Job's delivery_confirmed flips on via the compute
        job.invalidate_recordset()
        self.assertTrue(
            job.delivery_confirmed,
            "Manifest in 'discrepancy' state must flip "
            "delivery_confirmed True.",
        )

    # ==================================================================
    # test_07 — barcode scan falls back to lot then default_code
    # ==================================================================
    def test_07_barcode_scan_falls_back_to_lot_then_default_code(self):
        job = self._make_job()
        manifest = self.Manifest.create({
            "job_id": job.id, "state": "open",
        })
        # Create a lot for product_b
        lot = self.env["stock.lot"].create({
            "name": "LOT-W2430-AB99",
            "product_id": self.product_b.id,
        })
        line = self.Line.create({
            "manifest_id": manifest.id,
            "sequence": 10,
            "product_id": self.product_b.id,
            "lot_id": lot.id,
            "qty_expected": 1.0,
        })

        # Scan by lot.name (not the product barcode)
        result = self.Line.scan_barcode_on_manifest(
            manifest.id, "LOT-W2430-AB99",
        )
        self.assertEqual(result["status"], "ok",
                         f"Expected ok via lot match, got {result}")
        self.assertEqual(line.status, "ok")

        # Reset + scan via default_code
        line.action_set_pending()
        result = self.Line.scan_barcode_on_manifest(
            manifest.id, "SB-W2430",
        )
        self.assertEqual(result["status"], "ok",
                         f"Expected ok via default_code match, got {result}")

    # ==================================================================
    # test_08 — vendor selection picks lowest-sequence active seller
    # ==================================================================
    def test_08_auto_po_picks_lowest_sequence_active_seller(self):
        job = self._make_job()
        # product_a has 2 sellers: vendor (seq 10) and vendor2 (seq 20).
        flag = self.Flag.create({
            "job_id": job.id,
            "product_id": self.product_a.id,
            "issue_type": "wrong_sku",
            "urgency": "blocking",
            "qty_affected": 1.0,
            "description": "Wrong cab arrived.",
        })
        self.assertTrue(flag.replacement_po_id)
        self.assertEqual(
            flag.replacement_po_id.partner_id, self.vendor,
            "Should select sequence=10 vendor over sequence=20.",
        )

    # ==================================================================
    # test_09 — no vendor configured = no PO + chatter note + no crash
    # ==================================================================
    def test_09_no_vendor_no_po_but_no_crash(self):
        job = self._make_job()
        # product_no_vendor has empty seller_ids
        flag = self.Flag.create({
            "job_id": job.id,
            "product_id": self.product_no_vendor.id,
            "issue_type": "damaged_transit",
            "urgency": "blocking",
            "qty_affected": 1.0,
            "description": "Damaged but no vendor configured.",
        })
        # Flag is still created (didn't roll back)
        self.assertTrue(flag.id)
        # State stays 'open' (auto-PO failed silently)
        self.assertEqual(flag.state, "open")
        self.assertFalse(flag.replacement_po_id)

        # Job IS still blocked even though PO failed
        job.invalidate_recordset()
        self.assertTrue(job.is_blocked)
