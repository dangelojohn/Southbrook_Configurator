# SPDX-License-Identifier: LGPL-3.0-only
from lxml import etree

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "pm_dashboard")
class TestSouthbrookPmDashboardViews(TransactionCase):

    def test_pm_dashboard_kanban_template_uses_record_values(self):
        view = self.env.ref("southbrook_mrp_pm.view_southbrook_pm_kanban")
        arch = etree.fromstring(view.arch_db.encode())

        self.assertFalse(
            arch.xpath(".//templates//field"),
            "PM dashboard kanban card template should avoid field widgets; "
            "they can break when archInfo.fieldNodes is stale or incomplete.",
        )
        self.assertTrue(
            arch.xpath(".//templates//t[contains(@t-esc, 'record.')]"),
        )
