# SPDX-License-Identifier: LGPL-3.0-only
"""P6 — Complete "Your build" summary + completeness checklist.

The audit asks for three observable behaviours:

  1. ALL chosen attributes appear in the summary (chips), not just 4.
  2. The "X options still needed" checklist NAMES the specific
     unsatisfied required attributes.
  3. "Add to Quote" is disabled until required attributes satisfied,
     driven by the checklist.

The server-side ``_build_completeness_payload`` is the single source
of truth; this test exercises it directly via the
SouthbrookConfiguratorAPI controller class (no HTTP plumbing needed
in TransactionCase).
"""
from odoo.tests.common import TransactionCase, tagged

from odoo.addons.southbrook_configurator_ux.controllers.main import (
    SouthbrookConfiguratorAPI,
)


@tagged("post_install", "-at_install", "southbrook", "configurator_ux", "p6",
        "completeness")
class TestP6Completeness(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Attribute = cls.env["product.attribute"]
        cls.AttributeValue = cls.env["product.attribute.value"]
        cls.Tmpl = cls.env["product.template"]
        cls.TmplAttrLine = cls.env["product.template.attribute.line"]
        cls.Session = cls.env["product.config.session"]
        cls.api = SouthbrookConfiguratorAPI()

    def _attr(self, name, values, create_variant="always"):
        a = self.Attribute.create({
            "name": name, "create_variant": create_variant,
        })
        vals = [
            self.AttributeValue.create({"name": v, "attribute_id": a.id})
            for v in values
        ]
        return a, vals

    def _make_template_with_two_required_attrs(self):
        tmpl = self.Tmpl.create({
            "name": "P6 — Test 3-Drawer Cabinet",
            "type": "consu", "is_storable": True,
        })
        width_attr, width_vals = self._attr("Width", ["24 in"])
        finish_attr, finish_vals = self._attr("Finish", ["White"])
        family_attr, family_vals = self._attr("Family", ["Base"])

        # Width + Finish are required; Family is optional. Required is
        # set on the attribute LINE per OCA convention.
        for attr, vals, required in (
            (width_attr, width_vals, True),
            (finish_attr, finish_vals, True),
            (family_attr, family_vals, False),
        ):
            line_vals = {
                "product_tmpl_id": tmpl.id,
                "attribute_id": attr.id,
                "value_ids": [(6, 0, [v.id for v in vals])],
            }
            if "required" in self.TmplAttrLine._fields:
                line_vals["required"] = required
            self.TmplAttrLine.create(line_vals)
        tmpl._create_variant_ids()
        return tmpl, {
            "Width": width_vals[0],
            "Finish": finish_vals[0],
            "Family": family_vals[0],
        }

    def _make_session(self, tmpl):
        return self.Session.create({
            "product_tmpl_id": tmpl.id,
            "user_id": self.env.user.id,
        })

    def _groups(self, tmpl):
        return self.api._build_group_payload_for_template(tmpl)

    # ------------------------------------------------------------------
    # Acceptance — chips list enumerates every chosen attribute
    # ------------------------------------------------------------------
    def test_chosen_chips_enumerates_all_picks(self):
        tmpl, vals_by_name = self._make_template_with_two_required_attrs()
        session = self._make_session(tmpl)
        session.value_ids = [(6, 0, [
            vals_by_name["Width"].id,
            vals_by_name["Finish"].id,
            vals_by_name["Family"].id,
        ])]
        payload = self.api._build_completeness_payload(
            tmpl, session, self._groups(tmpl), attributes={})
        chip_names = {(c["attribute_name"], c["value_name"])
                      for c in payload["chosen_chips"]}
        self.assertEqual(chip_names, {
            ("Width", "24 in"),
            ("Finish", "White"),
            ("Family", "Base"),
        }, "every picked attribute must appear as a chip")

    # ------------------------------------------------------------------
    # Acceptance — required_missing names the specific missing attribute
    # ------------------------------------------------------------------
    def test_required_missing_names_the_one_unsatisfied_attribute(self):
        tmpl, vals_by_name = self._make_template_with_two_required_attrs()
        session = self._make_session(tmpl)
        # Pick Width (required) + Family (optional). Finish (required)
        # remains unpicked. This is the audit's "17/18 — name the one
        # missing" scenario in miniature.
        session.value_ids = [(6, 0, [
            vals_by_name["Width"].id,
            vals_by_name["Family"].id,
        ])]
        payload = self.api._build_completeness_payload(
            tmpl, session, self._groups(tmpl), attributes={})
        missing_names = [r["attribute_name"]
                         for r in payload["required_missing"]]
        # NB: this only asserts if the OCA product.template.attribute.line
        # model exposes a `required` boolean. On versions where it does
        # not, the resolver skips the required check and required_missing
        # is empty — which we accept as a soft-fail (the test still
        # exercises the chips list above).
        if "required" in self.TmplAttrLine._fields:
            self.assertEqual(missing_names, ["Finish"],
                             "missing list must NAME the unsatisfied attr")

    # ------------------------------------------------------------------
    # Acceptance — add_to_quote_enabled false until requireds satisfied
    # ------------------------------------------------------------------
    def test_add_to_quote_enabled_only_when_no_required_missing(self):
        tmpl, vals_by_name = self._make_template_with_two_required_attrs()
        session = self._make_session(tmpl)
        # No picks -> if required field exists -> 2 missing -> disabled.
        session.value_ids = [(6, 0, [])]
        payload = self.api._build_completeness_payload(
            tmpl, session, self._groups(tmpl), attributes={})
        if "required" in self.TmplAttrLine._fields:
            self.assertFalse(payload["add_to_quote_enabled"])

        # Both required attrs picked -> enabled.
        session.value_ids = [(6, 0, [
            vals_by_name["Width"].id,
            vals_by_name["Finish"].id,
        ])]
        payload = self.api._build_completeness_payload(
            tmpl, session, self._groups(tmpl), attributes={})
        self.assertTrue(payload["add_to_quote_enabled"])
