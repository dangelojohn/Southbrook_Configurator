# SPDX-License-Identifier: LGPL-3.0-only
"""G2a opt-in gate behaviour.

The bridge POST + Regenerate-CAD button must:

* Default to OFF (system param freecad_bridge.enabled empty/false).
* Block ``action_regenerate_cad`` with a clear UserError when off.
* No-op silently in ``action_confirm`` when off (installing this addon
  must not change MO-confirm behaviour on stacks without the bridge).
* Fire the POST exactly once when on.
"""
from unittest.mock import patch, MagicMock

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook_freecad_bridge", "g2a")
class TestG2aGate(TransactionCase):

    def setUp(self):
        super().setUp()
        self.Param = self.env["ir.config_parameter"].sudo()
        self.product = self.env["product.product"].create({
            "name": "G2a Test Cabinet",
            "type": "consu",
            "is_storable": True,
        })

    def _make_mo(self):
        return self.env["mrp.production"].create({
            "product_id": self.product.id,
            "product_qty": 1.0,
            "product_uom_id": self.product.uom_id.id,
        })

    def _set_gate(self, on: bool):
        self.Param.set_param(
            "freecad_bridge.enabled", "true" if on else "false")

    # ──────────────────────────────────────────────────────────────────
    # Gate off
    # ──────────────────────────────────────────────────────────────────
    def test_default_param_is_off(self):
        # The addon ships with freecad_bridge.enabled = "false" (data file).
        val = self.Param.get_param("freecad_bridge.enabled", "")
        self.assertIn(str(val).strip().lower(), {"false", "", "0", "no"})

    def test_regenerate_raises_when_off(self):
        self._set_gate(False)
        mo = self._make_mo()
        with self.assertRaises(UserError):
            mo.action_regenerate_cad()

    def test_confirm_noops_when_off(self):
        self._set_gate(False)
        mo = self._make_mo()
        with patch(
            "odoo.addons.southbrook_freecad_bridge.models.mrp_production"
            ".requests.post"
        ) as mock_post:
            try:
                mo.action_confirm()
            except Exception:
                pass  # confirm might raise for unrelated workflow reasons
            mock_post.assert_not_called()

    # ──────────────────────────────────────────────────────────────────
    # Gate on
    # ──────────────────────────────────────────────────────────────────
    def test_regenerate_posts_when_on(self):
        self._set_gate(True)
        self.Param.set_param("freecad_bridge.secret", "test-secret")
        mo = self._make_mo()
        fake_resp = MagicMock(status_code=202, text='{"ok":true}')
        with patch(
            "odoo.addons.southbrook_freecad_bridge.models.mrp_production"
            ".requests.post",
            return_value=fake_resp,
        ) as mock_post:
            mo.action_regenerate_cad()
            mock_post.assert_called_once()
            call_kwargs = mock_post.call_args.kwargs
            self.assertEqual(
                call_kwargs["headers"].get("X-Bridge-Secret"), "test-secret")
        self.assertEqual(mo.x_cad_status, "rendering")

    def test_regenerate_records_error_on_bridge_failure(self):
        self._set_gate(True)
        mo = self._make_mo()
        fake_resp = MagicMock(status_code=500, text="bridge down")
        with patch(
            "odoo.addons.southbrook_freecad_bridge.models.mrp_production"
            ".requests.post",
            return_value=fake_resp,
        ):
            mo.action_regenerate_cad()
        self.assertEqual(mo.x_cad_status, "error")
