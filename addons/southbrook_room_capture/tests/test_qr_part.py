# SPDX-License-Identifier: LGPL-3.0-only
"""Tests for the QR part-lookup backend added to southbrook_room_capture.

Covers:
  * southbrook.qr.part (AbstractModel) — dual-format payload resolution
    (legacy "sb-package:<id>" + signed "sb://pkg/<id>?..."), customer-
    safe serialization.
  * controllers/main.py's POST /southbrook/api/order/<id>/scan-part —
    ownership enforcement against the SCANNED package's own order (not
    just the route's own order_id), malformed/unknown-id handling, the
    nullable sale_order_line_id case, and the "no records created"
    read-only guarantee.

Follows the `stubbed_request` pattern established in
southbrook_estimating_website/tests/test_room_api.py (also used by
this addon's own test_room_capture.py): swap the `request` LocalProxy
in EVERY controller module whose code path is exercised —
`_southbrook_resolve_order`'s `request` binding lives in
southbrook_estimating_website.controllers.main (the mixin's home
module), not in this addon's own controller module, so both must be
swapped for the duration of each call.

No external calls are made anywhere in this flow (HMAC verification is
local, ORM lookups are local) so nothing needs mocking beyond `request`
itself.

Run with:
    odoo --no-http --test-enable -u southbrook_room_capture \\
        -d <db> --stop-after-init --test-tags=southbrook_room_capture
"""
from contextlib import contextmanager
from unittest.mock import MagicMock

from odoo.tests import TransactionCase, tagged

from odoo.addons.southbrook_room_capture.controllers import (
    main as ctrl_capture,
)
from odoo.addons.southbrook_estimating_website.controllers import (
    main as ctrl_main,
)


@contextmanager
def stubbed_request(env, user=None):
    """Swap `request` in both controller modules for the duration of
    the with-block. Mirrors test_room_capture.py's helper of the same
    name — `_southbrook_resolve_order`'s `request` binding lives in
    ctrl_main (the mixin's home module), not in our own
    controllers.main.
    """
    saved_capture = ctrl_capture.request
    saved_main = ctrl_main.request
    mock = MagicMock()
    mock.env = env if user is None else env(user=user.id)
    mock.session = {}
    mock.params = {}
    ctrl_capture.request = mock
    ctrl_main.request = mock
    try:
        yield mock
    finally:
        ctrl_capture.request = saved_capture
        ctrl_main.request = saved_main


