# SPDX-License-Identifier: AGPL-3.0-or-later
#
# Tests for ``product.config.session.create_get_bom`` — the chain that
# produces a ``mrp.bom`` record when a configurable product variant is
# created via the wizard.
#
# Context (from ``docs/notes/post-merge-followups.md`` ``[REF] (b)``):
# the 19.0 migration verified that the create_get_bom code path RUNS
# without error (commit 135d275 includes the ``env.context = ctx`` →
# ``with_context(ctx)`` migration fix). What was NOT previously
# asserted by any test in the OCA suite was the CORRECTNESS of the
# BoM produced — a valid-but-wrong BoM (wrong components, missing
# operations, incorrect quantities) would pass every test currently
# in place. These tests close that gap.
#
# Coverage:
#   * Branch 1 — no parent BoM: ``bom_line_ids`` are constructed from
#     option-products attached to the variant's attribute values.
#   * Branch 2 — parent BoM with ``config_set`` lines: ``bom_line_ids``
#     are constructed by iterating the parent's lines and filtering by
#     ``config_set.configuration_ids.value_ids`` against the variant's
#     attribute values.
#   * Branch 3 — idempotency: re-running the chain for the same variant
#     returns the existing BoM rather than creating a duplicate.

from odoo.addons.base.tests.common import BaseCommon


