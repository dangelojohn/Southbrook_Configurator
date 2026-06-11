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
    """A8 schema checks — each finish-by-species rule pins one finish to
    the right species domain. Runtime availability is delegated to OCA's
    own values_available logic; here we verify what we COMMITTED."""

    def test_01_maple_stain_rule_pins_to_maple_domain(self):
        rule = self._ref("ruleA8_base_1dr_maple_stain_by_species")
        maple_stain = self._ref("value_finish_maple_stain")
        self.assertEqual(rule.value_ids.ids, [maple_stain.id])
        self.assertEqual(
            rule.domain_id, self._ref("domain_species_is_maple"))

    def test_02_cherry_stain_rule_covers_cherry_and_alder(self):
        rule = self._ref("ruleA8_base_1dr_cherry_stain_by_species")
        cherry_stain = self._ref("value_finish_cherry_stain")
        self.assertEqual(rule.value_ids.ids, [cherry_stain.id])
        dom = rule.domain_id
        self.assertEqual(dom, self._ref("domain_species_allows_cherry_stain"))
        species_ids = set(dom.domain_line_ids.mapped("value_ids").ids)
        self.assertEqual(species_ids, {
            self._ref("value_species_cherry").id,
            self._ref("value_species_alder").id,
        })

    def test_03_walnut_stain_rule_covers_four_species(self):
        rule = self._ref("ruleA8_base_1dr_walnut_stain_by_species")
        walnut_stain = self._ref("value_finish_walnut_stain")
        self.assertEqual(rule.value_ids.ids, [walnut_stain.id])
        dom = rule.domain_id
        self.assertEqual(dom, self._ref("domain_species_allows_walnut_stain"))
        species_ids = set(dom.domain_line_ids.mapped("value_ids").ids)
        self.assertEqual(species_ids, {
            self._ref("value_species_walnut").id,
            self._ref("value_species_red_oak").id,
            self._ref("value_species_white_oak_rift").id,
            self._ref("value_species_hickory").id,
        })

    def test_04_white_and_custom_have_no_a8_rule(self):
        """White paint + Custom finish should NOT be in any A8 rule —
        they apply universally (including on MDF)."""
        IMD = self.env["ir.model.data"]
        a8_imds = IMD.search([
            ("module", "=", "southbrook_estimating"),
            ("model", "=", "product.config.line"),
            ("name", "=like", "ruleA8_%"),
        ])
        white = self._ref("value_finish_white")
        custom = self._ref("value_finish_custom")
        for imd in a8_imds:
            rule = self.env["product.config.line"].browse(imd.res_id)
            self.assertNotIn(
                white.id, rule.value_ids.ids,
                f"{imd.name} unexpectedly restricts White paint",
            )
            self.assertNotIn(
                custom.id, rule.value_ids.ids,
                f"{imd.name} unexpectedly restricts Custom finish",
            )

    def test_05_a8_rules_exist_for_all_q8_cabinets(self):
        """Every Q8 cabinet has all 3 A8 rules — no gaps."""
        for cab in _Q8_CABINETS:
            for stain in ("maple_stain", "cherry_stain", "walnut_stain"):
                xml_id = f"ruleA8_{cab}_{stain}_by_species"
                self._ref(xml_id)  # raises if missing


@tagged("post_install", "-at_install", "southbrook")
class TestAuditPhase2A5MullionGlass(SouthbrookTestCase):
    """A5 schema check — mullion_glass + reeded restricted to wall family."""

    def test_01_wall_cabinets_have_all_9_door_styles(self):
        """Sanity: wall cabinets carry all 9 door styles in their
        attribute_line so the audit's other rules (rule1 series → door)
        have room to restrict among them."""
        for cab in ("wall_1dr", "wall_2dr"):
            line = self._ref(f"attr_line_{cab}_door_style")
            names = set(line.value_ids.mapped("name"))
            self.assertIn("Mullion Glass", names)
            self.assertIn("Reeded", names)

    def test_02_a5_rule_excludes_mullion_and_reeded(self):
        """The 8 A5 rules pin door_style to the 7 'non-wall' values —
        explicitly leaving out Mullion Glass + Reeded."""
        mullion = self._ref("value_door_mullion_glass")
        reeded = self._ref("value_door_reeded")
        for cab in (
            "base_1dr", "base_2dr", "drawer_bank", "sink_base",
            "tall_pantry", "tall_oven", "corner", "vanity",
        ):
            rule = self._ref(f"ruleA5_{cab}_door_style_not_wall_only")
            value_ids = set(rule.value_ids.ids)
            self.assertNotIn(
                mullion.id, value_ids,
                f"{cab} A5 rule includes Mullion Glass — should exclude",
            )
            self.assertNotIn(
                reeded.id, value_ids,
                f"{cab} A5 rule includes Reeded — should exclude",
            )
            self.assertEqual(
                len(value_ids), 7,
                f"{cab} A5 rule should restrict to 7 values, got "
                f"{len(value_ids)}",
            )

    def test_03_a5_rule_domain_is_not_wall(self):
        for cab in (
            "base_1dr", "base_2dr", "drawer_bank", "sink_base",
            "tall_pantry", "tall_oven", "corner", "vanity",
        ):
            rule = self._ref(f"ruleA5_{cab}_door_style_not_wall_only")
            self.assertEqual(
                rule.domain_id,
                self._ref("domain_family_is_not_wall"),
                f"{cab} A5 rule has wrong domain",
            )


