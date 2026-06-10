# SPDX-License-Identifier: LGPL-3.0-only
"""Phase 3 Sprint A1 — vendored web fonts test.

The configurator's SCSS references "Roboto Flex" + "JetBrains Mono"
in font-family rules; until the fonts.scss vendoring landed, nothing
actually loaded the woff2 files. This test guards against regression:
the asset files must remain present, the @font-face declaration must
remain in the asset bundle, and both must be reachable via HTTP.
"""
import os

from odoo.tests.common import HttpCase, tagged


# Path resolution: the test loads from inside the addon, so resolve
# relative to this file's directory rather than the Odoo data dir.
ADDON_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@tagged("post_install", "-at_install", "southbrook", "phase-3", "fonts")
class TestVendoredFonts(HttpCase):

    def test_roboto_flex_woff2_exists_on_disk(self):
        """The vendored Roboto Flex woff2 must be present.

        Without it, the @font-face URL in fonts.scss 404s and every
        visitor falls back to the OS sans-serif font. Catches an
        accidental `git rm` or an out-of-sync rsync deploy.
        """
        path = os.path.join(
            ADDON_ROOT, "static", "src", "fonts", "RobotoFlex.woff2",
        )
        self.assertTrue(
            os.path.exists(path),
            f"RobotoFlex.woff2 missing from {path}",
        )
        # Sanity: woff2 magic bytes are wOF2.
        with open(path, "rb") as f:
            magic = f.read(4)
        self.assertEqual(magic, b"wOF2",
                          "RobotoFlex.woff2 is not a valid woff2 file")

    def test_jetbrains_mono_woff2_exists_on_disk(self):
        path = os.path.join(
            ADDON_ROOT, "static", "src", "fonts",
            "JetBrainsMono.woff2",
        )
        self.assertTrue(
            os.path.exists(path),
            f"JetBrainsMono.woff2 missing from {path}",
        )
        with open(path, "rb") as f:
            self.assertEqual(f.read(4), b"wOF2")

    def test_fonts_scss_declares_font_face(self):
        """The bundle SCSS source must declare both @font-face rules.

        Guards against someone deleting fonts.scss while leaving the
        woff2 files in place (silent regression — no 404, just no
        font loaded because nothing references it).
        """
        path = os.path.join(
            ADDON_ROOT, "static", "src", "scss", "fonts.scss",
        )
        self.assertTrue(os.path.exists(path),
                         "fonts.scss missing — bundle would have no "
                         "@font-face declarations")
        with open(path, "r") as f:
            css = f.read()
        self.assertIn('font-family: "Roboto Flex"', css)
        self.assertIn('font-family: "JetBrains Mono"', css)
        self.assertIn("font-display: swap", css)
        # The src URL must point at the vendored path, NOT at any
        # external CDN (Google Fonts, jsDelivr, etc.).
        self.assertNotIn("fonts.gstatic.com", css)
        self.assertNotIn("googleapis.com", css)

    def test_roboto_flex_served_at_static_url(self):
        """End-to-end: the woff2 must be reachable via HTTP.

        The asset URL Odoo serves for module-static files follows the
        pattern /<module>/static/<path>. If the manifest's asset
        bundle entry is wrong, fonts.scss compiles but the woff2
        404s and the @font-face rule silently no-ops.
        """
        url = ("/southbrook_estimating_website/static/src/fonts/"
               "RobotoFlex.woff2")
        resp = self.url_open(url)
        self.assertEqual(resp.status_code, 200,
                          f"GET {url} returned {resp.status_code}")
        self.assertEqual(resp.content[:4], b"wOF2")
        # Sanity: served bytes match disk bytes.
        path = os.path.join(
            ADDON_ROOT, "static", "src", "fonts", "RobotoFlex.woff2",
        )
        with open(path, "rb") as f:
            self.assertEqual(resp.content, f.read())
