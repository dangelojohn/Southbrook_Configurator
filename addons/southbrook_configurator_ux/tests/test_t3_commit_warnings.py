# SPDX-License-Identifier: LGPL-3.0-only
"""T3 — Commit-with-warnings server gate.

The /state and /select responses gain commit_warnings + the count.
Three configurator-side heuristics fire:

  - Door Style contains "Custom" -> "custom_door_style" warning
  - Drawer Construction set + Drawer Slide unpicked -> "drawer_slide_default"
  - Finished Sides = None / unpicked -> "finished_sides_missing"

CTA remains enabled even with warnings — add_to_quote_enabled is
strictly required-missing only.
"""
from odoo.tests.common import TransactionCase, tagged

from odoo.addons.southbrook_configurator_ux.controllers.main import (
    SouthbrookConfiguratorAPI,
)


@tagged("post_install", "-at_install", "southbrook", "configurator_ux", "t3",
        "commit_warnings")
class TestT3CommitWarnings(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.api = SouthbrookConfiguratorAPI()
        cls.Attribute = cls.env["product.attribute"]
        cls.AttributeValue = cls.env["product.attribute.value"]
        cls.Tmpl = cls.env["product.template"]
        cls.TmplAttrLine = cls.env["product.template.attribute.line"]
        cls.Session = cls.env["product.config.session"]

    def _attr(self, name, values):
        a = self.Attribute.create({"name": name, "create_variant": "always"})
        return a, [
            self.AttributeValue.create({"name": v, "attribute_id": a.id})
            for v in values
        ]

    def _make_template_and_session(self, attrs_to_values):
        tmpl = self.Tmpl.create({
            "name": "T3 test cabinet",
            "type": "consu", "is_storable": True,
        })
        all_value_ids = []
        for attr_name, value_name in attrs_to_values.items():
            attr, vals = self._attr(attr_name, [value_name])
            self.TmplAttrLine.create({
                "product_tmpl_id": tmpl.id,
                "attribute_id": attr.id,
                "value_ids": [(6, 0, [v.id for v in vals])],
            })
            all_value_ids.extend(v.id for v in vals)
        tmpl._create_variant_ids()

        session = self.Session.create({
            "product_tmpl_id": tmpl.id,
            "user_id": self.env.user.id,
        })
        session.value_ids = [(6, 0, all_value_ids)]
        return tmpl, session

    def _completeness(self, tmpl, session):
        groups = self.api._build_group_payload_for_template(tmpl)
        return self.api._build_completeness_payload(
            tmpl, session, groups, attributes={})

    # ------------------------------------------------------------------
    # Acceptance — Custom door style fires the warning
    # ------------------------------------------------------------------
    def test_custom_door_style_warning(self):
        tmpl, session = self._make_template_and_session({
            "Door Style": "Custom (Signature)",
            "Finished Sides": "Both",  # suppress the FS warning
        })
        payload = self._completeness(tmpl, session)
        names = [w["name"] for w in payload["commit_warnings"]]
        self.assertIn("custom_door_style", names)

    # ------------------------------------------------------------------
    # Acceptance — Drawer Construction without Slide fires the info
    # ------------------------------------------------------------------
    def test_drawer_slide_default_warning(self):
        tmpl, session = self._make_template_and_session({
            "Drawer Construction": "3-Drawer Stack (Dovetail)",
            "Finished Sides": "Both",
        })
        payload = self._completeness(tmpl, session)
        names = [w["name"] for w in payload["commit_warnings"]]
        self.assertIn("drawer_slide_default", names)

    # ------------------------------------------------------------------
    # Acceptance — Drawer Slide picked suppresses the default warning
    # ------------------------------------------------------------------
    def test_drawer_slide_picked_suppresses_warning(self):
        tmpl, session = self._make_template_and_session({
            "Drawer Construction": "3-Drawer Stack (Dovetail)",
            "Drawer Slide": "King Slide K2832 21\" Soft-Close",
            "Finished Sides": "Both",
        })
        payload = self._completeness(tmpl, session)
        names = [w["name"] for w in payload["commit_warnings"]]
        self.assertNotIn("drawer_slide_default", names)

    # ------------------------------------------------------------------
    # Acceptance — Finished Sides=None fires the warning
    # ------------------------------------------------------------------
    def test_finished_sides_none_warning(self):
        tmpl, session = self._make_template_and_session({
            "Width": "24 in",
            "Finished Sides": "None",
        })
        payload = self._completeness(tmpl, session)
        names = [w["name"] for w in payload["commit_warnings"]]
        self.assertIn("finished_sides_missing", names)

    # ------------------------------------------------------------------
    # Acceptance — add_to_quote_enabled stays TRUE even with warnings
    # ------------------------------------------------------------------
    def test_warnings_do_not_disable_cta(self):
        tmpl, session = self._make_template_and_session({
            "Door Style": "Custom (Signature)",
            "Finished Sides": "None",  # fire 2 warnings
        })
        payload = self._completeness(tmpl, session)
        self.assertGreater(len(payload["commit_warnings"]), 0)
        # No required attributes -> CTA stays enabled despite warnings.
        if not payload["required_missing"]:
            self.assertTrue(payload["add_to_quote_enabled"],
                            "warnings must not disable the CTA")
