# SPDX-License-Identifier: LGPL-3.0-only
"""Audit Phase 2A-2L regression coverage.

Locks in the audit's contributions so a future upgrade that destroys
gating rules (Phase 2I taught us that catalog_expansion + rule_completion
can silently delete them) fails CI instead of shipping a broken
configurator.

Covers:

  * A1-A8 rule cardinality (85 audit rules bound)
  * Soft-close default ON for every Q8 cabinet's accessories line
  * Four wizard step buckets exist + every Q8 cabinet has step_lines
    covering all its attribute_lines exactly once
  * A8 finish-by-species spot checks (MDF, Maple, Cherry, Walnut)
  * A5 mullion-glass restriction spot check (non-wall cabinets)
"""
from odoo.tests.common import tagged

from .common import SouthbrookTestCase


_Q8_CABINETS = (
    "wall_1dr", "wall_2dr", "base_1dr", "base_2dr", "drawer_bank",
    "sink_base", "tall_pantry", "tall_oven", "corner", "vanity",
)

# Expected audit rule cardinality per sub-rule. Bump this map when
# new audit rules land — that's the signal CI should green on.
_EXPECTED_RULE_COUNTS = {
    "ruleA1": 10,  # frameless overlay = full | partial
    "ruleA2": 10,  # non-premium overlay drops beaded inset
    "ruleA3": 10,  # contractor → framed only
    "ruleA4": 6,   # contractor → no dovetail
    "ruleA5": 8,   # non-wall → no mullion glass / reeded
    "ruleA6": 6,   # non-corner → no lazy susan
    "ruleA7": 5,   # non-base → no pull-out trash
    "ruleA8": 30,  # finish scoped by wood species
}
_EXPECTED_TOTAL = sum(_EXPECTED_RULE_COUNTS.values())  # 85

_AUDIT_STEPS = (
    ("step_construction",  "Construction & Sizing"),
    ("step_door_finish",   "Door & Finish"),
    ("step_hardware",      "Hardware & Sides"),
    ("step_interior",      "Interior & Accessories"),
)


@tagged("post_install", "-at_install", "southbrook")
class TestAuditPhase2Rules(SouthbrookTestCase):
    """A1-A8 cardinality + structural sanity."""

    def test_01_audit_rule_total(self):
        """All 85 audit gating rules bound to product.config.line."""
        IMD = self.env["ir.model.data"]
        n = IMD.search_count([
            ("module", "=", "southbrook_estimating"),
            ("model", "=", "product.config.line"),
            ("name", "=like", "ruleA%"),
        ])
        self.assertEqual(
            n, _EXPECTED_TOTAL,
            f"Audit rule count drift: expected {_EXPECTED_TOTAL}, got {n}. "
            "If this dropped, suspect rule_completion or catalog_expansion "
            "deleting config.line records mid-upgrade.",
        )

    def test_02_audit_rule_subgroup_counts(self):
        """A1-A8 each match expected per-group cardinality."""
        IMD = self.env["ir.model.data"]
        for prefix, expected in _EXPECTED_RULE_COUNTS.items():
            n = IMD.search_count([
                ("module", "=", "southbrook_estimating"),
                ("model", "=", "product.config.line"),
                ("name", "=like", f"{prefix}_%"),
            ])
            self.assertEqual(
                n, expected,
                f"Sub-group {prefix}: expected {expected}, got {n}",
            )

    def test_03_a8_finish_rules_target_finish_attribute(self):
        """Every A8 rule binds attribute_line_id pointing at attr_finish."""
        finish_attr = self._ref("attr_finish")
        IMD = self.env["ir.model.data"]
        a8_imds = IMD.search([
            ("module", "=", "southbrook_estimating"),
            ("model", "=", "product.config.line"),
            ("name", "=like", "ruleA8_%"),
        ])
        ConfigLine = self.env["product.config.line"]
        for imd in a8_imds:
            cfg = ConfigLine.browse(imd.res_id)
            self.assertEqual(
                cfg.attribute_line_id.attribute_id.id,
                finish_attr.id,
                f"A8 rule {imd.name} does not target attr_finish",
            )


@tagged("post_install", "-at_install", "southbrook")
class TestAuditPhase2SoftClose(SouthbrookTestCase):
    """Phase 2I — soft-close default ON for the 10 Q8 cabinets."""

    def test_01_all_q8_cabinets_default_soft_close(self):
        soft_close = self._ref("value_accessory_soft_close")
        for cab in _Q8_CABINETS:
            line = self._ref(f"attr_line_{cab}_accessories")
            self.assertEqual(
                line.default_val.id, soft_close.id,
                f"{cab} accessories line missing soft-close default",
            )


