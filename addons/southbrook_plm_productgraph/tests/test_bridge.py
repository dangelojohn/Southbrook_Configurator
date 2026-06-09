# SPDX-License-Identifier: LGPL-3.0-only
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook_plm_productgraph")
class TestBridge(TransactionCase):
    """Confirms the bridge fires a pg.release when an ECO with a linked
    EBOM is applied, and stays quiet otherwise."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.user.group_ids = [(
            4, cls.env.ref("product_graph_base.group_pg_admin").id,
        ), (
            4, cls.env.ref("southbrook_plm.group_southbrook_plm_approver").id,
        )]

        # Build a released cabinet item + its EBOM (root only, no children,
        # to keep the test self-contained — the validator passes because
        # the EBOM has zero non-released child items).
        cat = cls.env.ref("product_graph_base.cat_mechanical")
        cls.cab = cls.env["pg.item"].create({
            "name": "Bridge Test Cabinet",
            "item_type": "assembly",
            "category_id": cat.id,
        })
        cls.cab.action_to_engineering()
        cls.cab_rev = cls.env["pg.revision"].create({
            "item_id": cls.cab.id,
            "name": "A",
            "change_summary": "Bridge test — initial cabinet revision.",
        })
        cls.cab_rev.action_submit_for_review()
        cls.cab_rev.action_release()

        # A real component so the EBOM has at least one line.
        cls.hinge = cls.env["pg.item"].create({
            "name": "Bridge Test Hinge",
            "item_type": "purchased",
            "category_id": cat.id,
        })
        cls.hinge.action_to_engineering()
        cls.hinge_rev = cls.env["pg.revision"].create({
            "item_id": cls.hinge.id,
            "name": "A",
            "change_summary": "Bridge test — initial hinge component.",
        })
        cls.hinge_rev.action_submit_for_review()
        cls.hinge_rev.action_release()
        tmpl = cls.env["product.template"].create({
            "name": cls.hinge.name,
            "type": "consu",
            "default_code": cls.hinge.part_number,
            "uom_id": cls.hinge.uom_id.id,
        })
        prod = tmpl.product_variant_ids[:1]
        cls.hinge.with_context(_pg_release_bypass=True).write({"product_id": prod.id})

        cls.ebom = cls.env["pg.ebom"].create({
            "root_item_id": cls.cab.id,
            "revision_id": cls.cab_rev.id,
            "ebom_line_ids": [(0, 0, {
                "pg_item_id": cls.hinge.id,
                "product_qty": 2.0,
            })],
        })
        cls.ebom.action_submit_for_review()
        cls.ebom.action_release()

        # Use a rule-kind ECO so _apply_rule is the PLM-side handler — it
        # only requires a git_ref (no mrp.bom mutation, no cut_spec touch,
        # no document attachment required). Keeps the bridge as the sole
        # thing touching mrp.bom in this test.
        cls.eco_type = cls.env["southbrook.eco.type"].create({
            "name": "Bridge Test (Rule)",
            "target_kind": "rule",
        })

    def _make_eco(self, **extra):
        vals = {
            "title": "Bridge fires release",
            "eco_type_id": self.eco_type.id,
            "git_ref": "test/abc123def456",
        }
        vals.update(extra)
        return self.env["southbrook.eco"].create(vals)

    def test_bridge_fires_release(self):
        eco = self._make_eco(pg_ebom_id=self.ebom.id)
        eco.action_approve()
        eco.action_apply()
        self.assertEqual(eco.state, "applied")
        self.assertTrue(eco.pg_release_id,
                        "Bridge did not create a pg.release.")
        self.assertEqual(eco.pg_release_id.state, "completed")
        self.assertEqual(eco.pg_release_id.ebom_id, self.ebom)
        self.assertTrue(eco.pg_release_id.mrp_bom_id)

    def test_bridge_skips_without_ebom(self):
        eco = self._make_eco()
        eco.action_approve()
        eco.action_apply()
        self.assertEqual(eco.state, "applied")
        self.assertFalse(eco.pg_release_id,
                         "Bridge fired without an EBOM link.")

    def test_bridge_skips_when_auto_release_off(self):
        eco = self._make_eco(
            pg_ebom_id=self.ebom.id,
            pg_auto_release=False,
        )
        eco.action_approve()
        eco.action_apply()
        self.assertEqual(eco.state, "applied")
        self.assertFalse(eco.pg_release_id,
                         "Bridge fired with pg_auto_release=False.")

    def test_bridge_idempotent(self):
        eco = self._make_eco(pg_ebom_id=self.ebom.id)
        eco.action_approve()
        eco.action_apply()
        first_release = eco.pg_release_id
        # Force a second apply via the same path; the idempotency check
        # in _should_trigger_pg_release should prevent another release.
        # (We can't call action_apply twice — PLM rejects re-apply — so we
        # call _should_trigger_pg_release directly.)
        self.assertFalse(eco._should_trigger_pg_release(),
                         "Idempotency check failed; would have re-released.")
        self.assertEqual(eco.pg_release_id, first_release)
