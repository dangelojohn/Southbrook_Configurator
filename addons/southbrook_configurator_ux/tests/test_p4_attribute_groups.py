# SPDX-License-Identifier: LGPL-3.0-only
"""P4 — Re-shard the "Other" section by manufacturing meaning.

Pure-Python test against ATTRIBUTE_GROUPS — no DB fixtures needed. The
audit's acceptance criteria boil down to four assertions:

  1. No attribute name from the pre-audit grouping is missing in the
     new grouping (no deletion).
  2. Drawer Construction appears in a top-level "Construction" group
     (i.e. its group comes BEFORE the novelty Add-ons group).
  3. The three named groups land where the audit said they should
     (Construction / Materials & Finish / Add-ons).
  4. Family is in "Size & Layout".

The audit's full "sample build -> $680 / 6.5 kg / SB-... at 18/18"
regression depends on live attribute_value seed data and is exercised
by the golden-path TransactionCase in test_state_endpoint.py; here we
guard the structural invariant the audit specifically called out.
"""
from odoo.tests.common import TransactionCase, tagged

from odoo.addons.southbrook_configurator_ux.controllers.main import (
    ATTRIBUTE_GROUPS,
)


@tagged("post_install", "-at_install", "southbrook", "configurator_ux", "p4",
        "attribute_groups")
class TestP4AttributeGroups(TransactionCase):

    # The pre-audit grouping — the source of truth for "no attribute
    # was deleted". Mirrors what was in main.py before this commit.
    _PRE_AUDIT_GROUPS = [
        ("Size & Layout",         ["Width", "Door Count"]),
        ("Series & Materials",    ["Series", "Box Material", "Door Style"]),
        ("Finish & Construction", ["Finish", "Hinge Side", "Finished Sides", "Gables"]),
        ("Hardware & Add-ons",    ["Handle", "Accessories"]),
    ]

    def _flat_names(self, groups):
        out = []
        for _title, names in groups:
            out.extend(names)
        return out

    # ------------------------------------------------------------------
    # Acceptance — no attribute deleted
    # ------------------------------------------------------------------
    def test_no_pre_audit_attribute_removed(self):
        pre = set(self._flat_names(self._PRE_AUDIT_GROUPS))
        post = set(self._flat_names(ATTRIBUTE_GROUPS))
        missing = pre - post
        self.assertFalse(
            missing,
            f"audit P4 forbids deletion of any attribute; missing: {missing}")

    # ------------------------------------------------------------------
    # Acceptance — Drawer Construction sits in "Construction", above
    # the novelty Add-ons group.
    # ------------------------------------------------------------------
    def test_drawer_construction_in_top_level_construction_group(self):
        titles = [t for t, _names in ATTRIBUTE_GROUPS]
        self.assertIn("Construction", titles)
        construction_idx = titles.index("Construction")
        addons_idx = titles.index("Add-ons") if "Add-ons" in titles else 999
        self.assertLess(
            construction_idx, addons_idx,
            "Drawer Construction's group must sit ABOVE the novelty "
            "Add-ons group — that's the structural intent of P4")

        construction_attrs = next(
            names for t, names in ATTRIBUTE_GROUPS if t == "Construction")
        self.assertIn("Drawer Construction", construction_attrs)

    # ------------------------------------------------------------------
    # Acceptance — three newly-named groups with the right members
    # ------------------------------------------------------------------
    def test_construction_group_membership(self):
        construction = next(
            names for t, names in ATTRIBUTE_GROUPS if t == "Construction")
        for required in ("Frame Style", "Door Overlay", "Drawer Construction"):
            self.assertIn(required, construction)

    def test_materials_and_finish_group_membership(self):
        mat = next(
            names for t, names in ATTRIBUTE_GROUPS if t == "Materials & Finish")
        for required in ("Wood Species", "Pull Finish", "Door Edge Profile"):
            self.assertIn(required, mat)

    def test_addons_group_membership(self):
        addons = next(
            names for t, names in ATTRIBUTE_GROUPS if t == "Add-ons")
        for required in ("Lighting", "Interior Storage"):
            self.assertIn(required, addons)

    # ------------------------------------------------------------------
    # Acceptance — Family is in Size & Layout (it is structural)
    # ------------------------------------------------------------------
    def test_family_in_size_and_layout(self):
        sl = next(
            names for t, names in ATTRIBUTE_GROUPS if t == "Size & Layout")
        self.assertIn("Family", sl)

    # ------------------------------------------------------------------
    # Sanity — no group is empty in the *spec* (templates may still
    # have empty groups at runtime if they don't expose the attribute;
    # the state-endpoint code filters those out).
    # ------------------------------------------------------------------
    def test_no_spec_group_is_empty(self):
        for title, names in ATTRIBUTE_GROUPS:
            self.assertTrue(
                names, f"group '{title}' has no attribute names — empty group "
                "would render an empty section header")
