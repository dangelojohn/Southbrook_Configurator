# addons/southbrook_os/tests/test_public_endpoint.py
from odoo.tests.common import HttpCase, tagged


@tagged("post_install", "-at_install", "southbrook", "southbrook_os", "-standard")
class TestOsPublicEndpoint(HttpCase):
    def test_os_json_returns_sections(self):
        resp = self.url_open("/southbrook/os.json")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("sections", data)
        self.assertIn("publication", data)
        self.assertGreaterEqual(len(data["sections"]), 5)
        # At least the charter should be present
        slugs = {s["slug"] for s in data["sections"]}
        self.assertIn("00_charter", slugs)

    def test_section_payload_shape(self):
        resp = self.url_open("/southbrook/os.json")
        data = resp.json()
        section = data["sections"][0]
        for key in ("slug", "name", "version", "source", "body", "last_updated_at"):
            self.assertIn(key, section)
