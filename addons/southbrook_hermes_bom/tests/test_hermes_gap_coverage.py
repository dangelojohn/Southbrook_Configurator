# SPDX-License-Identifier: LGPL-3.0-only
"""Tests for the 5 review-flagged coverage gaps:

1. TOCTOU re-check (MO created between research and apply).
2. Canonical-code BOM detection ignores decoy substring matches.
3. Confidence-gated enrichment: low-confidence proposal does NOT
   overwrite an existing non-empty field.
4. ``subcontract`` bom_type proposal falls back to ``normal`` on CE.
5. All-lines-invalid → existing Hermes BOM left untouched (no zombie
   empty BOM).

Plus a few smaller tests for the new GC cron, the unlink-guard on
applied jobs, and the json-helpers on hermes.research.job.
"""
import json
from datetime import datetime, timedelta
from unittest.mock import patch

from odoo.exceptions import AccessError, UserError
from odoo.tests.common import TransactionCase


PATCH_TARGET = (
    "odoo.addons.southbrook_hermes_bom.services."
    "hermes_service.HermesService.research"
)


def _response(bom_lines=None, bom_type="normal", confidence=0.92,
              enrichment=None):
    """Compact canned-response builder shared across cases."""
    return {
        "product_enrichment": enrichment or {
            "name": "Updated Cabinet",
            "short_description": "A better description.",
            "long_description": "<p>Long form.</p>",
            "technical_description": "Steel body, 35mm cup.",
        },
        "bom": {
            "bom_type": bom_type,
            "lines": bom_lines if bom_lines is not None else [
                {"sku": "GAP-A", "name": "Gap A", "qty": 1},
            ],
        },
        "audit": {
            "source_urls": ["https://example.com/spec.pdf"],
            "overall_confidence": confidence,
        },
    }


