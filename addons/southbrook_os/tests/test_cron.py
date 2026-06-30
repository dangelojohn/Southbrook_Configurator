# SPDX-License-Identifier: LGPL-3.0-only
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "southbrook_os")
class TestOsCron(TransactionCase):
    def test_cron_record_exists(self):
        cron = self.env.ref(
            "southbrook_os.cron_regenerate_os_sections",
            raise_if_not_found=False,
        )
        self.assertTrue(cron, "Expected southbrook_os.cron_regenerate_os_sections")
        self.assertEqual(cron.interval_type, "days")
        self.assertEqual(cron.interval_number, 1)
        self.assertTrue(cron.active)

    def test_cron_method_runs_without_error(self):
        # Should not raise even if some sources are missing
        self.env["southbrook.os.generators"].generate_all()
