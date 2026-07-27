# SPDX-License-Identifier: LGPL-3.0-only
from odoo.tests.common import TransactionCase, tagged


@tagged("southbrook", "onshape")
class TestOnshapeCadUrl(TransactionCase):

    def test_field_exists(self):
        """x_onshape_cad_url exists on product.template"""
        tmpl = self.env["product.template"]
        self.assertIn("x_onshape_cad_url", tmpl._fields)

    def test_field_is_char(self):
        tmpl = self.env["product.template"]
        self.assertEqual(tmpl._fields["x_onshape_cad_url"].type, "char")

    def test_write_and_read(self):
        """URL round-trips through ORM without modification"""
        url = "https://cad.onshape.com/documents/abc/w/def/e/ghi"
        tmpl = self.env["product.template"].create({
            "name": "Test Cabinet",
            "type": "consu",
            "x_onshape_cad_url": url,
        })
        self.assertEqual(tmpl.x_onshape_cad_url, url)

    def test_empty_url_is_falsy(self):
        """Products without a URL have a falsy value"""
        tmpl = self.env["product.template"].create({
            "name": "No CAD Cabinet",
            "type": "consu",
        })
        self.assertFalse(tmpl.x_onshape_cad_url)