class TestBoMContents(BaseCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Two attribute values with associated option-products. The
        # option-products are what ``create_get_bom`` Branch 1 iterates
        # to construct BoM lines.
        option_a_tmpl = cls.env["product.template"].create(
            {
                "name": "Option Component A",
                "type": "consu",
                "list_price": 10.0,
            }
        )
        option_b_tmpl = cls.env["product.template"].create(
            {
                "name": "Option Component B",
                "type": "consu",
                "list_price": 20.0,
            }
        )
        cls.option_a = option_a_tmpl.product_variant_id
        cls.option_b = option_b_tmpl.product_variant_id

        cls.attribute = cls.env["product.attribute"].create(
            {
                "name": "Component Attribute",
                "create_variant": "no_variant",
                "value_ids": [
                    (0, 0, {"name": "Value A", "product_id": cls.option_a.id}),
                    (0, 0, {"name": "Value B", "product_id": cls.option_b.id}),
                ],
            }
        )
        cls.value_a = cls.attribute.value_ids.filtered(lambda v: v.name == "Value A")
        cls.value_b = cls.attribute.value_ids.filtered(lambda v: v.name == "Value B")

        # Configurable template
        cls.template = cls.env["product.template"].create(
            {
                "name": "BoM-Asserted Configurable Template",
                "type": "consu",
                "config_ok": True,
                "attribute_line_ids": [
                    (
                        0,
                        0,
                        {
                            "attribute_id": cls.attribute.id,
                            "value_ids": [(6, 0, (cls.value_a + cls.value_b).ids)],
                        },
                    )
                ],
            }
        )

    def _make_session_and_confirm(self, template, attr_value):
        """Create a config session, set its value_ids, confirm it.

        Confirm triggers ``create_get_variant`` which (because _mrp is
        installed and overrides it) auto-calls ``create_get_bom``. This
        is the same chain the wizard flows through via
        ``action_config_done`` — but invoked directly on the session
        model for test isolation from sale/mrp wizard subclasses.
        """
        session = (
            self.env["product.config.session"]
            .sudo()
            .create_get_session(
                product_tmpl_id=template.id,
                user_id=self.env.user.id,
            )
        )
        session.value_ids = [(6, 0, attr_value.ids)]
        session.action_confirm()
        return session

    # ------------------------------------------------------------------
    # Branch 1 — no parent BoM (lines from option-products)
    # ------------------------------------------------------------------
    def test_branch_1_no_parent_bom_lines_from_option_products(self):
        """Configuring with value_a (whose option-product is option_a)
        should produce a BoM with exactly one line referencing option_a.
        Branch 1 of create_get_bom: parent_bom search returns empty,
        so attr_products is iterated."""
        # Sanity: no pre-existing BoM for this template
        self.assertFalse(
            self.env["mrp.bom"].search([("product_tmpl_id", "=", self.template.id)]),
            "No BoM should exist for the template prior to configuration",
        )

        session = self._make_session_and_confirm(self.template, self.value_a)
        variant = session.product_id

        # The session produced a variant
        self.assertTrue(variant, "Session.action_confirm should produce a variant")
        self.assertEqual(variant.product_tmpl_id, self.template)

        # The BoM was created for this variant
        bom = self.env["mrp.bom"].search(
            [
                ("product_tmpl_id", "=", self.template.id),
                ("product_id", "=", variant.id),
            ]
        )
        self.assertEqual(
            len(bom),
            1,
            "create_get_bom should produce exactly one BoM for the variant",
        )

        # BoM lines: exactly one, referencing option_a
        self.assertEqual(
            len(bom.bom_line_ids),
            1,
            "Branch 1 (no parent BoM) should produce one line per "
            "option-product attached to the variant's selected values",
        )
        self.assertEqual(
            bom.bom_line_ids[0].product_id,
            self.option_a,
            "The single BoM line should reference option_a (the "
            "option-product of value_a)",
        )
        self.assertEqual(
            bom.bom_line_ids[0].product_qty,
            1.0,
            "Default qty for option-product lines is 1.0",
        )

    # ------------------------------------------------------------------
    # Branch 2 — parent BoM with config_set lines
    # ------------------------------------------------------------------
    def test_branch_2_parent_bom_filtered_by_config_set(self):
        """When a parent BoM exists (template-level, product_id=False)
        with bom_lines that have config_set_id linking to specific
        attribute values, create_get_bom iterates the parent's lines
        and only includes those whose config_set's configuration_ids
        match the variant's attribute values."""
        # Set up a parent BoM at the template level with one line per
        # attribute value, each gated by a config_set.
        config_set_a = self.env["mrp.bom.line.configuration.set"].create(
            {
                "name": "Set for Value A",
                "configuration_ids": [
                    (
                        0,
                        0,
                        {
                            "value_ids": [(6, 0, [self.value_a.id])],
                        },
                    )
                ],
            }
        )
        config_set_b = self.env["mrp.bom.line.configuration.set"].create(
            {
                "name": "Set for Value B",
                "configuration_ids": [
                    (
                        0,
                        0,
                        {
                            "value_ids": [(6, 0, [self.value_b.id])],
                        },
                    )
                ],
            }
        )

        parent_bom = self.env["mrp.bom"].create(
            {
                "product_tmpl_id": self.template.id,
                "product_id": False,
                "type": "normal",
                "bom_line_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.option_a.id,
                            "product_qty": 3,
                            "config_set_id": config_set_a.id,
                        },
                    ),
                    (
                        0,
                        0,
                        {
                            "product_id": self.option_b.id,
                            "product_qty": 5,
                            "config_set_id": config_set_b.id,
                        },
                    ),
                ],
            }
        )
        self.assertEqual(len(parent_bom.bom_line_ids), 2)

        # Configure with value_a — Branch 2 should select only the
        # bom_line gated by config_set_a (config_set_b does not apply
        # because value_b is not selected).
        session = self._make_session_and_confirm(self.template, self.value_a)
        variant = session.product_id

        variant_bom = self.env["mrp.bom"].search(
            [
                ("product_tmpl_id", "=", self.template.id),
                ("product_id", "=", variant.id),
            ]
        )
        self.assertEqual(
            len(variant_bom),
            1,
            "Exactly one variant-specific BoM should be produced",
        )
        self.assertEqual(
            len(variant_bom.bom_line_ids),
            1,
            "Branch 2 should select only the parent line whose "
            "config_set matches the variant's attribute values",
        )
        self.assertEqual(
            variant_bom.bom_line_ids[0].product_id,
            self.option_a,
            "Selected line should reference option_a (gated by config_set_a)",
        )
        self.assertEqual(
            variant_bom.bom_line_ids[0].product_qty,
            3.0,
            "Quantity should be inherited from the parent BoM line, not defaulted",
        )

    # ------------------------------------------------------------------
    # Branch 3 — idempotency: re-creating BoM for an existing variant
    # ------------------------------------------------------------------
    def test_branch_3_idempotency_returns_existing_bom(self):
        """If a BoM already exists for the variant, create_get_bom
        must return that existing BoM rather than creating a duplicate."""
        session_1 = self._make_session_and_confirm(self.template, self.value_a)
        variant = session_1.product_id

        bom_after_first = self.env["mrp.bom"].search(
            [
                ("product_tmpl_id", "=", self.template.id),
                ("product_id", "=", variant.id),
            ]
        )
        self.assertEqual(len(bom_after_first), 1)
        first_bom_id = bom_after_first.id

        # Directly invoke create_get_bom a second time on the same
        # variant via a new session — this is the idempotency path.
        session_2 = (
            self.env["product.config.session"]
            .sudo()
            .create_get_session(
                product_tmpl_id=self.template.id,
                user_id=self.env.user.id,
            )
        )
        returned_bom = session_2.create_get_bom(
            variant=variant, product_tmpl_id=self.template
        )

        self.assertEqual(
            returned_bom.id,
            first_bom_id,
            "create_get_bom must return the existing BoM, not duplicate it",
        )
        # No duplicate created:
        all_boms = self.env["mrp.bom"].search(
            [
                ("product_tmpl_id", "=", self.template.id),
                ("product_id", "=", variant.id),
            ]
        )
        self.assertEqual(
            len(all_boms),
            1,
            "No duplicate BoM should exist after the second create_get_bom call",
        )
