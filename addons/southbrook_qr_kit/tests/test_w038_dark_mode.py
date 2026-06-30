# SPDX-License-Identifier: LGPL-3.0-only
"""W038 (R8.5, 2026-06-27) — Night-shift dark mode tests.

JTBD: "When my shift is 10pm-6am and the bright white UI burns my
eyes, I want a dark mode that auto-engages or persists across
sessions."

Coverage (Python-side, asset + ICP shape):
  * ICP `southbrook.dark_mode.auto_engage` exists and defaults to "0"
    (day-shift users never get surprised on first install).
  * Dark-mode JS asset is registered in both web.assets_backend and
    web.assets_frontend bundles in the manifest (so kanban, scan
    modal, POD page, traveler-print preview all honour the same
    toggle).
  * Dark-mode SCSS asset is registered in both bundles too.
  * The JS file contains the load-bearing identifiers — body class
    `sb-dark-mode`, the localStorage key `sb.dark.mode`, the URL
    param `theme=dark`, and the global `sbDarkMode`.
  * The SCSS file is body-class-scoped to `sb-dark-mode` so non-
    dark users see zero rules apply.
  * The SCSS file preserves the print-stays-light @media print
    invariant (toner doesn't invert).
"""
import os

from odoo.modules import get_module_path
from odoo.tests.common import TransactionCase, tagged


_QR_KIT_ROOT = get_module_path("southbrook_qr_kit")


@tagged("post_install", "-at_install", "southbrook", "sbk_qr_kit", "w038")
class TestW038DarkMode(TransactionCase):

    def test_10_icp_auto_engage_seeded_default_off(self):
        """Default = OFF so day-shift users never get surprised."""
        ICP = self.env["ir.config_parameter"].sudo()
        val = ICP.get_param("southbrook.dark_mode.auto_engage")
        self.assertEqual(
            val, "0",
            "W038: auto-engage MUST default to '0' so day-shift "
            "users never see an automatic theme swap on first load.")

    def test_20_manifest_registers_js_in_both_bundles(self):
        """JS asset must be present in BOTH backend and frontend
        bundles so every operator surface honours the toggle."""
        mod = self.env["ir.module.module"].search([
            ("name", "=", "southbrook_qr_kit")], limit=1)
        # The assets dict lives in __manifest__.py; pull it through
        # the manifest read API for forwards-compat.
        manifest_path = os.path.join(_QR_KIT_ROOT, "__manifest__.py")
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest_src = f.read()
        self.assertIn(
            "southbrook_qr_kit/static/src/js/dark_mode_toggle.js",
            manifest_src,
            "W038 JS toggle must be registered in __manifest__.py "
            "assets dict.")
        # Verify presence in BOTH bundles — count of substring should
        # be >= 2 (once for backend, once for frontend).
        count = manifest_src.count(
            "southbrook_qr_kit/static/src/js/dark_mode_toggle.js")
        self.assertGreaterEqual(
            count, 2,
            "W038 JS must appear in BOTH web.assets_backend AND "
            "web.assets_frontend; got %d occurrences." % count)

    def test_30_manifest_registers_scss_in_both_bundles(self):
        manifest_path = os.path.join(_QR_KIT_ROOT, "__manifest__.py")
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest_src = f.read()
        count = manifest_src.count(
            "southbrook_qr_kit/static/src/scss/dark_mode.scss")
        self.assertGreaterEqual(
            count, 2,
            "W038 SCSS must appear in BOTH backend and frontend "
            "bundles; got %d occurrences." % count)

    def test_40_js_carries_load_bearing_identifiers(self):
        """Smoke-check the JS file — the load-bearing identifiers
        must be present. If a future refactor renames any of these
        the test catches it before deploy."""
        js_path = os.path.join(
            _QR_KIT_ROOT, "static", "src", "js", "dark_mode_toggle.js")
        self.assertTrue(os.path.exists(js_path), "JS file must exist.")
        with open(js_path, "r", encoding="utf-8") as f:
            js = f.read()
        # Body class.
        self.assertIn(
            "sb-dark-mode", js,
            "JS must apply / remove the 'sb-dark-mode' body class.")
        # localStorage key.
        self.assertIn(
            "sb.dark.mode", js,
            "JS must read / write localStorage key 'sb.dark.mode'.")
        # URL param.
        self.assertIn(
            'params.get("theme")', js,
            "JS must accept URL query param ?theme=dark / ?theme=light.")
        # Global handle for console.
        self.assertIn(
            "window.sbDarkMode", js,
            "JS must expose window.sbDarkMode global for console "
            "and dev access.")
        # Default OFF guarantee — applyTheme(false) must be a path.
        self.assertIn(
            "applyTheme(false)", js,
            "JS must default to applyTheme(false) so day-shift users "
            "see zero change on first load.")

    def test_50_scss_is_body_class_scoped(self):
        """The SCSS file must scope EVERY rule under
        `body.sb-dark-mode` so absent the class no rules apply."""
        scss_path = os.path.join(
            _QR_KIT_ROOT, "static", "src", "scss", "dark_mode.scss")
        self.assertTrue(os.path.exists(scss_path))
        with open(scss_path, "r", encoding="utf-8") as f:
            scss = f.read()
        self.assertIn(
            "body.sb-dark-mode {", scss,
            "SCSS must open a body.sb-dark-mode {} root block so "
            "absent the body class no rules apply.")
        # Print-stays-light invariant: there must be a @media print
        # block that re-lights body.sb-dark-mode so paper output
        # doesn't burn toner.
        self.assertIn("@media print", scss,
                      "SCSS must include a @media print block.")
        self.assertIn(
            "background-color: #ffffff !important", scss,
            "Print block must re-light to white background — toner "
            "doesn't invert.")
