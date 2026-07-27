# SPDX-License-Identifier: LGPL-3.0-only
"""Prodboard asset importer tests.

The importer caches licensed Prodboard-derived image binaries as private
Odoo attachments linked to `southbrook.cabinet.archetype`. The public
catalog UI must keep serving Southbrook-owned product.template images;
archetype attachments are an internal catalogue cache only.
"""
import base64
import os
import tempfile

from odoo.tests.common import TransactionCase, tagged


_PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\xfc\xcf"
    b"\xc0\x00\x00\x00\x03\x00\x01\xe3]\xc5\x06\x00\x00\x00\x00IEND\xaeB`\x82"
)


@tagged("post_install", "-at_install", "southbrook", "prodboard_assets")
class TestProdboardAssetImporter(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Archetype = cls.env["southbrook.cabinet.archetype"]
        cls.Importer = cls.env["southbrook.estimating.prodboard_asset_importer"]

    def _archetype(self, code="TEST-BHL1DR"):
        return self.Archetype.create({
            "external_id": 900000 + len(code),
            "code": code,
            "name": "Importer Test Cabinet",
            "collection": "classic",
            "body_class": "base",
            "image_uuid": "11111111-2222-3333-4444-555555555555",
            "image_filename": "Importer Test Cabinet.png",
            "image_url": (
                "https://blobs.prodboard.com/betterkitchens/icon/"
                "11111111-2222-3333-4444-555555555555/"
                "Importer%20Test%20Cabinet.png"
            ),
        })

    def test_mock_fetcher_imports_private_attachment(self):
        archetype = self._archetype()

        result = self.Importer._import_one(
            archetype,
            fetcher=lambda url: (_PNG_BYTES, "image/png"),
        )

        self.assertTrue(result)
        self.assertEqual(archetype.prodboard_asset_status, "imported")
        self.assertTrue(archetype.prodboard_asset_attachment_id)
        attachment = archetype.prodboard_asset_attachment_id
        self.assertEqual(attachment.res_model, "southbrook.cabinet.archetype")
        self.assertEqual(attachment.res_id, archetype.id)
        self.assertFalse(attachment.public)
        self.assertEqual(attachment.mimetype, "image/png")
        self.assertEqual(
            base64.b64decode(attachment.datas),
            _PNG_BYTES,
        )
        self.assertEqual(archetype.prodboard_asset_bytes, len(_PNG_BYTES))
        self.assertTrue(archetype.prodboard_asset_sha256)

    def test_import_is_idempotent_and_updates_existing_attachment(self):
        archetype = self._archetype("TEST-BHL2DR")

        self.Importer._import_one(
            archetype,
            fetcher=lambda url: (_PNG_BYTES, "image/png"),
        )
        first_attachment = archetype.prodboard_asset_attachment_id
        replacement = _PNG_BYTES + b"updated"

        self.Importer._import_one(
            archetype,
            fetcher=lambda url: (replacement, "image/png"),
        )

        self.assertEqual(
            archetype.prodboard_asset_attachment_id,
            first_attachment,
            "re-import must update the existing attachment, not duplicate it",
        )
        self.assertEqual(
            base64.b64decode(first_attachment.datas),
            replacement,
        )
        self.assertEqual(archetype.prodboard_asset_bytes, len(replacement))

    def test_offline_directory_import_uses_uuid_filename(self):
        archetype = self._archetype("TEST-BHL3DR")
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, archetype.image_uuid + ".png")
            with open(path, "wb") as fh:
                fh.write(_PNG_BYTES)

            self.Importer._import_one(archetype, offline_dir=tmpdir)

        self.assertEqual(archetype.prodboard_asset_status, "imported")
        self.assertTrue(archetype.prodboard_asset_attachment_id)
        self.assertEqual(
            base64.b64decode(archetype.prodboard_asset_attachment_id.datas),
            _PNG_BYTES,
        )

    def test_network_is_disabled_by_default(self):
        archetype = self._archetype("TEST-BHL4DR")

        result = self.Importer._import_one(archetype)

        self.assertFalse(result)
        self.assertEqual(archetype.prodboard_asset_status, "missing_source")
        self.assertFalse(archetype.prodboard_asset_attachment_id)
        self.assertIn("network disabled", archetype.prodboard_asset_error)

    def test_ssrf_guard_blocks_non_public_and_non_http_urls(self):
        """import_assets(allow_network=True) is an AbstractModel method that
        bypasses ir.model.access, so any authenticated user can drive
        _fetch_url with an arbitrary image_url. The guard must reject
        file://, loopback, RFC1918, link-local and cloud-metadata targets."""
        for bad in (
            "file:///etc/passwd",                        # local file read
            "ftp://example.com/x",                       # non-http scheme
            "http://127.0.0.1:8069/web",                 # loopback
            "http://169.254.169.254/latest/meta-data/",  # cloud metadata
            "http://10.1.2.3/x",                          # RFC1918
            "http://192.168.0.5/x",                       # RFC1918
            "http://172.16.4.4/x",                        # RFC1918
            "http:///no-host",                            # no host
            "",                                           # empty
        ):
            with self.assertRaises(ValueError, msg="must block %r" % bad):
                self.Importer._assert_safe_public_url(bad)

    def test_ssrf_guard_allows_public_ip(self):
        # A public IP literal (no DNS needed — works offline) must pass.
        self.Importer._assert_safe_public_url("https://8.8.8.8/icon.png")

