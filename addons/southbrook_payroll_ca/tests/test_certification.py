# SPDX-License-Identifier: LGPL-3.0-only
from datetime import timedelta

from odoo import fields
from odoo.tests.common import TransactionCase, tagged


@tagged("southbrook", "post_install", "-at_install")
class TestCertification(TransactionCase):
    def setUp(self):
        super().setUp()
        self.Cert = self.env["southbrook.payroll.certification"]
        self.emp = self.env["hr.employee"].create({"name": "Cert Emp"})

    def _mk(self, days_from_now):
        return self.Cert.create(
            {
                "name": "WHMIS 2015",
                "employee_id": self.emp.id,
                "issued_at": fields.Date.today() - timedelta(days=365),
                "expires_at": fields.Date.today() + timedelta(days=days_from_now),
            }
        )

    def test_expiry_status_computed(self):
        cert = self._mk(15)
        self.assertEqual(cert.expiry_status, "expiring_soon")

    def test_expiry_status_expired(self):
        cert = self._mk(-1)
        self.assertEqual(cert.expiry_status, "expired")

    def test_expiry_status_valid(self):
        cert = self._mk(120)
        self.assertEqual(cert.expiry_status, "valid")

    def test_cert_cron_posts_activity(self):
        self._mk(25)
        before = self.env["mail.activity"].search_count(
            [("res_model", "=", "southbrook.payroll.certification")]
        )
        self.Cert.cron_alert_expiring()
        after = self.env["mail.activity"].search_count(
            [("res_model", "=", "southbrook.payroll.certification")]
        )
        self.assertGreater(after, before)
