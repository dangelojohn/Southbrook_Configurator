# SPDX-License-Identifier: LGPL-3.0-only
"""Regression test for the SSRF guard on Hermes-supplied source URLs
(_attach_documents fetches AI-agent-supplied URLs — must reject private/
loopback/metadata hosts)."""
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook_hermes_bom")
class TestHermesSsrfGuard(TransactionCase):

    def _guard(self, url):
        return self.env["hermes.wizard"]._is_safe_public_url(url)

    def test_blocks_cloud_metadata_and_private_and_loopback(self):
        for bad in (
            "http://169.254.169.254/latest/meta-data/",   # cloud metadata
            "http://127.0.0.1:8069/web",                  # loopback
            "http://localhost/internal",                  # loopback name
            "http://10.1.2.3/x", "http://192.168.0.5/x",  # RFC1918
            "http://172.16.4.4/x",
            "not-a-url", "ftp://example.com/x", "",        # malformed/scheme
        ):
            self.assertFalse(self._guard(bad), "must block %r" % bad)

    def test_allows_public_ip(self):
        # A public IP literal (no DNS needed — works offline) must pass.
        self.assertTrue(self._guard("https://8.8.8.8/doc.pdf"))
