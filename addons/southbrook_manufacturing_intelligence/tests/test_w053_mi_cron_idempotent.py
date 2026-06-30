# SPDX-License-Identifier: LGPL-3.0-only
"""W053 — MI recompute sweep cron + idempotent recompute.

The 5-min cron sweeps in-flight MOs and calls _recompute_production.
The contract: when nothing changed, NO write hits the DB so the cron
is safe at any frequency.
"""
from unittest.mock import patch

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestW053MiCronIdempotent(TransactionCase):

    def test_cron_method_exists_on_mo(self):
        """The sweep entry point is callable on mrp.production model."""
        self.assertTrue(
            hasattr(self.env["mrp.production"], "_cron_mi_recompute_sweep"),
            "_cron_mi_recompute_sweep must exist for the ir.cron to dispatch.",
        )

    def test_cron_record_exists_and_active(self):
        """Cron data record loaded at 5-min interval."""
        cron = self.env.ref(
            "southbrook_manufacturing_intelligence.cron_mi_recompute_sweep",
            raise_if_not_found=False,
        )
        self.assertTrue(cron, "cron_mi_recompute_sweep record should exist")
        self.assertEqual(cron.interval_number, 5)
        self.assertEqual(cron.interval_type, "minutes")
        self.assertTrue(cron.active)

    def test_recompute_is_idempotent_no_change_no_write(self):
        """Calling _recompute_production twice yields zero writes on the
        second call when no upstream signals changed.
        """
        Engine = self.env["southbrook.mi.engine"]
        # Build a minimal MO. Using draft+manual write of MI fields keeps
        # this self-contained; the helper is what we're testing.
        product = self.env["product.product"].create({
            "name": "W053 MI test",
            "type": "consu",
            "is_storable": True,
        })
        mo = self.env["mrp.production"].create({
            "product_id": product.id,
            "product_qty": 1.0,
        })
        # First recompute — may or may not write depending on state.
        Engine._recompute_production(mo)
        # Capture the post-recompute snapshot.
        snapshot = {
            "x_mi_status": mo.x_mi_status,
            "x_mi_blocker_count": mo.x_mi_blocker_count,
            "x_mi_warning_count": mo.x_mi_warning_count,
            "x_mi_next_action": mo.x_mi_next_action,
        }
        # Patch write to assert it is NOT called for unchanged state.
        with patch.object(
            type(mo), "write", autospec=True, return_value=True
        ) as mock_write:
            Engine._recompute_production(mo)
            # The MI engine may call write on OTHER records (e.g. checks);
            # filter to writes on this MO's recordset.
            mo_writes = [
                call for call in mock_write.call_args_list
                if call.args and call.args[0] == mo
            ]
            self.assertEqual(
                mo_writes, [],
                "Second recompute must NOT write to the MO when MI state "
                "is unchanged (idempotency contract for W053 cron).",
            )
        # Snapshot should still match post-recompute.
        self.assertEqual(mo.x_mi_status, snapshot["x_mi_status"])
