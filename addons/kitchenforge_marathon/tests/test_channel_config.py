# SPDX-License-Identifier: LGPL-3.0-only
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "kitchenforge", "marathon")
class TestChannelConfig(TransactionCase):

    def test_get_active_creates_singleton(self):
        Cfg = self.env["kitchenforge.marathon.channel.config"]
        cfg1 = Cfg.get_active()
        cfg2 = Cfg.get_active()
        self.assertEqual(cfg1.id, cfg2.id)
        self.assertTrue(cfg1.enabled)

    def test_disabled_blocks_emit(self):
        cfg = self.env["kitchenforge.marathon.channel.config"].get_active()
        cfg.enabled = False
        product = self.env["product.product"].search([], limit=1)
        if not product:
            self.skipTest("no products in fresh DB")
        rec = self.env["kitchenforge.marathon.spec.event"].emit(product=product)
        self.assertFalse(rec)
