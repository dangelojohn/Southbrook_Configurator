# addons/southbrook_os/tests/test_os_publication.py
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "southbrook_os")
class TestOsPublication(TransactionCase):
    def setUp(self):
        super().setUp()
        Section = self.env["southbrook.os.section"]
        # NOTE: post_init_hook `_post_init_load_canonical` pre-seeds slugs
        # `00_charter`, `02_catalog`, etc. Tests use a `99_test_*` prefix
        # to avoid colliding with the unique-slug constraint on canonical seeds.
        self.s1 = Section.create({
            "slug": "99_test_charter", "name": "Charter",
            "source": "canonical", "body": "v1 body",
        })
        self.s2 = Section.create({
            "slug": "99_test_catalog", "name": "Catalog",
            "source": "canonical", "body": "v1 body",
        })

    def test_publish_creates_snapshot_of_every_section(self):
        pub = self.env["southbrook.os.publication"].publish("2026-06")
        self.assertEqual(pub.calendar_key, "2026-06")
        self.assertTrue(pub.build_hash)
        # publish() snapshots EVERY section in the DB — including the
        # canonical post_init_hook seeds (~14 records). Filter to the
        # slugs this test created so the assertion is robust to seed
        # growth. Sanity-check the total still matches the live section
        # count at publish time.
        own_slugs = {self.s1.slug, self.s2.slug}
        own_snaps = pub.section_snapshot_ids.filtered(
            lambda s: s.slug in own_slugs)
        self.assertEqual(len(own_snaps), 2)
        for snap in own_snaps:
            self.assertEqual(snap.section_version, 1)
        self.assertEqual(
            len(pub.section_snapshot_ids),
            self.env["southbrook.os.section"].search_count([]),
        )

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
            lambda s: s.slug == "99_test_charter")
        self.assertEqual(s1_snap.section_version, 2)