@tagged("post_install", "-at_install", "southbrook", "southbrook_room_capture")
class TestQrPartModel(TransactionCase):
    """Direct tests of the southbrook.qr.part AbstractModel."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.QrPart = cls.env["southbrook.qr.part"]
        cls.Product = cls.env["product.product"]
        cls.Package = cls.env["sb.production.package"]
        cls.MO = cls.env["mrp.production"]
        cls.SaleOrder = cls.env["sale.order"]

        cls.partner_a = cls.env["res.partner"].create({
            "name": "Test Customer QR Part A",
            "email": "qr_part_a@southbrook.test",
        })

        cls.product_a = cls.Product.create({
            "name": "Base 2-Door Cabinet · 30in",
            "type": "consu",
            "is_storable": True,
            "default_code": "SB-BASE-30",
        })

        cls.order_a = cls.SaleOrder.create({
            "partner_id": cls.partner_a.id,
            "order_line": [(0, 0, {
                "product_id": cls.product_a.id,
                "product_uom_qty": 1.0,
                "name": 'Base 2-Door · Contemporary · 30"',
                "price_unit": 425.0,
            })],
        })
        cls.line_a = cls.order_a.order_line[0]
        cls.line_a.write({
            "zone": "base_run",
            "position_from_left_mm": 100,
        })

        cls.mo_a = cls.MO.create({
            "product_id": cls.product_a.id,
            "product_qty": 1.0,
        })
        cls.package_a = cls.Package.create({
            "mo_id": cls.mo_a.id,
            "sale_order_line_id": cls.line_a.id,
        })

        # Orphan package: legacy, no sale_order_line_id.
        cls.mo_orphan = cls.MO.create({
            "product_id": cls.product_a.id,
            "product_qty": 1.0,
        })
        cls.package_orphan = cls.Package.create({"mo_id": cls.mo_orphan.id})

    # ------------------------------------------------------------------
    # resolve_package_id
    # ------------------------------------------------------------------
    def test_resolve_legacy_payload(self):
        pkg_id = self.QrPart.resolve_package_id(
            "sb-package:%s" % self.package_a.id)
        self.assertEqual(pkg_id, self.package_a.id)

    def test_resolve_signed_payload(self):
        payload = self.env["southbrook.qr.payload"].build(
            "pkg", self.package_a.id)
        pkg_id = self.QrPart.resolve_package_id(payload)
        self.assertEqual(pkg_id, self.package_a.id)

    def test_resolve_signed_payload_wrong_kind_rejected(self):
        payload = self.env["southbrook.qr.payload"].build(
            "wo", self.package_a.id)
        pkg_id = self.QrPart.resolve_package_id(payload)
        self.assertIsNone(pkg_id)

    def test_resolve_signed_payload_bad_signature_rejected(self):
        payload = self.env["southbrook.qr.payload"].build(
            "pkg", self.package_a.id)
        forged = payload[:-4] + "beef"
        pkg_id = self.QrPart.resolve_package_id(forged)
        self.assertIsNone(pkg_id)

    def test_resolve_malformed_payload_rejected(self):
        for bad in ("not-a-qr-payload", "", None, 12345, "sb-package:abc"):
            self.assertIsNone(self.QrPart.resolve_package_id(bad))

    def test_resolve_out_of_range_id_rejected(self):
        # HIGH-1 regression: a package id beyond PostgreSQL int4 range
        # (or non-positive) must resolve to None — NOT reach the ORM,
        # where `WHERE id IN (<huge>)` would raise "integer out of range"
        # (unhandled 500). The id is attacker-controlled via the QR string.
        for bad in (
            "sb-package:99999999999999999999",   # >> int4 max
            "sb-package:2147483648",              # int4 max + 1
            "sb-package:0",
            "sb-package:-5",
        ):
            self.assertIsNone(
                self.QrPart.resolve_package_id(bad),
                "out-of-range/non-positive id must not resolve: %r" % bad,
            )

    # ------------------------------------------------------------------
    # serialize
    # ------------------------------------------------------------------
    def test_serialize_customer_safe_fields(self):
        result = self.QrPart.serialize(self.package_a, self.order_a.id)
        self.assertEqual(result["quote_number"], self.order_a.name)
        self.assertEqual(result["line_id"], self.line_a.id)
        self.assertTrue(result["in_current_order"])
        part = result["part"]
        self.assertEqual(part["product"]["id"], self.product_a.id)
        self.assertEqual(part["product"]["default_code"], "SB-BASE-30")
        self.assertEqual(part["name"], 'Base 2-Door · Contemporary · 30"')
        self.assertEqual(part["price_unit"], 425.0)
        self.assertEqual(part["zone"], "base_run")
        self.assertEqual(part["position_from_left_mm"], 100)
        # Internal fields must never appear on the part dict.
        for forbidden in (
            "standard_price", "cost_subtotal", "margin", "state",
            "mo_id", "cutlist_id", "hardware_package_id",
            "has_pricing_pending",
        ):
            self.assertNotIn(forbidden, part)

    def test_serialize_orphan_package_line_id_none(self):
        result = self.QrPart.serialize(self.package_orphan, self.order_a.id)
        self.assertIsNone(result["line_id"])
        self.assertIsNone(result["quote_number"])
        self.assertFalse(result["in_current_order"])
        self.assertIsNone(result["part"]["product"]["id"])

    def test_serialize_in_current_order_false_for_other_order(self):
        result = self.QrPart.serialize(self.package_a, self.order_a.id + 999999)
        self.assertFalse(result["in_current_order"])


@tagged("post_install", "-at_install", "southbrook", "southbrook_room_capture")
class TestScanPartController(TransactionCase):
    """Tests of the /southbrook/api/order/<id>/scan-part JSON-RPC route."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Product = cls.env["product.product"]
        cls.Package = cls.env["sb.production.package"]
        cls.MO = cls.env["mrp.production"]
        cls.SaleOrder = cls.env["sale.order"]

        # --- Partner A / Order A (the "current" order) ---------------
        cls.partner_a = cls.env["res.partner"].create({
            "name": "Test Customer Scan A",
            "email": "scan_a@southbrook.test",
        })
        cls.product_a = cls.Product.create({
            "name": "Base 2-Door Cabinet · Scan A",
            "type": "consu",
            "is_storable": True,
            "default_code": "SB-SCAN-A",
        })
        cls.order_a = cls.SaleOrder.create({
            "partner_id": cls.partner_a.id,
            "order_line": [(0, 0, {
                "product_id": cls.product_a.id,
                "product_uom_qty": 1.0,
                "name": "Base 2-Door · Scan A",
                "price_unit": 300.0,
            })],
        })
        cls.line_a = cls.order_a.order_line[0]
        cls.mo_a = cls.MO.create({
            "product_id": cls.product_a.id, "product_qty": 1.0,
        })
        cls.package_a = cls.Package.create({
            "mo_id": cls.mo_a.id, "sale_order_line_id": cls.line_a.id,
        })

        # --- Partner B / Order B (a DIFFERENT customer's order) ------
        cls.partner_b = cls.env["res.partner"].create({
            "name": "Test Customer Scan B (Stranger)",
            "email": "scan_b@southbrook.test",
        })
        cls.product_b = cls.Product.create({
            "name": "Base 2-Door Cabinet · Scan B",
            "type": "consu",
            "is_storable": True,
        })
        cls.order_b = cls.SaleOrder.create({
            "partner_id": cls.partner_b.id,
            "order_line": [(0, 0, {
                "product_id": cls.product_b.id,
                "product_uom_qty": 1.0,
                "name": "Base 2-Door · Scan B",
                "price_unit": 300.0,
            })],
        })
        cls.line_b = cls.order_b.order_line[0]
        cls.mo_b = cls.MO.create({
            "product_id": cls.product_b.id, "product_qty": 1.0,
        })
        cls.package_b = cls.Package.create({
            "mo_id": cls.mo_b.id, "sale_order_line_id": cls.line_b.id,
        })

        # --- Orphan package: legacy, no sale_order_line_id ------------
        cls.mo_orphan = cls.MO.create({
            "product_id": cls.product_a.id, "product_qty": 1.0,
        })
        cls.package_orphan = cls.Package.create({"mo_id": cls.mo_orphan.id})

        # --- Portal user owning order A --------------------------------
        portal_group = cls.env.ref("base.group_portal")
        cls.portal_user_a = cls.env["res.users"].create({
            "name": "Portal User Scan A",
            "login": "portal_scan_a@southbrook.test",
            "partner_id": cls.partner_a.id,
            "group_ids": [(6, 0, [portal_group.id])],
        })

        cls.controller = ctrl_capture.SouthbrookRoomCaptureApi()

    # ------------------------------------------------------------------
    # (a) valid legacy payload resolves
    # ------------------------------------------------------------------
    def test_legacy_payload_resolves(self):
        with stubbed_request(self.env):
            result = self.controller.southbrook_api_scan_part(
                self.order_a.id,
                payload="sb-package:%s" % self.package_a.id,
            )
        self.assertTrue(result.get("ok"), msg=result)
        self.assertEqual(result["quote_number"], self.order_a.name)
        self.assertEqual(result["line_id"], self.line_a.id)
        self.assertTrue(result["in_current_order"])
        self.assertEqual(result["part"]["product"]["id"], self.product_a.id)

    # ------------------------------------------------------------------
    # (b) valid signed payload resolves
    # ------------------------------------------------------------------
    def test_signed_payload_resolves(self):
        payload = self.env["southbrook.qr.payload"].build(
            "pkg", self.package_a.id)
        with stubbed_request(self.env):
            result = self.controller.southbrook_api_scan_part(
                self.order_a.id, payload=payload,
            )
        self.assertTrue(result.get("ok"), msg=result)
        self.assertEqual(result["quote_number"], self.order_a.name)
        self.assertEqual(result["line_id"], self.line_a.id)

    # ------------------------------------------------------------------
    # (c) ownership: package belonging to a DIFFERENT customer's order
    # ------------------------------------------------------------------
    def test_ownership_rejected_for_other_customers_package(self):
        """Portal user owns order A and is scanning WITHIN order A's
        route, but the scanned QR resolves to a package that belongs
        to order B (partner B, a different customer). Must be rejected
        with NO part data — owning order A does not grant access to
        order B's data just because the id was guessed/scanned.

        MEDIUM-1: the rejection is `not_found` (NOT `forbidden`) — the
        scanned-package id is attacker-controlled, so returning
        `forbidden` for "exists but not yours" vs `not_found` for
        "doesn't exist" would be an existence oracle for enumerating
        valid package ids. Both collapse to not_found; no data leaks."""
        with stubbed_request(self.env, user=self.portal_user_a):
            result = self.controller.southbrook_api_scan_part(
                self.order_a.id,
                payload="sb-package:%s" % self.package_b.id,
            )
        self.assertEqual(result.get("error"), "not_found")
        # regardless of the code, NO cross-customer data is ever returned
        self.assertNotIn("part", result)
        self.assertNotIn("quote_number", result)
        self.assertIsNot(result.get("ok"), True)

    def test_ownership_rejection_for_non_owning_portal_user_own_route(self):
        """A portal user who doesn't own order_a at all is rejected at
        the route's own <order_id> ownership check (belt-and-braces —
        this is the same guard analyze-photos uses)."""
        stranger_partner = self.env["res.partner"].create({
            "name": "Totally Unrelated Stranger",
        })
        stranger_portal_group = self.env.ref("base.group_portal")
        stranger_user = self.env["res.users"].create({
            "name": "Stranger Portal User",
            "login": "stranger_scan_part@southbrook.test",
            "partner_id": stranger_partner.id,
            "group_ids": [(6, 0, [stranger_portal_group.id])],
        })
        with stubbed_request(self.env, user=stranger_user):
            result = self.controller.southbrook_api_scan_part(
                self.order_a.id,
                payload="sb-package:%s" % self.package_a.id,
            )
        self.assertEqual(result.get("error"), "forbidden")

    # ------------------------------------------------------------------
    # (d) malformed payload -> invalid
    # ------------------------------------------------------------------
    def test_malformed_payload_invalid(self):
        with stubbed_request(self.env):
            result = self.controller.southbrook_api_scan_part(
                self.order_a.id, payload="not-a-qr-code-at-all",
            )
        self.assertEqual(result.get("error"), "invalid")

    def test_empty_payload_invalid(self):
        with stubbed_request(self.env):
            result = self.controller.southbrook_api_scan_part(
                self.order_a.id, payload="",
            )
        self.assertEqual(result.get("error"), "invalid")

    def test_non_string_payload_invalid(self):
        with stubbed_request(self.env):
            result = self.controller.southbrook_api_scan_part(
                self.order_a.id, payload=12345,
            )
        self.assertEqual(result.get("error"), "invalid")

    # ------------------------------------------------------------------
    # (e) unknown/nonexistent id -> not_found
    # ------------------------------------------------------------------
    def test_unknown_package_id_not_found(self):
        existing_ids = (
            self.package_a | self.package_b | self.package_orphan
        ).ids
        probe_id = max(existing_ids) + 100000
        with stubbed_request(self.env):
            result = self.controller.southbrook_api_scan_part(
                self.order_a.id, payload="sb-package:%s" % probe_id,
            )
        self.assertEqual(result.get("error"), "not_found")

    # ------------------------------------------------------------------
    # (f) package with sale_order_line_id=False -> not_found gracefully
    # ------------------------------------------------------------------
    def test_orphan_package_not_found_gracefully(self):
        with stubbed_request(self.env):
            result = self.controller.southbrook_api_scan_part(
                self.order_a.id,
                payload="sb-package:%s" % self.package_orphan.id,
            )
        self.assertEqual(result.get("error"), "not_found")

    # ------------------------------------------------------------------
    # (g) no records created by the flow
    # ------------------------------------------------------------------
    def test_no_records_created(self):
        Package = self.env["sb.production.package"]
        SaleOrder = self.env["sale.order"]
        SaleOrderLine = self.env["sale.order.line"]
        before = (
            Package.search_count([]),
            SaleOrder.search_count([]),
            SaleOrderLine.search_count([]),
        )
        with stubbed_request(self.env):
            self.controller.southbrook_api_scan_part(
                self.order_a.id,
                payload="sb-package:%s" % self.package_a.id,
            )
            self.controller.southbrook_api_scan_part(
                self.order_a.id,
                payload=self.env["southbrook.qr.payload"].build(
                    "pkg", self.package_a.id),
            )
            self.controller.southbrook_api_scan_part(
                self.order_a.id, payload="garbage",
            )
            self.controller.southbrook_api_scan_part(
                self.order_a.id, payload="sb-package:999999999",
            )
            self.controller.southbrook_api_scan_part(
                self.order_a.id,
                payload="sb-package:%s" % self.package_orphan.id,
            )
        after = (
            Package.search_count([]),
            SaleOrder.search_count([]),
            SaleOrderLine.search_count([]),
        )
        self.assertEqual(before, after)
