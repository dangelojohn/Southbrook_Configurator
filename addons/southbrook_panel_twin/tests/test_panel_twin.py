# SPDX-License-Identifier: LGPL-3.0-only
from odoo.tests.common import TransactionCase, tagged
from odoo.exceptions import ValidationError
from psycopg2 import IntegrityError
from odoo.tools import mute_logger


@tagged("post_install", "-at_install", "southbrook", "southbrook_panel_twin")
class TestPanelTwin(TransactionCase):

    def test_panel_gets_sequenced_name(self):
        panel = self.env["sb.panel"].create({"barcode": "BC-0001"})
        self.assertTrue(panel.name.startswith("SB-PANEL-"),
                        f"expected SB-PANEL- prefix, got {panel.name!r}")

    def test_barcode_must_be_unique(self):
        self.env["sb.panel"].create({"barcode": "BC-DUP"})
        with self.assertRaises(IntegrityError), mute_logger("odoo.sql_db"):
            with self.env.cr.savepoint():
                self.env["sb.panel"].create({"barcode": "BC-DUP"})

    def test_cycle_links_to_panel_and_rolls_up_qc(self):
        panel = self.env["sb.panel"].create({"barcode": "BC-QC-1"})
        self.env["sb.panel.cycle"].create({
            "panel_id": panel.id, "operation": "CUT", "qc_result": "pass",
        })
        self.env["sb.panel.cycle"].create({
            "panel_id": panel.id, "operation": "DRILL", "qc_result": "pass",
        })
        self.assertEqual(len(panel.cycle_ids), 2)
        self.assertEqual(panel.qc_result, "pass")

    def test_panel_qc_fails_if_any_cycle_fails(self):
        panel = self.env["sb.panel"].create({"barcode": "BC-QC-2"})
        self.env["sb.panel.cycle"].create({
            "panel_id": panel.id, "operation": "DRILL", "qc_result": "fail",
        })
        self.assertEqual(panel.qc_result, "fail")

    def test_event_stream_accepts_unmatched_events(self):
        # An event with no panel yet must be storable (telemetry arrives first).
        evt = self.env["sb.machine.event"].create({
            "event_type": "alarm", "machine_code": "DRILLTEQ",
            "payload": '{"code": "LOW_AIR"}',
        })
        self.assertFalse(evt.panel_id)
        panel = self.env["sb.panel"].create({"barcode": "BC-EVT-1"})
        evt.panel_id = panel.id
        self.assertIn(evt, panel.event_ids)

    def test_derive_customer_is_crash_safe_without_link(self):
        # A bare MO with no sale/partner link must not raise; customer stays empty.
        product = self.env["product.product"].create(
            {"name": "Twin Test Panel"})
        mo = self.env["mrp.production"].create({"product_id": product.id})
        panel = self.env["sb.panel"].create(
            {"barcode": "BC-CUST-1", "production_id": mo.id})
        panel._derive_customer()  # must not raise
        # No assertion on value (env-dependent); the point is no exception.
        self.assertTrue(True)

    def test_lookup_by_barcode_returns_panel_with_ordered_history(self):
        panel = self.env["sb.panel"].create({"barcode": "BC-LOOK-1"})
        self.env["sb.panel.cycle"].create({
            "panel_id": panel.id, "operation": "CUT",
            "timestamp": "2026-07-10 08:32:00",
        })
        self.env["sb.panel.cycle"].create({
            "panel_id": panel.id, "operation": "DRILL",
            "timestamp": "2026-07-10 10:08:00",
        })
        found = self.env["sb.panel"]._lookup_by_barcode("BC-LOOK-1")
        self.assertEqual(found, panel)
        # cycle_ids are _order'd by timestamp → CUT before DRILL
        self.assertEqual(found.cycle_ids.mapped("operation"), ["CUT", "DRILL"])

    def test_lookup_by_barcode_empty_when_missing(self):
        found = self.env["sb.panel"]._lookup_by_barcode("BC-DOES-NOT-EXIST")
        self.assertFalse(found)

    def _make_mo(self):
        product = self.env["product.product"].create({"name": "Sim Panel"})
        return self.env["mrp.production"].create({"product_id": product.id})

    def test_simulator_creates_panels_with_genealogy(self):
        mo = self._make_mo()
        panels = self.env["sb.panel"]._simulate_from_production(
            mo, panel_count=3, seed=42)
        self.assertEqual(len(panels), 3)
        for p in panels:
            self.assertEqual(p.production_id, mo)
            self.assertEqual(p.cycle_ids.mapped("operation"), ["CUT", "DRILL"])
            self.assertTrue(p.event_ids)

    def test_simulator_is_deterministic_with_seed(self):
        mo1 = self._make_mo()
        mo2 = self._make_mo()
        a = self.env["sb.panel"]._simulate_from_production(mo1, 3, seed=7)
        b = self.env["sb.panel"]._simulate_from_production(mo2, 3, seed=7)
        self.assertEqual(
            a.cycle_ids.mapped("duration_s"),
            b.cycle_ids.mapped("duration_s"),
            "same seed must produce identical cycle times",
        )
