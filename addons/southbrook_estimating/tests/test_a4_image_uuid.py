# SPDX-License-Identifier: LGPL-3.0-only
"""A4 — UUID-versioned catalog-icon URLs.

Asserts:
  - x_image_uuid + x_image_filename fields exist on product.template
  - Writing them round-trips through the ORM
  - The /southbrook/catalog/icon/<uuid>/<filename> route resolves
    a matching template's image_1920 to image bytes
  - Unknown UUIDs return 404
"""
import base64

from odoo.tests.common import HttpCase, TransactionCase, tagged

# A minimal 1×1 PNG (transparent) used as test image content.
_TINY_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\xfc\xcf"
    b"\xc0\x00\x00\x00\x03\x00\x01\xe3]\xc5\x06\x00\x00\x00\x00IEND\xaeB`\x82"
)


@tagged("post_install", "-at_install", "southbrook", "estimating", "a4",
        "image_uuid")
class TestA4ImageUuidFields(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Template = cls.env["product.template"]

    def test_x_image_uuid_field_exists(self):
        self.assertIn("x_image_uuid", self.Template._fields)
        self.assertIn("x_image_filename", self.Template._fields)

    def test_round_trip(self):
        tmpl = self.Template.create({
            "name": "A4 Test Template",
            "type": "consu",
            "x_image_uuid": "deadbeef-1111-2222-3333-444455556666",
            "x_image_filename": "test image.png",
        })
        self.assertEqual(tmpl.x_image_uuid,
                         "deadbeef-1111-2222-3333-444455556666")
        self.assertEqual(tmpl.x_image_filename, "test image.png")

    def test_uuid_indexed(self):
        # Confirms the field is indexed; matters because the controller
        # does a search by uuid on every request.
        f = self.Template._fields["x_image_uuid"]
        self.assertTrue(getattr(f, "index", False),
                        "x_image_uuid must be indexed for controller perf")


@tagged("post_install", "-at_install", "southbrook", "estimating", "a4",
        "image_uuid", "http")
class TestA4CatalogIconController(HttpCase):

    def test_controller_serves_image_bytes(self):
        Template = self.env["product.template"]
        tmpl = Template.create({
            "name": "A4 HTTP Test Template",
            "type": "consu",
            "x_image_uuid": "deadbeef-aaaa-bbbb-cccc-ddddeeeeffff",
            "image_1920": base64.b64encode(_TINY_PNG).decode("ascii"),
        })
        response = self.url_open(
            f"/southbrook/catalog/icon/{tmpl.x_image_uuid}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("Content-Type"), "image/png")
        self.assertIn("max-age=31536000",
                      response.headers.get("Cache-Control", ""))
        self.assertEqual(response.content, _TINY_PNG)

    def test_controller_returns_404_for_unknown_uuid(self):
        response = self.url_open(
            "/southbrook/catalog/icon/00000000-0000-0000-0000-000000000000")
        self.assertEqual(response.status_code, 404)

    def test_controller_accepts_optional_filename(self):
        Template = self.env["product.template"]
        tmpl = Template.create({
            "name": "A4 HTTP Filename Test",
            "type": "consu",
            "x_image_uuid": "12345678-9999-aaaa-bbbb-ccccddddeeee",
            "image_1920": base64.b64encode(_TINY_PNG).decode("ascii"),
        })
        response = self.url_open(
            f"/southbrook/catalog/icon/{tmpl.x_image_uuid}/"
            "ignored-cosmetic-filename.png")
        self.assertEqual(response.status_code, 200)
