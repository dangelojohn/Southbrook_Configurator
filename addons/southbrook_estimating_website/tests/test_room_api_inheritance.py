# SPDX-License-Identifier: LGPL-3.0-only
"""Regression tests — `SouthbrookRoomApi` must expose `_southbrook_resolve_order`.

Before the 2026-07-01 mixin refactor, `SouthbrookRoomApi(SouthbrookKitchenPlanner)`
inherited nothing useful because the resolver used to live on
`SouthbrookOrderBuilderPortal` — a sibling class that RoomApi does NOT extend.
Every /southbrook/api/order/<id>/... call therefore raised
    AttributeError: '<...RoomApi...>' object has no attribute '_southbrook_resolve_order'

The existing `test_room_api` suite monkey-patched the method onto the controller
instance for each test case, silently masking the defect. These tests exercise
the plain-class MRO instead, so they'd have failed pre-fix.
"""
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "southbrook_room_api")
class TestRoomApiInheritance(TransactionCase):

    def test_room_api_inherits_order_resolver(self):
        from odoo.addons.southbrook_estimating_website.controllers.room_api import (
            SouthbrookRoomApi,
        )
        self.assertTrue(
            hasattr(SouthbrookRoomApi, "_southbrook_resolve_order"),
            "SouthbrookRoomApi must inherit _southbrook_resolve_order via the "
            "shared mixin — a broken MRO here means every "
            "/southbrook/api/order/<id>/... call blows up at runtime.",
        )
        self.assertTrue(
            callable(SouthbrookRoomApi._southbrook_resolve_order),
        )

    def test_kitchen_planner_inherits_order_resolver(self):
        from odoo.addons.southbrook_estimating_website.controllers.main import (
            SouthbrookKitchenPlanner,
        )
        self.assertTrue(
            hasattr(SouthbrookKitchenPlanner, "_southbrook_resolve_order"),
        )

    def test_order_builder_portal_inherits_order_resolver(self):
        from odoo.addons.southbrook_estimating_website.controllers.main import (
            SouthbrookOrderBuilderPortal,
        )
        self.assertTrue(
            hasattr(SouthbrookOrderBuilderPortal, "_southbrook_resolve_order"),
        )

    def test_mixin_is_single_source_of_truth(self):
        """All three controllers must resolve to the same function object.

        Guards against a future 'quick fix' that reintroduces duplication
        (paste the body back into one class + forget the others) rather
        than sharing the mixin.
        """
        from odoo.addons.southbrook_estimating_website.controllers.main import (
            SouthbrookKitchenPlanner,
            SouthbrookOrderBuilderPortal,
        )
        from odoo.addons.southbrook_estimating_website.controllers.room_api import (
            SouthbrookRoomApi,
        )
        f = SouthbrookRoomApi._southbrook_resolve_order
        self.assertIs(SouthbrookKitchenPlanner._southbrook_resolve_order, f)
        self.assertIs(SouthbrookOrderBuilderPortal._southbrook_resolve_order, f)
