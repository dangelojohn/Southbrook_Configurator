# SPDX-License-Identifier: LGPL-3.0-only
"""View-render tests for the Order Builder — commit 9 NF13-class mitigation.

Per John's commit-9 ask: views can install without rendering what you
intended (xpath expressions matching the wrong element, missing position
attributes, broken arch overrides). XML lint catches well-formedness; it
doesn't catch Odoo-semantic correctness.

These tests assert that:
  1. The Order Builder view installs (env.ref resolves the xml_id)
  2. The view's compiled arch contains the southbrook-specific fields
     and buttons (xpath actually matched the expected elements)
  3. The Order Builder menu entry exists and resolves to the action
  4. The seed-mode banner appears in the rendered arch when expected

This is the "view installs and renders the right things" check.
End-to-end "rendering looks right visually" is John's live-instance review.
"""
from odoo.tests.common import tagged

from .common import SouthbrookTestCase


@tagged("post_install", "-at_install", "southbrook", "views")
class TestOrderBuilderViews(SouthbrookTestCase):

    # ------------------------------------------------------------------
    # View install + xml_id resolution
    # ------------------------------------------------------------------

    def test_01_sale_order_form_inherit_installs(self):
        v = self._ref("view_order_form_southbrook")
        self.assertEqual(v.model, "sale.order")
        self.assertEqual(v.inherit_id.xml_id, "sale.view_order_form")

    def test_02_res_users_form_inherit_installs(self):
        v = self._ref("view_users_form_southbrook")
        self.assertEqual(v.model, "res.users")

    def test_03_order_builder_action_installs(self):
        a = self._ref("action_order_builder")
        self.assertEqual(a.res_model, "sale.order")
        # Action must filter to draft/sent orders so the Order Builder
        # shows the rep's open work, not the full order history.
        self.assertIn("draft", str(a.domain))

    def test_04_menu_under_sales_exists(self):
        m = self._ref("menu_southbrook_order_builder")
        self.assertEqual(m.action.id, self._ref("action_order_builder").id)
        # Parent menu must be sale.sale_order_menu — the Sales menu in
        # standard Odoo. If a future contributor reparents this menu
        # (e.g. to a new top-level Southbrook menu), this assertion
        # forces an explicit decision.
        self.assertEqual(
            m.parent_id.xml_id,
            "sale.sale_order_menu",
            "menu_southbrook_order_builder must live under Sales menu",
        )

    # ------------------------------------------------------------------
    # Arch content — assertions on the compiled view xml
    # ------------------------------------------------------------------

    def test_05_sale_order_form_arch_contains_southbrook_buttons(self):
        """The Duplicate-as-Draft button must appear in the compiled arch.

        view.read() returns the resolved arch as a string (after
        inheritance is applied). We search for the button name; if the
        xpath silently failed to match, the button never makes it into
        the rendered arch.
        """
        form_view = self.env.ref("sale.view_order_form")
        # NF24 (caught at live test run 2026-05-30): Odoo 17+ renamed
        # fields_view_get → get_view; the model method now returns a
        # dict with 'arch' (string) and 'models' (mapping). Same data,
        # new signature.
        arch = self.env["sale.order"].get_view(form_view.id, "form")["arch"]
        self.assertIn("action_duplicate_as_draft", arch,
                      "NF6 button not in rendered arch — xpath likely missed")
        self.assertIn("ILLUSTRATIVE SEED", arch,
                      "seed-mode banner not in rendered arch")

    def test_06_sale_order_line_tree_contains_zone(self):
        """The zone field must appear in the order_line tree."""
        form_view = self.env.ref("sale.view_order_form")
        arch = self.env["sale.order"].get_view(form_view.id, "form")["arch"]
        # The zone field is added before product_id in the order_line tree.
        self.assertIn('name="zone"', arch,
                      "Q21 zone column not in rendered arch")
        self.assertIn('name="zone_label"', arch,
                      "Q21 zone_label not in rendered arch")

    def test_07_res_users_form_contains_prefs(self):
        """The Order Builder preferences group must appear in res.users form."""
        users_view = self.env.ref("base.view_users_form")
        arch = self.env["res.users"].get_view(users_view.id, "form")["arch"]
        self.assertIn("southbrook_default_series", arch,
                      "NF7 user pref field not in rendered arch")
        self.assertIn("southbrook_order_entry_mode", arch,
                      "NF8 user pref field not in rendered arch")

    # ------------------------------------------------------------------
    # Commit 9.5 — zone grouping + stat-button placement
    # ------------------------------------------------------------------

    def test_08_order_line_tree_is_grouped_by_zone(self):
        """Q21 visual grouping: the embedded order_line tree must carry
        default_group_by='zone' so the Richwood multi-zone pattern shows
        lines grouped under zone headers.
        """
        form_view = self.env.ref("sale.view_order_form")
        arch = self.env["sale.order"].get_view(form_view.id, "form")["arch"]
        # Search for the attribute in the order_line tree. If a future xpath
        # refactor accidentally drops the grouping, this assertion fails
        # before install reaches a live instance.
        self.assertIn('default_group_by="zone"', arch,
                      "Q21 zone grouping missing from compiled arch")

    def test_09_duplicate_button_is_in_button_box(self):
        """Discipline-A placement assertion (per John's commit-9 review):
        the Duplicate-as-Draft button must live inside the standard
        button_box (stat-button container), not in <header> or <footer>.

        Pins the placement so a future refactor doesn't silently move the
        button into a different region.
        """
        import re
        form_view = self.env.ref("sale.view_order_form")
        arch = self.env["sale.order"].get_view(form_view.id, "form")["arch"]

        # Find the button_box div span in the arch (greedy across newlines).
        # The button name must appear between the opening div tag with
        # name='button_box' and its closing </div>. If it lands in <header>
        # or <footer> instead, this regex misses.
        button_box_match = re.search(
            r'<div[^>]*\bname=["\']button_box["\'][^>]*>(.*?)</div>',
            arch, re.DOTALL,
        )
        self.assertTrue(
            button_box_match,
            "button_box div not present in compiled arch",
        )
        button_box_content = button_box_match.group(1)
        self.assertIn(
            "action_duplicate_as_draft",
            button_box_content,
            "NF6 button is NOT inside button_box — placement drifted "
            "(expected stat-button container, found elsewhere)",
        )
