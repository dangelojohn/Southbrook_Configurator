# addons/southbrook_os/tests/test_public_endpoint.py
from odoo.tests.common import HttpCase, tagged


@tagged("post_install", "-at_install", "southbrook", "southbrook_os", "-standard")
class TestOsPublicEndpoint(HttpCase):
    def test_os_json_returns_only_public_sections(self):
        """The public endpoint must expose ONLY sections whose canonical
        `audience:` frontmatter includes `public` (today: just the charter),
        and must NOT leak audience-scoped internal content — this is the
        regression guard for the CRITICAL infra/knowledge-base disclosure."""
        resp = self.url_open("/southbrook/os.json")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("sections", data)
        self.assertIn("publication", data)
        slugs = {s["slug"] for s in data["sections"]}
        # The one public-tagged section is served…
        self.assertIn("00_charter", slugs)
        # …and internal sections are NOT leaked to anonymous callers.
        for internal in ("20_systems_topology", "01_company", "02_catalog",
                         "05_production", "06_plm"):
            self.assertNotIn(
                internal, slugs,
                "internal section %r must never appear on the public endpoint"
                % internal)
        # Every served section really is public-tagged.
        for s in data["sections"]:
            self.assertIn("public", (s.get("audience_tags") or "").split(","))

    def test_public_get_does_not_write_publications(self):
        """The anonymous route is read-only: hitting it must not create a
        publication row (building is the cron/OSRO job)."""
        Pub = self.env["southbrook.os.publication"]
        before = Pub.search_count([])
        self.url_open("/southbrook/os.json")
        self.url_open("/southbrook/os.json")
        self.assertEqual(Pub.search_count([]), before,
                         "public GET must not build publications")

    def test_section_payload_shape(self):
        resp = self.url_open("/southbrook/os.json")
        data = resp.json()
        self.assertTrue(data["sections"], "expected at least the public charter")
        section = data["sections"][0]
        for key in ("slug", "name", "version", "source", "body", "last_updated_at"):
            self.assertIn(key, section)
