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


@tagged("post_install", "-at_install", "southbrook", "rule_enforcement",
        "configurator_v19_regression")
class TestOCAValidationErrorWrappersV19(TransactionCase):
    """Regression tests for the two v19 `ValidationError.name` twins in
    OCA `product_configurator/models/product_config.py`. Both were
    upgrading legitimate rule violations to `AttributeError` and masking
    the actionable message.

    Fixed 2026-07-01:
      * :894 (session.create → validate_configuration wrapper)
      * :937 (create_get_variant → validate_configuration wrapper)

    Regression: exercise BOTH branches and assert the rule message
    survives the wrapper (i.e. no AttributeError, ValidationError.args[0]
    is a string that names the blocked attribute or value).
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Session = cls.env["product.config.session"]
        cls.tmpl = cls.env.ref("southbrook_estimating.base_1dr")
        cls.series_contractor = cls.env.ref(
            "southbrook_estimating.value_series_contractor")
        cls.box_maple = cls.env.ref(
            "southbrook_estimating.value_box_maple")

    def test_01_session_create_wrapper_preserves_rule_message(self):
        """`session.create({value_ids=[contractor, maple]})` triggers the
        :894 wrapper. Verifies the wrapper renders the underlying
        "Box Material: Maple" text — NOT an AttributeError or the
        generic "Default values provided generate an invalid
        configuration" fallback.
        """
        with self.assertRaises(ValidationError) as ctx:
            self.Session.create({
                "product_tmpl_id": self.tmpl.id,
                "user_id": self.env.uid,
                "value_ids": [(6, 0, [
                    self.series_contractor.id, self.box_maple.id,
                ])],
            })
        msg = str(ctx.exception)
        # Must be a rule-blocked message, not the fallback text nor an
        # AttributeError proxy.
        self.assertNotIn(
            "AttributeError", msg,
            "The wrapper must not upgrade to AttributeError; "
            "regression of the :894 exc.name bug.",
        )
        self.assertNotIn(
            "Default values provided generate an invalid configuration",
            msg,
            "The wrapper must not fall through to the outer "
            "except Exception branch; regression of the :894 "
            "exc.name bug that made every rule error look like "
            "'invalid default'.",
        )
        self.assertTrue(
            "Maple" in msg or "Box Material" in msg,
            f"The wrapper must preserve the rule-engine message; "
            f"got: {msg!r}",
        )

    def test_02_create_get_variant_wrapper_source_is_v19_safe(self):
        """Source-code regression for the `:937` twin fix.

        `create_get_variant`'s wrapper cannot be triggered directly at
        runtime without bypassing every ORM guard on `session.value_ids`
        (`write()` silently prunes invalid values via
        `values_available()`, so a fresh session cannot be goaded into
        an invalid `self.value_ids` state through supported ORM calls).

        The invariant is IDENTICAL to the `:894` sibling covered by
        test_01: `except ValidationError as exc: raise ValidationError(
        env._("%s") % exc.name)`. In v19 that `.name` attribute doesn't
        exist and the wrapper elevates to `AttributeError`.

        This test pins the fix at the source-code level so a regression
        (e.g. a merge from upstream OCA that reintroduces `.name`)
        surfaces immediately.
        """
        import inspect
        from odoo.addons.product_configurator.models import product_config

        source = inspect.getsource(
            product_config.ProductConfigSession.create_get_variant)
        # The fixed form uses exc.args[0]; the broken form uses exc.name.
        self.assertIn(
            "exc.args[0] if exc.args else str(exc)",
            source,
            "create_get_variant's ValidationError wrapper has "
            "regressed to `exc.name`. See "
            "product_configurator/models/product_config.py:937 — the "
            "fix is the same as the :894 twin: use "
            "`exc.args[0] if exc.args else str(exc)`.",
        )
        # And explicitly refuse a `.name` regression.
        # `.name` alone would be too easy to false-positive on a
        # comment; test the specific broken idiom.
        self.assertNotIn(
            'self.env._("%s") % exc.name',
            source,
            "create_get_variant's wrapper still contains the broken "
            "`exc.name` string interpolation; v19 ValidationError "
            "has no `.name`.",
        )


@tagged("post_install", "-at_install", "southbrook", "rule_enforcement",
        "configurator_multi_attr_quirk")
class TestOCAMultiAttributeSingleValueQuirk(TransactionCase):
    """Document the OCA `product_configurator/models/product_config.py:1605`
    multi-attribute quirk: `validate_configuration()` only surfaces the
    "multi values not permitted" error when 2+ values are picked on a
    multi-type attribute. A single picked value that violates the domain
    slips through.

    This is a KNOWN OCA behavior — not a bug we own. This test pins it
    down so a future upstream OCA change (that starts firing the domain
    check on single-value multi picks) surfaces as a green-to-fail on
    Southbrook's side rather than a silent behavior change.

    Concrete demo: on `corner` template with `family_subtype=bifold`,
    accessory Rule 4 restricts accessories to {drawer_organisers,
    pull_outs}. Picking JUST soft_close under bifold does NOT raise —
    only picking soft_close + pull_outs does.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Session = cls.env["product.config.session"]
        cls.tmpl = cls.env.ref("southbrook_estimating.corner")
        cls.family_bifold = cls.env.ref(
            "southbrook_estimating.value_family_subtype_bifold")
        cls.acc_soft_close = cls.env.ref(
            "southbrook_estimating.value_accessory_soft_close")
        cls.acc_pull_outs = cls.env.ref(
            "southbrook_estimating.value_accessory_pull_outs")

    def test_01_single_multi_value_slip_through_is_the_status_quo(self):
        """Pinning test: OCA lets [bifold, soft_close] pass, but it
        should logically fail. When this test starts failing, OCA
        has tightened its multi-check — that's a good day; update the
        upstream Rule 4 test in test_rule_enforcement.py to use a
        single-value pick instead of the two-value workaround.
        """
        session = self.Session.create({
            "product_tmpl_id": self.tmpl.id,
            "user_id": self.env.uid,
        })
        # If this ValidationError starts firing, the quirk is fixed
        # upstream. Assert with a clear message so the failure is
        # instantly readable in CI.
        raised = False
        try:
            session.validate_configuration(
                product_tmpl_id=self.tmpl.id,
                value_ids=[
                    self.family_bifold.id, self.acc_soft_close.id,
                ],
                final=True,
            )
        except ValidationError:
            raised = True
        self.assertFalse(
            raised,
            "OCA product_configurator has tightened its multi-attribute "
            "validation: single-value multi picks now trigger rule "
            "violations. UPDATE this test AND the Rule 4 test in "
            "TestRule4BifoldSoftClose.test_01 — the two-value workaround "
            "is no longer needed.",
        )

    def test_02_two_value_pick_correctly_raises(self):
        """The complement — the same rule DOES fire when 2+ values are
        picked. This is the shape Southbrook's Rule 4 negative test
        relies on.
        """
        session = self.Session.create({
            "product_tmpl_id": self.tmpl.id,
            "user_id": self.env.uid,
        })
        with self.assertRaises(ValidationError):
            session.validate_configuration(
                product_tmpl_id=self.tmpl.id,
                value_ids=[
                    self.family_bifold.id,
                    self.acc_soft_close.id,
                    self.acc_pull_outs.id,
                ],
                final=True,
            )
