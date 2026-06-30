# SPDX-License-Identifier: LGPL-3.0-only
"""Idempotency tests — the Hermes BOM is updated-in-place, never duplicated."""
from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase


CANNED_RESPONSE = {
    "product_enrichment": {"name": "X", "short_description": "x"},
    "bom": {
        "bom_type": "normal",
        "lines": [{"sku": "DUP-A", "name": "Dup A", "qty": 1}],
    },
    "audit": {"source_urls": [], "overall_confidence": 0.9},
}


class HermesDuplicatePreventionCase(TransactionCase):

    def setUp(self):
        super().setUp()
        self.env["product.product"].create({
            "name": "Dup A", "default_code": "DUP-A", "type": "consu",
        })
        self.template = self.env["product.template"].create({
            "name": "Dup Test Cabinet",
            "default_code": "DUP-TEST-1",
            "type": "consu",
        })
        self.env["ir.config_parameter"].sudo().set_param(
            "southbrook_hermes_bom.api_key", "TEST-KEY"
        )

    def _run_once(self):
        action = self.template.action_hermes_research_and_build_bom()
        wizard = self.env["hermes.wizard"].browse(action["res_id"])
        with patch(
            "odoo.addons.southbrook_hermes_bom.services."
            "hermes_service.HermesService.research",
            return_value=CANNED_RESPONSE,
        ):
            wizard.action_collect_and_research()
        wizard.action_apply()
        return wizard

    def test_second_run_updates_existing_bom_not_duplicates(self):
        self._run_once()
        self._run_once()
        boms = self.env["mrp.bom"].search([
            ("product_tmpl_id", "=", self.template.id),
            ("code", "ilike", "Hermes"),
        ])
        # Exactly one Hermes BOM survives both runs.
        self.assertEqual(len(boms), 1)

    def test_confirmed_bom_blocks_replacement(self):
        wizard = self._run_once()
        bom = wizard.job_id.bom_id
        # Simulate "the BOM has been used by an MO" — the wizard
        # detects this via mrp.production lookup, so we create a
        # minimal MO that points at the bom.
        product = self.env["product.product"].create({
            "name": "MO Product",
            "default_code": "DUP-MO-1",
            "type": "consu",
        })
        self.env["mrp.production"].create({
            "product_id": product.id,
            "product_qty": 1.0,
            "bom_id": bom.id,
            "product_uom_id": product.uom_id.id,
        })
        # Now run a second wizard — apply must refuse.
        action = self.template.action_hermes_research_and_build_bom()
        wizard2 = self.env["hermes.wizard"].browse(action["res_id"])
        with patch(
            "odoo.addons.southbrook_hermes_bom.services."
            "hermes_service.HermesService.research",
            return_value=CANNED_RESPONSE,
        ):
            wizard2.action_collect_and_research()
        # Existing-BOM detection should mark it confirmed.
        self.assertEqual(wizard2.existing_bom_state, "confirmed")
        with self.assertRaises(UserError):
            wizard2.action_apply()

    def test_audit_job_per_wizard_invocation(self):
        # Two runs ⇒ two jobs.
        w1 = self._run_once()
        w2 = self._run_once()
        self.assertNotEqual(w1.job_id.id, w2.job_id.id)
        jobs = self.env["hermes.research.job"].search([
            ("product_template_id", "=", self.template.id),
        ])
        self.assertEqual(len(jobs), 2)
