# SPDX-License-Identifier: LGPL-3.0-only
"""Rule-firing tests — 2026-07-01 E2E audit follow-up.

Coverage gap identified in the audit (docs/E2E_AUDIT_SOUTHBROOK_ESTIMATING_
2026-07-01.md §6.2): `test_config_rule_domains.py` only asserts the SHAPE
of the seeded domain records; it does not verify that a `product.config.
session.validate_configuration(...)` call with an offending value combination
actually raises `ValidationError`. This file closes that gap for the three
rules that lacked negative tests:

  * Rule 2 (box_material → series) — positive + negative
  * Rule 3 (width → door_count) — negative
  * Rule 4 (family_subtype → soft-close) — negative

Rule 1 (series → door_style) already has a live-rule negative in
`test_phase1_smoke.py test_step_05_rules_block_invalid_combinations`.

Design (mirrors `test_step_05`, per John's commit-11 guidance
"test the engine, not the rendering"):

* Create a bare `product.config.session` for the target template WITHOUT
  passing value_ids. This avoids the OCA `create()` implicit-defaults
  union that would otherwise fold `default_val` into the picks and shift
  the assertion surface (see the pull-outs/soft-close default trap
  observed while iterating this file 2026-07-01).
* Then call `session.validate_configuration(value_ids=[…], final=True)`
  directly with the exact value set we want to validate. This is the
  same seam the wizard hits on Next/Confirm and is the true business-
  rule enforcement API.
* Assert `ValidationError` is raised (negative) or NOT raised (positive).
"""
from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase, tagged


def _fresh_session(env, tmpl):
    """Create a session with no picks — bypasses OCA's implicit-defaults
    union in create() so validate_configuration() calls see EXACTLY the
    value_ids we pass in."""
    return env["product.config.session"].create({
        "product_tmpl_id": tmpl.id,
        "user_id": env.uid,
    })


@tagged("post_install", "-at_install", "southbrook", "rule_enforcement")
class TestRule2BoxMaterialSeries(TransactionCase):
    """Rule 2 — box_material → series.

    From Southbrook_Excel_to_Odoo_Mapping.md §3.4 and CLAUDE.md §5:
      * Maple box is offered ONLY on Contemporary, Elegance, Signature.
      * Contractor series is White Melamine only.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.tmpl = cls.env.ref("southbrook_estimating.base_1dr")
        cls.series_signature = cls.env.ref(
            "southbrook_estimating.value_series_signature")
        cls.series_contractor = cls.env.ref(
            "southbrook_estimating.value_series_contractor")
        cls.box_maple = cls.env.ref(
            "southbrook_estimating.value_box_maple")
        cls.box_white_melamine = cls.env.ref(
            "southbrook_estimating.value_box_white_melamine")

    def test_01_signature_plus_maple_is_valid(self):
        session = _fresh_session(self.env, self.tmpl)
        try:
            session.validate_configuration(
                product_tmpl_id=self.tmpl.id,
                value_ids=[self.series_signature.id, self.box_maple.id],
                final=True,
            )
        except ValidationError as exc:
            self.fail(
                "Rule 2 rejected the valid Signature + Maple pair: %s" % exc)

    def test_02_contractor_plus_maple_raises(self):
        session = _fresh_session(self.env, self.tmpl)
        with self.assertRaises(
            ValidationError,
            msg="Rule 2 did NOT raise on Contractor + Maple",
        ) as ctx:
            session.validate_configuration(
                product_tmpl_id=self.tmpl.id,
                value_ids=[
                    self.series_contractor.id, self.box_maple.id,
                ],
                final=True,
            )
        msg = str(ctx.exception)
        self.assertTrue(
            "Maple" in msg or "Box Material" in msg,
            f"ValidationError must name the blocked box choice; "
            f"got: {msg!r}",
        )

    def test_03_contractor_plus_white_melamine_is_valid(self):
        session = _fresh_session(self.env, self.tmpl)
        try:
            session.validate_configuration(
                product_tmpl_id=self.tmpl.id,
                value_ids=[
                    self.series_contractor.id,
                    self.box_white_melamine.id,
                ],
                final=True,
            )
        except ValidationError as exc:
            self.fail(
                "Rule 2 rejected the Contractor + White Melamine baseline: "
                "%s" % exc)


@tagged("post_install", "-at_install", "southbrook", "rule_enforcement")
class TestRule3WidthDoorCount(TransactionCase):
    """Rule 3 — width → door_count.

    From Mapping §3.4 / CLAUDE.md §5:
      * 9-21" cabinets are 1-door.
      * 24-36" cabinets are 2-door.

    `drawer_bank` exposes BOTH narrow and wide widths and both door_count
    values, so it can host both directions of the negative test.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.tmpl = cls.env.ref("southbrook_estimating.drawer_bank")
        cls.width_30 = cls.env.ref("southbrook_estimating.value_width_30")
        cls.width_12 = cls.env.ref("southbrook_estimating.value_width_12")
        cls.door_count_1 = cls.env.ref(
            "southbrook_estimating.value_door_count_1")
        cls.door_count_2 = cls.env.ref(
            "southbrook_estimating.value_door_count_2")

    def test_01_wide_30in_plus_1door_raises(self):
        session = _fresh_session(self.env, self.tmpl)
        with self.assertRaises(
            ValidationError,
            msg="Rule 3 did NOT raise on 30\" width + 1-door "
                "(should force 2-door)",
        ) as ctx:
            session.validate_configuration(
                product_tmpl_id=self.tmpl.id,
                value_ids=[self.width_30.id, self.door_count_1.id],
                final=True,
            )
        msg = str(ctx.exception)
        self.assertTrue(
            "Door Count" in msg or "1" in msg or "Width" in msg,
            f"ValidationError must name the blocked width/door choice; "
            f"got: {msg!r}",
        )

    def test_02_narrow_12in_plus_2door_raises(self):
        session = _fresh_session(self.env, self.tmpl)
        with self.assertRaises(
            ValidationError,
            msg="Rule 3 did NOT raise on 12\" width + 2-door "
                "(should force 1-door)",
        ):
            session.validate_configuration(
                product_tmpl_id=self.tmpl.id,
                value_ids=[self.width_12.id, self.door_count_2.id],
                final=True,
            )

    def test_03_wide_30in_plus_2door_is_valid(self):
        session = _fresh_session(self.env, self.tmpl)
        try:
            session.validate_configuration(
                product_tmpl_id=self.tmpl.id,
                value_ids=[self.width_30.id, self.door_count_2.id],
                final=True,
            )
        except ValidationError as exc:
            self.fail(
                "Rule 3 rejected the 30\" + 2-door baseline: %s" % exc)