@tagged("post_install", "-at_install", "southbrook")
class TestAuditPhase2WizardSteps(SouthbrookTestCase):
    """Phase 2K — four wizard step buckets + Q8 cabinet step_lines."""

    def test_01_four_step_records_present(self):
        names = []
        for xml_id, label in _AUDIT_STEPS:
            step = self._ref(xml_id)
            names.append(step.name)
        self.assertEqual(len(names), 4)

    def test_02_every_q8_cabinet_has_four_step_lines(self):
        for cab in _Q8_CABINETS:
            tmpl = self._ref(cab)
            sl_steps = set(tmpl.config_step_line_ids.mapped(
                "config_step_id.id"))
            self.assertEqual(
                len(sl_steps), 4,
                f"{cab}: expected 4 step_lines, got {len(sl_steps)}",
            )

    def test_03_step_lines_partition_all_attribute_lines(self):
        """Every attribute_line on a Q8 cabinet belongs to exactly one
        step — no orphans (would render as a flat-list scroll), no
        duplicates (would render under multiple tabs)."""
        for cab in _Q8_CABINETS:
            tmpl = self._ref(cab)
            grouped_attr_lines = []
            for sl in tmpl.config_step_line_ids:
                grouped_attr_lines.extend(sl.attribute_line_ids.ids)
            tmpl_attr_line_ids = set(tmpl.attribute_line_ids.ids)
            grouped_set = set(grouped_attr_lines)
            # Every attribute_line shows up in the grouping.
            missing = tmpl_attr_line_ids - grouped_set
            self.assertFalse(
                missing,
                f"{cab}: attribute_lines not in any step: {missing}",
            )
            # No double-membership.
            self.assertEqual(
                len(grouped_attr_lines), len(grouped_set),
                f"{cab}: some attribute_lines appear in multiple steps",
            )


@tagged("post_install", "-at_install", "southbrook")
class TestAuditPhase2A8FinishSpecies(SouthbrookTestCase):
    """A8 spot checks — finish availability under each species."""

    def setUp(self):
        super().setUp()
        # Use SB-BASE-1DR as the representative non-wall cabinet.
        self.tmpl = self._ref("base_1dr")
        self.species_line = self.tmpl.attribute_line_ids.filtered(
            lambda l: l.attribute_id.name == "Wood Species"
        )
        self.finish_line = self.tmpl.attribute_line_ids.filtered(
            lambda l: l.attribute_id.name == "Finish"
        )
        self.assertTrue(self.species_line)
        self.assertTrue(self.finish_line)

    def _available_finishes(self, species_xml_id):
        """Return finish value names allowed when species is set."""
        Session = self.env["product.config.session"]
        session = Session.create({"product_tmpl_id": self.tmpl.id})
        species_val = self._ref(species_xml_id)
        # All-but-species values get cleared; just set the species.
        session.value_ids = [(6, 0, [species_val.id])]
        available = self.finish_line._configurator_value_ids()
        return set(available.mapped("name"))

    def test_01_mdf_painted_offers_only_white_and_custom(self):
        names = self._available_finishes("value_species_mdf_painted")
        self.assertIn("White", names)
        self.assertIn("Custom", names)
        self.assertNotIn("Maple Stain", names)
        self.assertNotIn("Cherry Stain", names)
        self.assertNotIn("Walnut Stain", names)

    def test_02_maple_offers_maple_stain_only(self):
        names = self._available_finishes("value_species_maple")
        self.assertIn("Maple Stain", names)
        self.assertNotIn("Cherry Stain", names)
        self.assertNotIn("Walnut Stain", names)

    def test_03_cherry_offers_cherry_stain_only(self):
        names = self._available_finishes("value_species_cherry")
        self.assertIn("Cherry Stain", names)
        self.assertNotIn("Maple Stain", names)
        self.assertNotIn("Walnut Stain", names)

    def test_04_alder_offers_cherry_stain_historic_substitute(self):
        names = self._available_finishes("value_species_alder")
        self.assertIn("Cherry Stain", names)
        self.assertNotIn("Maple Stain", names)
        self.assertNotIn("Walnut Stain", names)

    def test_05_walnut_offers_walnut_stain(self):
        names = self._available_finishes("value_species_walnut")
        self.assertIn("Walnut Stain", names)
        self.assertNotIn("Maple Stain", names)
        self.assertNotIn("Cherry Stain", names)


@tagged("post_install", "-at_install", "southbrook")
class TestAuditPhase2A5MullionGlass(SouthbrookTestCase):
    """A5 spot check — non-wall cabinets can't pick mullion glass / reeded."""

    def test_01_wall_cabinet_includes_mullion_glass(self):
        """Sanity: wall cabinets still expose the mullion glass option."""
        tmpl = self._ref("wall_1dr")
        door_line = tmpl.attribute_line_ids.filtered(
            lambda l: l.attribute_id.name == "Door Style"
        )
        names = set(door_line.value_ids.mapped("name"))
        self.assertIn("Mullion Glass", names)
        self.assertIn("Reeded", names)

    def test_02_non_wall_cabinet_excludes_mullion_glass(self):
        """A5 hides mullion_glass + reeded on every non-wall family."""
        Session = self.env["product.config.session"]
        for cab in ("base_1dr", "drawer_bank", "corner", "vanity"):
            tmpl = self._ref(cab)
            door_line = tmpl.attribute_line_ids.filtered(
                lambda l: l.attribute_id.name == "Door Style"
            )
            session = Session.create({"product_tmpl_id": tmpl.id})
            available = door_line._configurator_value_ids()
            names = set(available.mapped("name"))
            self.assertNotIn(
                "Mullion Glass", names,
                f"{cab}: A5 should hide Mullion Glass on non-wall cabinets",
            )
            self.assertNotIn(
                "Reeded", names,
                f"{cab}: A5 should hide Reeded on non-wall cabinets",
            )
