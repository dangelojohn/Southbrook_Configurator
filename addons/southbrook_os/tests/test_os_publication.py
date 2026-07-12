# addons/southbrook_os/tests/test_os_publication.py
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "southbrook_os")
class TestOsPublication(TransactionCase):
    def setUp(self):
        super().setUp()
        Section = self.env["southbrook.os.section"]
        # Isolate from the canonical sections the post_init hook loads at
        # install — otherwise these fixed-slug creates collide (UNIQUE(slug))
        # and the len(snapshot)==2 assertions would count canonical rows too.
        Section.search([]).unlink()
        self.s1 = Section.create({
            "slug": "00_charter", "name": "Charter",
            "source": "canonical", "body": "v1 body",
        })
        self.s2 = Section.create({
            "slug": "02_catalog", "name": "Catalog",
            "source": "canonical", "body": "v1 body",
        })

    def test_publish_creates_snapshot_of_every_section(self):
        pub = self.env["southbrook.os.publication"].publish("2026-06")
        self.assertEqual(pub.calendar_key, "2026-06")
        self.assertTrue(pub.build_hash)
        self.assertEqual(len(pub.section_snapshot_ids), 2)
        for snap in pub.section_snapshot_ids:
            self.assertEqual(snap.section_version, 1)

    def test_publish_with_same_content_returns_existing_pub(self):
        first = self.env["southbrook.os.publication"].publish("2026-06")
        second = self.env["southbrook.os.publication"].publish("2026-06")
        self.assertEqual(first.id, second.id)

    def test_publish_after_section_change_makes_new_pub(self):
        self.env["southbrook.os.publication"].publish("2026-06")
        self.s1.bump_version(body="v2 body")
        new_pub = self.env["southbrook.os.publication"].publish("2026-06")
        # Same calendar_key but new build_hash
        self.assertEqual(new_pub.calendar_key, "2026-06")
        # Snapshot of s1 should be at version 2
        s1_snap = new_pub.section_snapshot_ids.filtered(
            lambda s: s.slug == "00_charter")
        self.assertEqual(s1_snap.section_version, 2)