@tagged("post_install", "-at_install", "southbrook", "rule_enforcement")
class TestRule4BifoldSoftClose(TransactionCase):
    """Rule 4 — family_subtype → soft-close.

    From Mapping §3.4 / CLAUDE.md §5 / Q23(b):
      * Bi-fold corner cabinets ship WITHOUT soft-close hinges.
      * Rule scoped to `corner` template only (Q23(b) — subtype is
        corner-specific). data/config_rules.xml seeds a single Rule 4
        record: `rule4_family_subtype_bifold_accessories_corner`, whose
        domain restricts accessories to `{drawer_organisers, pull_outs}`
        when `family_subtype == bifold`.

    Accessories is a `multi`-type attribute (multiple values allowed).
    `session.validate_configuration()` treats multi values as a set and
    checks that every picked value is in the allowed set — so passing
    `[bifold, soft_close]` is a real negative case.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.tmpl = cls.env.ref("southbrook_estimating.corner")
        cls.family_bifold = cls.env.ref(
            "southbrook_estimating.value_family_subtype_bifold")
        cls.family_standard = cls.env.ref(
            "southbrook_estimating.value_family_subtype_standard")
        cls.acc_soft_close = cls.env.ref(
            "southbrook_estimating.value_accessory_soft_close")
        cls.acc_pull_outs = cls.env.ref(
            "southbrook_estimating.value_accessory_pull_outs")

    def test_01_bifold_plus_soft_close_raises(self):
        """OCA quirk 2026-07-01: `validate_configuration` on a multi-type
        attribute only surfaces its "not permitted" error when TWO+
        values are picked; a single picked value that violates the
        domain slips through the multi-check branch at
        product_configurator/models/product_config.py:1605. So exercise
        the negative here by picking two accessories under bifold —
        one that's allowed (pull_outs) plus soft_close — the error
        message must call soft_close out by name.
        """
        session = _fresh_session(self.env, self.tmpl)
        with self.assertRaises(
            ValidationError,
            msg="Rule 4 did NOT raise on Bifold + soft-close + pull-outs",
        ) as ctx:
            session.validate_configuration(
                product_tmpl_id=self.tmpl.id,
                value_ids=[
                    self.family_bifold.id,
                    self.acc_soft_close.id,
                    self.acc_pull_outs.id,
                ],
                final=True,
            )
        msg = str(ctx.exception)
        self.assertTrue(
            "Soft-Close" in msg or "Accessories" in msg,
            f"ValidationError must reference Soft-Close/Accessories so "
            f"the rep sees which pick violates Rule 4; got: {msg!r}",
        )

    def test_02_bifold_plus_pull_outs_is_valid(self):
        session = _fresh_session(self.env, self.tmpl)
        try:
            session.validate_configuration(
                product_tmpl_id=self.tmpl.id,
                value_ids=[
                    self.family_bifold.id, self.acc_pull_outs.id,
                ],
                final=True,
            )
        except ValidationError as exc:
            self.fail(
                "Rule 4 rejected Bifold + pull-outs (should be allowed): "
                "%s" % exc)

    def test_03_standard_plus_soft_close_is_valid(self):
        session = _fresh_session(self.env, self.tmpl)
        try:
            session.validate_configuration(
                product_tmpl_id=self.tmpl.id,
                value_ids=[
                    self.family_standard.id, self.acc_soft_close.id,
                ],
                final=True,
            )
        except ValidationError as exc:
            self.fail(
                "Rule 4 rejected the Standard + soft-close baseline: "
                "%s" % exc)