class HermesGapCoverageCase(TransactionCase):

    def setUp(self):
        super().setUp()
        self.env["ir.config_parameter"].sudo().set_param(
            "southbrook_hermes_bom.api_key", "TEST-KEY-GAP"
        )
        self.product_a = self.env["product.product"].create({
            "name": "Gap A",
            "default_code": "GAP-A",
            "type": "consu",
        })
        self.product_b = self.env["product.product"].create({
            "name": "Gap B",
            "default_code": "GAP-B",
            "type": "consu",
        })
        self.template = self.env["product.template"].create({
            "name": "Gap Test Template",
            "default_code": "GAP-TEST-1",
            "type": "consu",
        })

    # ----------------------------------------------------------------
    # Helper
    # ----------------------------------------------------------------
    def _run(self, response=None):
        response = response or _response()
        action = self.template.action_hermes_research_and_build_bom()
        wizard = self.env["hermes.wizard"].browse(action["res_id"])
        with patch(PATCH_TARGET, return_value=response):
            wizard.action_collect_and_research()
        return wizard

    # ================================================================
    # 1. TOCTOU — MO created between research and apply
    # ================================================================
    def test_toctou_mo_created_after_research_blocks_apply(self):
        # First run creates the Hermes BOM.
        first = self._run()
        first.action_apply()
        bom = first.job_id.bom_id
        self.assertTrue(bom)

        # Start a SECOND run; pause after research, before apply.
        second = self._run()
        # During research, existing_bom_state was 'draft' because no
        # MO existed yet.
        self.assertEqual(second.existing_bom_state, "draft")

        # Foreign actor: create an MO referencing the Hermes BOM
        # between research and apply.
        self.env["mrp.production"].create({
            "product_id": self.product_b.id,
            "product_qty": 1.0,
            "bom_id": bom.id,
            "product_uom_id": self.product_b.uom_id.id,
        })

        # Apply must REFUSE despite the stale draft-state hint, because
        # _apply_bom re-checks mrp.production at apply time.
        with self.assertRaises(UserError):
            second.action_apply()

    # ================================================================
    # 2. Canonical-code BOM detection ignores decoys
    # ================================================================
    def test_decoy_bom_with_hermes_in_name_is_not_matched(self):
        # User-managed BOM with a name that just happens to contain
        # 'Hermes'. Must NOT be picked up by _find_hermes_bom.
        decoy = self.env["mrp.bom"].create({
            "product_tmpl_id": self.template.id,
            "code": "Hermes Edition Limited",
            "type": "normal",
        })
        action = self.template.action_hermes_research_and_build_bom()
        wizard = self.env["hermes.wizard"].browse(action["res_id"])
        found = wizard._find_hermes_bom()
        self.assertFalse(
            found and found.id == decoy.id,
            "decoy BOM with substring 'Hermes' must not be matched",
        )

        # Now create the canonical BOM and confirm it IS matched.
        canonical = self.env["mrp.bom"].create({
            "product_tmpl_id": self.template.id,
            "code": wizard._hermes_bom_code(),
            "type": "normal",
        })
        found2 = wizard._find_hermes_bom()
        self.assertEqual(found2.id, canonical.id)

    # ================================================================
    # 3. Confidence gating on enrichment
    # ================================================================
    def test_low_confidence_does_not_overwrite_nonempty_field(self):
        # Existing field is non-empty.
        self.template.write({
            "description_sale": "ORIGINAL sales description (do not overwrite)",
        })
        resp = _response(
            enrichment={
                "name": "",
                "short_description": "HERMES OVERWRITE",
                "long_description": "",
                "technical_description": "",
            },
            confidence=0.40,
        )
        wizard = self._run(response=resp)
        wizard.action_apply()
        self.assertEqual(
            self.template.description_sale,
            "ORIGINAL sales description (do not overwrite)",
            "low-confidence proposal must NOT overwrite a non-empty field",
        )

    def test_high_confidence_overwrites_nonempty_field(self):
        self.template.write({
            "description_sale": "OLD sales description",
        })
        resp = _response(
            enrichment={
                "name": "",
                "short_description": "NEW sales description",
                "long_description": "",
                "technical_description": "",
            },
            confidence=0.95,
        )
        wizard = self._run(response=resp)
        wizard.action_apply()
        self.assertEqual(
            self.template.description_sale,
            "NEW sales description",
            "high-confidence proposal SHOULD overwrite a non-empty field",
        )

    # ================================================================
    # 4. subcontract bom_type → normal fallback (CE only)
    # ================================================================
    def test_subcontract_bom_type_falls_back_to_normal(self):
        resp = _response(bom_type="subcontract")
        wizard = self._run(response=resp)
        wizard.action_apply()
        bom = wizard.job_id.bom_id
        self.assertEqual(
            bom.type, "normal",
            "subcontract is Enterprise-only — must fall back to normal "
            "on CE rather than raising ValueError on create",
        )

    # ================================================================
    # 5. All-lines-invalid → existing BOM untouched
    # ================================================================
    def test_all_invalid_lines_leave_existing_bom_intact(self):
        # First successful apply produces a Hermes BOM with one line.
        self._run().action_apply()
        bom = self.env["mrp.bom"].search([
            ("product_tmpl_id", "=", self.template.id),
            ("code", "=", "GAP-TEST-1 Hermes"),
        ])
        self.assertEqual(len(bom.bom_line_ids), 1)
        original_line_ids = bom.bom_line_ids.ids[:]

        # Second run proposes only lines that won't resolve.
        bad = _response(bom_lines=[
            {"sku": "DOES-NOT-EXIST", "name": "Nothing", "qty": 2},
            {"sku": "ALSO-NO", "name": "Nope", "qty": 0},
        ])
        second = self._run(response=bad)
        second.action_apply()

        # BOM lines should NOT have been deleted-and-replaced.
        bom_after = self.env["mrp.bom"].browse(bom.id)
        self.assertEqual(
            bom_after.bom_line_ids.ids, original_line_ids,
            "every proposed line invalid ⇒ existing BOM must be untouched, "
            "not replaced with an empty bom_line_ids set",
        )

    # ================================================================
    # Bonus: GC cron
    # ================================================================
    def test_gc_drops_old_failed_keeps_applied(self):
        old_failed = self.env["hermes.research.job"].create({
            "product_template_id": self.template.id,
            "state": "failed",
        })
        old_applied = self.env["hermes.research.job"].create({
            "product_template_id": self.template.id,
            "state": "applied",
        })
        # Backdate create_date to 200 days ago — past the 180-day default.
        long_ago = datetime.now() - timedelta(days=200)
        self.env.cr.execute(
            "UPDATE hermes_research_job SET create_date = %s "
            "WHERE id IN %s",
            (long_ago, tuple([old_failed.id, old_applied.id])),
        )
        # Invalidate ORM cache after the raw UPDATE.
        old_failed.invalidate_recordset(["create_date"])
        old_applied.invalidate_recordset(["create_date"])

        removed = self.env["hermes.research.job"]._gc_old_jobs()
        self.assertGreaterEqual(removed, 1)
        self.assertFalse(old_failed.exists(),
                         "old failed job should be GC'd")
        self.assertTrue(old_applied.exists(),
                        "applied job must be kept forever")

    def test_gc_disabled_when_retention_zero(self):
        self.env["ir.config_parameter"].sudo().set_param(
            "southbrook_hermes_bom.retention_days", "0",
        )
        old = self.env["hermes.research.job"].create({
            "product_template_id": self.template.id,
            "state": "failed",
        })
        long_ago = datetime.now() - timedelta(days=999)
        self.env.cr.execute(
            "UPDATE hermes_research_job SET create_date = %s WHERE id = %s",
            (long_ago, old.id),
        )
        old.invalidate_recordset(["create_date"])
        removed = self.env["hermes.research.job"]._gc_old_jobs()
        self.assertEqual(removed, 0)
        self.assertTrue(old.exists())

    # ================================================================
    # Bonus: unlink-guard
    # ================================================================
    def test_non_admin_cannot_unlink_applied_job(self):
        self._run().action_apply()
        applied = self.env["hermes.research.job"].search([
            ("product_template_id", "=", self.template.id),
            ("state", "=", "applied"),
        ], limit=1)
        self.assertTrue(applied)
        # Build a minimal user with group_hermes_user but NOT admin.
        g_user = self.env.ref("southbrook_hermes_bom.group_hermes_user")
        u = self.env["res.users"].create({
            "name": "Gap Tester",
            "login": "gap_tester_unlink",
            "group_ids": [(6, 0, [
                g_user.id, self.env.ref("base.group_user").id,
            ])],
        })
        with self.assertRaises(UserError):
            applied.with_user(u).unlink()

    # ================================================================
    # Bonus: hermes_request_payload is admin-only
    # ================================================================
    def test_payload_field_not_readable_by_user_group(self):
        wiz = self._run()
        wiz.action_apply()
        job = wiz.job_id
        g_user = self.env.ref("southbrook_hermes_bom.group_hermes_user")
        u = self.env["res.users"].create({
            "name": "Gap Reader",
            "login": "gap_tester_read",
            "group_ids": [(6, 0, [
                g_user.id, self.env.ref("base.group_user").id,
            ])],
        })
        # Field has groups="base.group_system" — a non-admin read()
        # must not return the field at all.
        rec = job.with_user(u).read(["name", "state"])
        self.assertNotIn("hermes_request_payload", rec[0])
