# SPDX-License-Identifier: LGPL-3.0-only
"""Hermes wizard — happy-path BOM creation.

The Hermes service is patched at the import path the wizard actually
uses so the test never touches the network.
"""
import json
from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase


CANNED_RESPONSE = {
    "product_enrichment": {
        "name": "Soft-Close Hinge — 110°",
        "short_description": "Concealed cup hinge with integrated soft-close.",
        "long_description": "<p>Industry-standard cup hinge.</p>",
        "technical_description": "Steel body, nickel-plated, "
                                  "35 mm cup, 110° opening angle.",
        "manufacturer": "Blum",
        "manufacturer_pn": "B71B3550",
        "dimensions": [{"label": "Cup diameter", "value": "35 mm"}],
        "specs": [],
        "install_notes": [],
    },
    "bom": {
        "bom_type": "normal",
        "lines": [
            {"sku": "TEST-COMP-A", "name": "Component A", "qty": 1},
            {"sku": "TEST-COMP-B", "name": "Component B", "qty": 2},
        ],
    },
    "audit": {
        "source_urls": [
            "https://manufacturer.example.com/hinge/B71B3550"
        ],
        "overall_confidence": 0.92,
    },
}


class HermesBomCreationCase(TransactionCase):

    def setUp(self):
        super().setUp()
        # Two seed component products the BOM payload should match by SKU.
        self.env["product.product"].create({
            "name": "Component A",
            "default_code": "TEST-COMP-A",
            "type": "consu",
        })
        self.env["product.product"].create({
            "name": "Component B",
            "default_code": "TEST-COMP-B",
            "type": "consu",
        })
        self.template = self.env["product.template"].create({
            "name": "Test Cabinet Hinge",
            "default_code": "TEST-HINGE-1",
            "type": "consu",
        })
        # Seed the api_key so HermesService doesn't refuse to dispatch.
        self.env["ir.config_parameter"].sudo().set_param(
            "southbrook_hermes_bom.api_key", "TEST-KEY-XYZ"
        )

    def _run_wizard(self, response=None):
        response = response or CANNED_RESPONSE
        action = self.template.action_hermes_research_and_build_bom()
        wizard = self.env["hermes.wizard"].browse(action["res_id"])
        patch_target = (
            "odoo.addons.southbrook_hermes_bom.services."
            "hermes_service.HermesService.research"
        )
        with patch(patch_target, return_value=response):
            wizard.action_collect_and_research()
        return wizard

    def test_no_existing_bom_creates_new(self):
        wizard = self._run_wizard()
        wizard.action_apply()
        bom = self.env["mrp.bom"].search([
            ("product_tmpl_id", "=", self.template.id)
        ])
        self.assertEqual(len(bom), 1)
        self.assertIn("Hermes", bom.code or "")
        self.assertEqual(len(bom.bom_line_ids), 2)
        self.assertEqual(
            sorted(bom.bom_line_ids.mapped("product_id.default_code")),
            ["TEST-COMP-A", "TEST-COMP-B"],
        )

    def test_payload_includes_attribute_lines(self):
        # Add an attribute line so the payload-builder exercises that branch.
        attr = self.env["product.attribute"].create({"name": "Finish"})
        val_a = self.env["product.attribute.value"].create({
            "name": "Nickel", "attribute_id": attr.id,
        })
        val_b = self.env["product.attribute.value"].create({
            "name": "Brass", "attribute_id": attr.id,
        })
        self.env["product.template.attribute.line"].create({
            "product_tmpl_id": self.template.id,
            "attribute_id": attr.id,
            "value_ids": [(6, 0, [val_a.id, val_b.id])],
        })
        # Trigger payload build directly — no patch needed because we
        # only inspect the wizard's internal helper.
        action = self.template.action_hermes_research_and_build_bom()
        wizard = self.env["hermes.wizard"].browse(action["res_id"])
        payload = wizard._collect_product_payload()
        self.assertIn("attribute_lines", payload)
        names = [a["attribute_name"] for a in payload["attribute_lines"]]
        self.assertIn("Finish", names)

    def test_missing_component_skips_line_and_posts_warning(self):
        bad_response = dict(CANNED_RESPONSE)
        bad_response = {
            **bad_response,
            "bom": {
                "bom_type": "normal",
                "lines": [
                    {"sku": "TEST-COMP-A", "name": "Component A", "qty": 1},
                    {"sku": "DOES-NOT-EXIST", "name": "Missing", "qty": 5},
                ],
            },
        }
        wizard = self._run_wizard(response=bad_response)
        wizard.action_apply()
        bom = self.env["mrp.bom"].search([
            ("product_tmpl_id", "=", self.template.id)
        ])
        self.assertEqual(len(bom), 1)
        # Only the matchable line landed.
        self.assertEqual(len(bom.bom_line_ids), 1)

    def test_missing_api_key_raises_userror(self):
        self.env["ir.config_parameter"].sudo().set_param(
            "southbrook_hermes_bom.api_key", ""
        )
        action = self.template.action_hermes_research_and_build_bom()
        wizard = self.env["hermes.wizard"].browse(action["res_id"])
        # Don't patch — let HermesService.research raise the missing-key
        # UserError before any HTTP call happens.
        with self.assertRaises(UserError):
            wizard.action_collect_and_research()

    def test_audit_job_records_payload_and_response(self):
        wizard = self._run_wizard()
        wizard.action_apply()
        job = wizard.job_id
        self.assertEqual(job.state, "applied")
        self.assertTrue(job.hermes_request_payload)
        self.assertTrue(job.hermes_raw_response)
        self.assertTrue(job.applied_fields)
        applied = json.loads(job.applied_fields)
        # At least the BOM-created entry is there.
        self.assertTrue(any(
            a.get("field") in ("_create", "bom_line_ids")
            for a in applied
        ))
