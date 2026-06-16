# addons/southbrook_hermes/tests/test_tool_decorator.py
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "hermes")
class TestToolDecorator(TransactionCase):
    def test_registry_collects_decorated_functions(self):
        from odoo.addons.southbrook_hermes.tools.decorator import TOOL_REGISTRY
        slugs = {t["slug"] for t in TOOL_REGISTRY}
        for required in ["list_my_orders", "get_order_status", "get_order_line"]:
            self.assertIn(required, slugs)

    def test_registry_filter_by_persona_and_tier(self):
        from odoo.addons.southbrook_hermes.tools.decorator import (
            TOOL_REGISTRY, registry_for_persona)
        slice_ = registry_for_persona("trade_partner", "T0+T1")
        for tool in TOOL_REGISTRY:
            if "trade_partner" in tool["personas"] and tool["tier"] in ("T0", "T1"):
                self.assertIn(tool["slug"], [t["slug"] for t in slice_])
        for tool in slice_:
            self.assertIn(tool["tier"], ("T0", "T1"))