@tagged("post_install", "-at_install", "southbrook")
class TestAuditPhase2PriceExtras(SouthbrookTestCase):
    """Pricing pass — every audit attribute value should resolve to a
    non-zero or-zero price_extra row (not silently skip due to a
    name mismatch like Phase 2L's Door Edge Profile bug)."""

    _AUDIT_VALUE_XMLIDS = (
        # Frame Style
        "value_frame_framed", "value_frame_frameless",
        # Door Overlay
        "value_overlay_full", "value_overlay_partial",
        "value_overlay_inset", "value_overlay_beaded_inset",
        # Wood Species
        "value_species_maple", "value_species_cherry",
        "value_species_red_oak", "value_species_white_oak_rift",
        "value_species_walnut", "value_species_alder",
        "value_species_hickory", "value_species_mdf_painted",
        # Drawer Construction
        "value_drawer_dovetail_hardwood", "value_drawer_plywood_5_8",
        "value_drawer_particleboard", "value_drawer_metal_blum",
        # Pull Finish
        "value_pull_polished_nickel", "value_pull_brushed_nickel",
        "value_pull_matte_black", "value_pull_antique_bronze",
        "value_pull_brushed_brass", "value_pull_polished_chrome",
        "value_pull_oil_rubbed_bronze", "value_pull_champagne_bronze",
        # Interior Storage
        "value_int_pullout_trash", "value_int_spice_pullout",
        "value_int_knife_block", "value_int_cutlery_tray_wood",
        "value_int_lazy_susan", "value_int_rollout_tray",
        "value_int_mixer_lift", "value_int_wine_rack",
        "value_int_charging_drawer", "value_int_tipout_sink",
        # Lighting
        "value_lighting_none", "value_lighting_under_cabinet_led",
        "value_lighting_toekick_led", "value_lighting_puck",
        # Glass Insert
        "value_glass_none", "value_glass_clear", "value_glass_frosted",
        "value_glass_seeded", "value_glass_reeded", "value_glass_leaded",
        # Door Edge Profile
        "value_edge_square", "value_edge_eased", "value_edge_bevel",
        "value_edge_ogee", "value_edge_bullnose",
        # Crown Molding
        "value_crown_none", "value_crown_simple", "value_crown_ogee",
        "value_crown_stacked", "value_crown_dental",
        # New door styles (Phase 1)
        "value_door_shaker", "value_door_raised_panel",
        "value_door_beadboard", "value_door_mullion_glass",
        "value_door_v_groove", "value_door_reeded",
    )

    def test_01_every_audit_value_has_at_least_one_ptav(self):
        """Every audit value must be attached to at least one cabinet
        template (otherwise the price_extra has nowhere to land)."""
        PTAV = self.env["product.template.attribute.value"]
        for xml_id in self._AUDIT_VALUE_XMLIDS:
            val = self._ref(xml_id)
            n = PTAV.search_count([
                ("product_attribute_value_id", "=", val.id),
            ])
            self.assertGreater(
                n, 0,
                f"{xml_id} has no PTAVs — no cabinet exposes this value, "
                "so its price_extra row can't bind",
            )

    def test_02_premium_audit_values_carry_non_zero_price_extra(self):
        """Premium audit values should have non-zero price_extra so
        users see meaningful price movement. (Baseline values like
        'None' / 'Square' / 'Particleboard' stay at $0 by design.)

        The price_extra writes live in southbrook_configurator_ux's
        tactical_price_seed.backfill_demo_price_extras, triggered by
        that module's data XML load. When THIS test runs via
        `-u southbrook_estimating`, the configurator_ux load isn't
        triggered — so we invoke the backfill ourselves to guarantee
        the deltas are written before asserting.
        """
        # Trigger the backfill if southbrook_configurator_ux is
        # installed. When it isn't, every premium price_extra stays
        # at 0 by design — those deltas LIVE in configurator_ux, not
        # in this base addon — so the test would be assertively
        # checking absent infrastructure. Skip instead.
        seed_model = self.env.get("southbrook.configurator_ux.tactical_seed")
        if seed_model is None:
            self.skipTest(
                "southbrook_configurator_ux not installed; premium "
                "price_extras live in that module's tactical_price_seed"
            )
        seed_model.sudo().backfill_demo_price_extras()
        PTAV = self.env["product.template.attribute.value"]
        premium_xmlids = (
            "value_overlay_inset",         # +$35
            "value_overlay_beaded_inset",  # +$55
            "value_species_walnut",        # +$85
            "value_species_white_oak_rift",  # +$65
            "value_drawer_dovetail_hardwood",  # +$45
            "value_drawer_metal_blum",     # +$65
            "value_int_pullout_trash",     # +$185
            "value_int_mixer_lift",        # +$245
            "value_lighting_under_cabinet_led",  # +$125
            "value_glass_leaded",          # +$145
            "value_crown_dental",          # +$95
            "value_door_mullion_glass",    # +$135
        )
        for xml_id in premium_xmlids:
            val = self._ref(xml_id)
            ptavs = PTAV.search([
                ("product_attribute_value_id", "=", val.id),
            ])
            extras = ptavs.mapped("price_extra")
            self.assertTrue(
                any(e > 0 for e in extras),
                f"{xml_id} has zero price_extra everywhere — "
                "tactical_price_seed must have skipped it. Check the "
                "name match between attributes.xml and "
                "tactical_price_seed.py's _DEMO_DELTAS dict.",
            )


@tagged("post_install", "-at_install", "southbrook")
class TestAuditPhase2CatalogExpansion(SouthbrookTestCase):
    """Phase 2L parity — every cabinet seeded by catalog_expansion.py
    must wear the same audit shape as the 10 Q8 cabinets defined in
    static XML. The Q8 set already gets explicit per-cabinet test
    coverage above; this class catches drift on the 30 extended SKUs.

    Failure modes this guards against:
      - a code change to catalog_expansion narrows or breaks the
        _AUDIT_STEPS membership map without touching the static XML,
        so the Q8 set still passes but expanded cabinets render as a
        flat scroll
      - the soft-close default extension stops firing on the expanded
        set (e.g. an indent error in the if-attr_name=='Accessories'
        block)
      - a future audit-rule on Wood Species or Finish ships only via
        static XML and silently doesn't bind to catalog-expanded SKUs
    """

    def _all_sb_templates(self):
        """All SB-* templates that catalog_expansion produces."""
        return self.env["product.template"].search([
            ("default_code", "=like", "SB-%"),
        ])

    def test_01_every_catalog_cabinet_has_some_step_lines(self):
        """No SB-* cabinet should render as a flat-list scroll. Even
        accessory SKUs that only carry a couple of attributes should
        get those attributes grouped into a step bucket so the wizard
        is visually consistent across the catalog."""
        skipped = []  # documented exemptions (e.g. SB-WORKTOP)
        for tmpl in self._all_sb_templates():
            attr_count = len(tmpl.attribute_line_ids)
            step_count = len(tmpl.config_step_line_ids)
            if attr_count == 0:
                # Nothing to group — fine.
                skipped.append(tmpl.default_code)
                continue
            self.assertGreater(
                step_count, 0,
                f"{tmpl.default_code} has {attr_count} attribute_lines "
                f"but no step_lines — would render as a flat scroll. "
                f"catalog_expansion._AUDIT_STEPS may have lost a name.",
            )

    def test_02_soft_close_default_on_every_accessories_line(self):
        """Every cabinet that exposes the Accessories attribute should
        default to Soft-Close pre-selected. catalog_expansion seeds
        this on the 30 extended SKUs in the same loop that seeds
        attribute_line value_ids."""
        soft_close = self._ref("value_accessory_soft_close")
        accessories_attr = self._ref("attr_accessories")
        for tmpl in self._all_sb_templates():
            acc_line = tmpl.attribute_line_ids.filtered(
                lambda l: l.attribute_id.id == accessories_attr.id
            )
            if not acc_line:
                continue
            self.assertEqual(
                acc_line.default_val.id, soft_close.id,
                f"{tmpl.default_code}: Accessories line missing the "
                "Soft-Close default. catalog_expansion's Phase 2I "
                "block (line ~360 — `if attr_name == 'Accessories'`) "
                "may have stopped firing on this cabinet shape.",
            )

    def test_03_q8_and_extended_cabinets_share_step_shape(self):
        """Spot-check that 4 representative extended cabinets carry
        the same 4 audit step labels the Q8 set does — no extra
        buckets, no missing buckets."""
        expected_labels = {
            "Construction & Sizing", "Door & Finish",
            "Hardware & Sides", "Interior & Accessories",
        }
        for sku in ("SB-CORNER-BLIND", "SB-WALL-GLASS",
                    "SB-VAN-1DR", "SB-TALL-FRIDGE"):
            tmpl = self.env["product.template"].search([
                ("default_code", "=", sku),
            ], limit=1)
            if not tmpl:
                self.skipTest(f"{sku} not in DB — extended catalog "
                              "may have changed; update this list.")
            seen = set(tmpl.config_step_line_ids.mapped(
                "config_step_id.name"))
            self.assertEqual(
                seen, expected_labels,
                f"{sku}: step labels diverged from Q8 set. Seen={seen}",
            )
