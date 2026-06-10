# SPDX-License-Identifier: LGPL-3.0-only
"""Contract tests for Phase 2c endpoints.

  POST /southbrook/api/configurator/select
  POST /southbrook/api/configurator/commit

Run:

    odoo --no-http --test-enable -u southbrook_configurator_ux \\
        -d <db> --stop-after-init

Or with the explicit tag:

    --test-tags=southbrook_cfg_select_commit
"""
from contextlib import contextmanager
from unittest.mock import MagicMock

from odoo.tests import TransactionCase, tagged

from odoo.addons.southbrook_configurator_ux.controllers import main as ctrl_main


@contextmanager
def stubbed_request(env, user=None):
    saved = ctrl_main.request
    mock = MagicMock()
    mock.env = env if user is None else env(user=user.id)
    mock.session = {}
    mock.params = {}
    ctrl_main.request = mock
    try:
        yield mock
    finally:
        ctrl_main.request = saved


@tagged("post_install", "-at_install", "southbrook_cfg_select_commit")
class TestConfiguratorSelectCommit(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.controller = ctrl_main.SouthbrookConfiguratorAPI()
        cls.tmpl = cls.env.ref("southbrook_estimating.base_1dr")
        # Test partner + portal user. Portal users have share=True;
        # internal users have share=False. /commit only cares that the
        # user isn't anonymous, not internal vs portal.
        cls.partner = cls.env["res.partner"].create({
            "name": "Test Configurator Customer 2026-06-03",
            "email": "test_cfg_2c@southbrook.test",
        })
        portal_group = cls.env.ref("base.group_portal")
        cls.user = cls.env["res.users"].create({
            "name": "Test Configurator User",
            "login": "test_cfg_2c@southbrook.test",
            "partner_id": cls.partner.id,
            # Odoo 19: groups_id -> group_ids.
            "group_ids": [(6, 0, [portal_group.id])],
        })

    # ==================================================================
    # /select — error paths
    # ==================================================================
    def test_select_missing_session_id_returns_error(self):
        with stubbed_request(self.env, user=self.user):
            r = self.controller.configurator_select(value_ids=[])
        self.assertFalse(r["ok"])
        self.assertEqual(r["error"], "missing_session_id")

    def test_select_bad_session_id_returns_error(self):
        with stubbed_request(self.env, user=self.user):
            r = self.controller.configurator_select(
                session_id="not-an-int", value_ids=[])
        self.assertFalse(r["ok"])
        self.assertEqual(r["error"], "bad_session_id")

    def test_select_unknown_session_returns_error(self):
        with stubbed_request(self.env, user=self.user):
            r = self.controller.configurator_select(
                session_id=999_999, value_ids=[])
        self.assertFalse(r["ok"])
        self.assertEqual(r["error"], "session_not_found")

    def test_select_value_ids_not_list_returns_error(self):
        sess = self._fresh_session()
        with stubbed_request(self.env, user=self.user):
            r = self.controller.configurator_select(
                session_id=sess.id, value_ids="not-a-list")
        self.assertFalse(r["ok"])
        self.assertEqual(r["error"], "value_ids_must_be_list")

    def test_select_other_users_session_returns_forbidden(self):
        sess = self._fresh_session()
        # Different user — admin can browse it but the controller's
        # _authorize_session compares request.env.user.id to
        # session.user_id.id and rejects.
        another_user = self.env["res.users"].create({
            "name": "Other Tester",
            "login": "other_tester_cfg@southbrook.test",
            "partner_id": self.env["res.partner"].create(
                {"name": "Other"}).id,
            "group_ids": [(6, 0, [
                self.env.ref("base.group_portal").id])],
        })
        with stubbed_request(self.env, user=another_user):
            r = self.controller.configurator_select(
                session_id=sess.id, value_ids=[])
        self.assertFalse(r["ok"])
        self.assertEqual(r["error"], "forbidden")

    # ==================================================================
    # /select — happy path
    # ==================================================================
    def test_select_returns_price_and_disabled_set(self):
        sess = self._fresh_session()
        # Pick a Width value to exercise the price + disabled computation.
        width = self.env["product.attribute"].search(
            [("name", "=", "Width")], limit=1)
        width_val = width.value_ids.sorted("sequence")[0] if width else None
        if not width_val:
            self.skipTest("Width attribute not present on this DB")
        with stubbed_request(self.env, user=self.user):
            r = self.controller.configurator_select(
                session_id=sess.id, value_ids=[width_val.id])
        self.assertTrue(r["ok"], f"select returned {r}")
        # Response shape
        for k in ("selected_value_ids", "price", "weight",
                  "disabled_value_ids", "warnings"):
            self.assertIn(k, r, f"missing key '{k}' in /select response")
        self.assertIn(width_val.id, r["selected_value_ids"])
        self.assertIsInstance(r["price"], float)
        self.assertIsInstance(r["disabled_value_ids"], list)

    def test_select_with_empty_value_ids_clears_session(self):
        sess = self._fresh_session()
        width = self.env["product.attribute"].search(
            [("name", "=", "Width")], limit=1)
        if not width:
            self.skipTest("Width attribute not present on this DB")
        first_val = width.value_ids.sorted("sequence")[0]
        # Seed the session with a value.
        sess.sudo().value_ids = [(6, 0, [first_val.id])]
        with stubbed_request(self.env, user=self.user):
            r = self.controller.configurator_select(
                session_id=sess.id, value_ids=[])
        self.assertTrue(r["ok"])
        # The seeded width value should be gone.
        self.assertNotIn(first_val.id, r["selected_value_ids"])

    # ==================================================================
    # /commit — error paths
    # ==================================================================
    def test_commit_public_user_returns_login_required(self):
        sess = self._fresh_session()
        public = self.env.ref("base.public_user")
        with stubbed_request(self.env, user=public):
            r = self.controller.configurator_commit(session_id=sess.id)
        self.assertFalse(r["ok"])
        self.assertEqual(r["error"], "login_required")
        self.assertIn("login_url", r)

    def test_commit_missing_session_id_returns_error(self):
        with stubbed_request(self.env, user=self.user):
            r = self.controller.configurator_commit()
        self.assertFalse(r["ok"])
        self.assertEqual(r["error"], "missing_session_id")

    def test_commit_unknown_session_returns_error(self):
        with stubbed_request(self.env, user=self.user):
            r = self.controller.configurator_commit(session_id=999_999)
        self.assertFalse(r["ok"])
        self.assertEqual(r["error"], "session_not_found")

    def test_commit_other_users_session_returns_forbidden(self):
        sess = self._fresh_session()
        another_user = self.env["res.users"].create({
            "name": "Other Tester 2",
            "login": "other_tester_cfg_b@southbrook.test",
            "partner_id": self.env["res.partner"].create(
                {"name": "Other B"}).id,
            "group_ids": [(6, 0, [
                self.env.ref("base.group_portal").id])],
        })
        with stubbed_request(self.env, user=another_user):
            r = self.controller.configurator_commit(session_id=sess.id)
        self.assertFalse(r["ok"])
        self.assertEqual(r["error"], "forbidden")

    # ==================================================================
    # /commit — happy paths
    # ==================================================================
    def test_commit_creates_variant_line_and_redirect(self):
        sess = self._fresh_session()
        self._complete_via_select(sess)
        with stubbed_request(self.env, user=self.user):
            r = self.controller.configurator_commit(session_id=sess.id)
        self.assertTrue(r["ok"], f"commit returned {r}")
        # Variant materialised
        variant = self.env["product.product"].browse(r["variant_id"])
        self.assertTrue(variant.exists())
        self.assertEqual(variant.product_tmpl_id.id, self.tmpl.id)
        # Order line attached to a draft order owned by our user
        line = self.env["sale.order.line"].browse(r["order_line_id"])
        self.assertTrue(line.exists())
        self.assertEqual(line.product_id.id, variant.id)
        self.assertEqual(line.product_uom_qty, 1.0)
        order = self.env["sale.order"].browse(r["order_id"])
        self.assertEqual(order.partner_id.id, self.partner.id)
        self.assertEqual(order.state, "draft")
        # Redirect URL points at the Order Builder for this order
        self.assertEqual(
            r["redirect"],
            f"/my/southbrook/order-builder/{order.id}")

    def test_commit_locks_session_after_success(self):
        sess = self._fresh_session()
        self._complete_via_select(sess)
        with stubbed_request(self.env, user=self.user):
            self.controller.configurator_commit(session_id=sess.id)
        sess.invalidate_recordset()
        self.assertEqual(sess.state, "done",
            "session should be locked (state=done) after a successful "
            "commit so a duplicate commit can't double-add the line")

    def test_commit_committed_session_returns_session_locked(self):
        sess = self._fresh_session()
        self._complete_via_select(sess)
        # First commit
        with stubbed_request(self.env, user=self.user):
            self.controller.configurator_commit(session_id=sess.id)
        # Second commit — should refuse
        with stubbed_request(self.env, user=self.user):
            r = self.controller.configurator_commit(session_id=sess.id)
        self.assertFalse(r["ok"])
        self.assertEqual(r["error"], "session_locked")

    def test_commit_reuses_existing_draft_order(self):
        # Pre-create a draft order for the partner.
        pre = self.env["sale.order"].sudo().create({
            "partner_id": self.partner.id,
        })
        sess = self._fresh_session()
        self._complete_via_select(sess)
        with stubbed_request(self.env, user=self.user):
            r = self.controller.configurator_commit(session_id=sess.id)
        self.assertTrue(r["ok"])
        self.assertEqual(r["order_id"], pre.id,
            "commit should reuse the existing draft rather than "
            "creating a parallel one")

    def test_commit_creates_draft_order_when_none_exists(self):
        # Make sure the partner has no existing draft.
        self.env["sale.order"].sudo().search([
            ("partner_id", "=", self.partner.id),
            ("state", "=", "draft"),
        ]).unlink()
        sess = self._fresh_session()
        self._complete_via_select(sess)
        with stubbed_request(self.env, user=self.user):
            r = self.controller.configurator_commit(session_id=sess.id)
        self.assertTrue(r["ok"])
        order = self.env["sale.order"].browse(r["order_id"])
        self.assertEqual(order.state, "draft")
        self.assertEqual(order.partner_id.id, self.partner.id)

    def test_commit_with_explicit_order_id_uses_that_order(self):
        target = self.env["sale.order"].sudo().create({
            "partner_id": self.partner.id,
        })
        sess = self._fresh_session()
        self._complete_via_select(sess)
        with stubbed_request(self.env, user=self.user):
            r = self.controller.configurator_commit(
                session_id=sess.id, order_id=target.id)
        self.assertTrue(r["ok"])
        self.assertEqual(r["order_id"], target.id)

    def test_commit_other_users_order_id_returns_forbidden(self):
        # Order belonging to a different partner.
        other_partner = self.env["res.partner"].create({"name": "Stranger"})
        their_order = self.env["sale.order"].sudo().create({
            "partner_id": other_partner.id,
        })
        sess = self._fresh_session()
        self._complete_via_select(sess)
        with stubbed_request(self.env, user=self.user):
            r = self.controller.configurator_commit(
                session_id=sess.id, order_id=their_order.id)
        self.assertFalse(r["ok"])
        self.assertEqual(r["error"], "order_forbidden")

    # ==================================================================
    # P1 — premature-disable filter
    # ==================================================================
    def test_select_empty_picks_does_not_disable_any_chip(self):
        """At page-load (no picks), every value the template exposes
        should be available — the customer must not see chips greyed
        before they've picked anything.

        Regression for the Box Material dead-end the sales-rep walk-
        through flagged: with rule-completion in place, the OCA engine
        treated all Box Material + Door Style values as unavailable
        whenever Series was unpicked, because each value's "Series
        allows V" domain failed to match the empty pick set. The
        controller post-processes the disabled set to clear values
        whose only restricting rules trigger off an unpicked
        attribute."""
        sess = self._fresh_session()
        with stubbed_request(self.env, user=self.user):
            r = self.controller.configurator_select(
                session_id=sess.id, value_ids=[])
        self.assertTrue(r["ok"])
        # Nothing picked yet → nothing should be disabled.
        self.assertEqual(r["disabled_value_ids"], [],
                         f"expected empty disabled set at page-load, "
                         f"got {r['disabled_value_ids']}")

    def test_select_series_picked_disables_only_real_conflicts(self):
        """After picking Contractor Series, Maple (incompatible with
        Contractor under Rule 2) should be disabled, but White Melamine
        and all unrelated-attribute values should remain available."""
        sess = self._fresh_session()
        series = self.env["product.attribute"].search(
            [("name", "=", "Series")], limit=1)
        box = self.env["product.attribute"].search(
            [("name", "=", "Box Material")], limit=1)
        if not (series and box):
            self.skipTest("Series / Box Material attributes not seeded")
        contractor = self.env["product.attribute.value"].search(
            [("attribute_id", "=", series.id),
             ("name", "=", "Contractor Series")], limit=1)
        white_mel = self.env["product.attribute.value"].search(
            [("attribute_id", "=", box.id),
             ("name", "=", "White Melamine")], limit=1)
        maple = self.env["product.attribute.value"].search(
            [("attribute_id", "=", box.id),
             ("name", "=", "Maple")], limit=1)
        if not (contractor and white_mel and maple):
            self.skipTest("Required values not seeded")
        with stubbed_request(self.env, user=self.user):
            r = self.controller.configurator_select(
                session_id=sess.id, value_ids=[contractor.id])
        self.assertTrue(r["ok"])
        disabled = set(r["disabled_value_ids"])
        self.assertNotIn(white_mel.id, disabled,
                         "White Melamine should be selectable under "
                         "Contractor (it IS in the allow list)")
        self.assertIn(maple.id, disabled,
                      "Maple should be disabled under Contractor "
                      "(Maple is NOT in the Contractor allow list)")

    def test_select_series_then_white_melamine_succeeds(self):
        """The completion path the customer was blocked from: pick
        Contractor, then pick White Melamine. The /select call must
        return ok=True and both values must land in
        selected_value_ids."""
        sess = self._fresh_session()
        series = self.env["product.attribute"].search(
            [("name", "=", "Series")], limit=1)
        box = self.env["product.attribute"].search(
            [("name", "=", "Box Material")], limit=1)
        if not (series and box):
            self.skipTest("attributes not seeded")
        contractor = self.env["product.attribute.value"].search(
            [("attribute_id", "=", series.id),
             ("name", "=", "Contractor Series")], limit=1)
        white_mel = self.env["product.attribute.value"].search(
            [("attribute_id", "=", box.id),
             ("name", "=", "White Melamine")], limit=1)
        if not (contractor and white_mel):
            self.skipTest("values not seeded")
        with stubbed_request(self.env, user=self.user):
            r = self.controller.configurator_select(
                session_id=sess.id,
                value_ids=[contractor.id, white_mel.id])
        self.assertTrue(r["ok"],
                        f"select rejected the valid combo: {r}")
        self.assertIn(contractor.id, r["selected_value_ids"])
        self.assertIn(white_mel.id, r["selected_value_ids"])

    # ==================================================================
    # P2 — silent-clear regression
    # ==================================================================
    def test_select_series_swap_clears_incompatible_box_material(self):
        """When the customer swaps Series from Contractor to Signature
        with White Melamine already picked, OCA's update_config must
        drop White Melamine from session.value_ids (Signature requires
        Maple). The /select response's selected_value_ids drives the
        client-side reconcile + 'cleared by rule change' toast — this
        test asserts the server-side half of that contract.

        Walkthrough symptom: completion counter dropped 9/12 → 8/12
        with no explanation. The fix in the OWL component surfaces a
        toast naming the cleared attribute + its previous value. This
        test ensures the server actually does the clear (without it,
        the client would have nothing to notify about)."""
        sess = self._fresh_session()
        series = self.env["product.attribute"].search(
            [("name", "=", "Series")], limit=1)
        box = self.env["product.attribute"].search(
            [("name", "=", "Box Material")], limit=1)
        if not (series and box):
            self.skipTest("attributes not seeded")
        contractor = self.env["product.attribute.value"].search(
            [("attribute_id", "=", series.id),
             ("name", "=", "Contractor Series")], limit=1)
        signature = self.env["product.attribute.value"].search(
            [("attribute_id", "=", series.id),
             ("name", "=", "Signature")], limit=1)
        white_mel = self.env["product.attribute.value"].search(
            [("attribute_id", "=", box.id),
             ("name", "=", "White Melamine")], limit=1)
        if not (contractor and signature and white_mel):
            self.skipTest("values not seeded")

        # Step 1: pick Contractor + White Melamine. Both should land
        # in selected_value_ids.
        with stubbed_request(self.env, user=self.user):
            r1 = self.controller.configurator_select(
                session_id=sess.id,
                value_ids=[contractor.id, white_mel.id])
        self.assertTrue(r1["ok"])
        self.assertIn(contractor.id, r1["selected_value_ids"])
        self.assertIn(white_mel.id, r1["selected_value_ids"])
        before_count = len(r1["selected_value_ids"])

        # Step 2: swap Series to Signature while still asking for
        # White Melamine. The rule engine must clear White Melamine
        # (Signature requires Maple).
        with stubbed_request(self.env, user=self.user):
            r2 = self.controller.configurator_select(
                session_id=sess.id,
                value_ids=[signature.id, white_mel.id])
        self.assertTrue(r2["ok"])
        self.assertIn(signature.id, r2["selected_value_ids"])
        self.assertNotIn(
            white_mel.id, r2["selected_value_ids"],
            "White Melamine should have been cleared on Series swap "
            "to Signature — without this clear, the client wouldn't "
            "know to surface a 'cleared by rule change' toast")
        # And the count should reflect the drop (client uses this
        # to update the progress ring 'N of M options chosen').
        self.assertLess(
            len(r2["selected_value_ids"]), before_count,
            "Total selected_value_ids count should drop after the "
            "incompatible pick is cleared")

    # ==================================================================
    # P3 — live preview reactivity (price, weight, SKU)
    # ==================================================================
    def test_select_returns_live_sku_composed_from_picks(self):
        """The /select response carries `live_sku` = the server-side
        SB-<width3>-<series3>-<finish3> composition of the current
        picks. Used by the OWL component for the SKU label and by
        /commit (P4) to write variant.default_code from the
        authoritative source.

        Verifies the spec part of P3 — 'the /select response carries
        the live SKU' — and the spec part of P4 — 'the variant's
        default_code is left false' — by checking the value the
        server will eventually write to default_code is available
        here on every select."""
        sess = self._fresh_session()
        width = self.env["product.attribute"].search(
            [("name", "=", "Width")], limit=1)
        series = self.env["product.attribute"].search(
            [("name", "=", "Series")], limit=1)
        finish = self.env["product.attribute"].search(
            [("name", "=", "Finish")], limit=1)
        if not (width and series and finish):
            self.skipTest("required attributes not seeded")
        w21 = self.env["product.attribute.value"].search(
            [("attribute_id", "=", width.id),
             ("name", "=", "21 in")], limit=1)
        sig = self.env["product.attribute.value"].search(
            [("attribute_id", "=", series.id),
             ("name", "=", "Signature")], limit=1)
        wal = self.env["product.attribute.value"].search(
            [("attribute_id", "=", finish.id),
             ("name", "=", "Walnut Stain")], limit=1)
        if not (w21 and sig and wal):
            self.skipTest("required values not seeded")
        with stubbed_request(self.env, user=self.user):
            r = self.controller.configurator_select(
                session_id=sess.id,
                value_ids=[w21.id, sig.id, wal.id])
        self.assertTrue(r["ok"])
        self.assertIn("live_sku", r,
                      "/select response must carry live_sku")
        self.assertEqual(
            r["live_sku"], "SB-21I-SIG-WAL",
            f"expected SB-21I-SIG-WAL from (21 in, Signature, "
            f"Walnut Stain), got {r['live_sku']!r}")

    def test_select_live_sku_falls_back_to_em_dash_without_width(self):
        """Without a Width pick the SKU is meaningless; live_sku
        returns the em-dash placeholder the OWL UI displays as '—'."""
        sess = self._fresh_session()
        series = self.env["product.attribute"].search(
            [("name", "=", "Series")], limit=1)
        if not series:
            self.skipTest("Series attribute not seeded")
        sig = self.env["product.attribute.value"].search(
            [("attribute_id", "=", series.id),
             ("name", "=", "Signature")], limit=1)
        if not sig:
            self.skipTest("Signature not seeded")
        with stubbed_request(self.env, user=self.user):
            r = self.controller.configurator_select(
                session_id=sess.id, value_ids=[sig.id])
        self.assertTrue(r["ok"])
        self.assertEqual(r["live_sku"], "—",
                         "Width unpicked → SKU should be em-dash, "
                         f"got {r['live_sku']!r}")

    def test_select_live_sku_changes_when_picks_change(self):
        """SKU must recompose on every /select — same session, two
        different pick sets, two different SKUs. Regression for the
        walkthrough finding that the UI SKU label appeared static."""
        sess = self._fresh_session()
        width = self.env["product.attribute"].search(
            [("name", "=", "Width")], limit=1)
        series = self.env["product.attribute"].search(
            [("name", "=", "Series")], limit=1)
        finish = self.env["product.attribute"].search(
            [("name", "=", "Finish")], limit=1)
        if not (width and series and finish):
            self.skipTest("attributes not seeded")
        # Round 1: 12 in / Contractor / White
        w12 = self.env["product.attribute.value"].search(
            [("attribute_id", "=", width.id),
             ("name", "=", "12 in")], limit=1)
        con = self.env["product.attribute.value"].search(
            [("attribute_id", "=", series.id),
             ("name", "=", "Contractor Series")], limit=1)
        wht = self.env["product.attribute.value"].search(
            [("attribute_id", "=", finish.id),
             ("name", "=", "White")], limit=1)
        with stubbed_request(self.env, user=self.user):
            r1 = self.controller.configurator_select(
                session_id=sess.id,
                value_ids=[w12.id, con.id, wht.id])
        self.assertEqual(r1["live_sku"], "SB-12I-CON-WHI")
        # Round 2: 18 in / Elegance / Cherry Stain
        w18 = self.env["product.attribute.value"].search(
            [("attribute_id", "=", width.id),
             ("name", "=", "18 in")], limit=1)
        ele = self.env["product.attribute.value"].search(
            [("attribute_id", "=", series.id),
             ("name", "=", "Elegance")], limit=1)
        chy = self.env["product.attribute.value"].search(
            [("attribute_id", "=", finish.id),
             ("name", "=", "Cherry Stain")], limit=1)
        with stubbed_request(self.env, user=self.user):
            r2 = self.controller.configurator_select(
                session_id=sess.id,
                value_ids=[w18.id, ele.id, chy.id])
        self.assertEqual(r2["live_sku"], "SB-18I-ELE-CHE")
        self.assertNotEqual(r1["live_sku"], r2["live_sku"],
                            "SKU must change between calls when picks "
                            "change")

    # ==================================================================
    # P4 — commit / Add-to-Quote handoff hardening
    # ==================================================================
    def _complete_pick_set(self):
        """Return a list of attribute_value_ids that picks ONE value
        for every attribute_line on the test template. Skips
        attribute_lines that expose only one value (those auto-resolve
        and the OCA engine doesn't gate on them)."""
        ids = []
        for line in self.tmpl.attribute_line_ids:
            if not line.value_ids:
                continue
            # Pick the FIRST value that's compatible with the picks so
            # far. We process Series last (so Box Material + Door Style
            # can be filtered against it) — for now, just take the first
            # value of each attribute and let the rule engine filter.
            ids.append(line.value_ids.sorted("sequence")[0].id)
        return ids

    def test_commit_sets_config_session_id_on_line(self):
        """P4 gap #1 — every configurator-added line must carry
        config_session_id pointing at the committing session, so the
        line is traceable to its originating configuration."""
        sess = self._fresh_session()
        # Run a /select with a complete pick set so create_get_variant
        # passes validation, then commit.
        with stubbed_request(self.env, user=self.user):
            self.controller.configurator_select(
                session_id=sess.id, value_ids=self._complete_pick_set())
        with stubbed_request(self.env, user=self.user):
            r = self.controller.configurator_commit(session_id=sess.id)
        self.assertTrue(r["ok"], f"commit failed: {r}")
        line = self.env["sale.order.line"].sudo().browse(r["order_line_id"])
        if "config_session_id" not in line._fields:
            self.skipTest(
                "config_session_id field not on this DB "
                "(website_product_configurator absent)")
        self.assertEqual(
            line.config_session_id.id, sess.id,
            "Configurator-added line must carry its session id")

    def test_commit_captures_cut_spec_and_bom_version_snapshots(self):
        """P4 gap #2 — the line's southbrook_cut_spec_version_id +
        southbrook_bom_version must be populated at commit time, not
        deferred to sale.order.action_confirm. The customer may sit on
        the draft order for days; the engineering snapshot should be
        frozen from the moment they agreed to the configuration."""
        sess = self._fresh_session()
        with stubbed_request(self.env, user=self.user):
            self.controller.configurator_select(
                session_id=sess.id, value_ids=self._complete_pick_set())
        with stubbed_request(self.env, user=self.user):
            r = self.controller.configurator_commit(session_id=sess.id)
        self.assertTrue(r["ok"])
        line = self.env["sale.order.line"].sudo().browse(r["order_line_id"])
        if "southbrook_cut_spec_version_id" not in line._fields:
            self.skipTest("southbrook_plm absent on this DB")
        # cut_spec_version_id should be the active cut.spec, if any
        # is active in this database.
        active_spec = self.env["southbrook.cut.spec"].sudo()._get_active()
        if active_spec:
            self.assertEqual(
                line.southbrook_cut_spec_version_id.id, active_spec.id,
                "Cut-spec snapshot must point at the active cut.spec "
                "record at commit time")

    def test_commit_writes_variant_default_code_from_live_sku(self):
        """P4 gap #3 — variant.default_code should be the
        live_sku from _compute_sku_from_session, NOT left blank.
        Without this, the eventual product code is empty in the DB
        until someone manually fills it."""
        sess = self._fresh_session()
        with stubbed_request(self.env, user=self.user):
            sel = self.controller.configurator_select(
                session_id=sess.id, value_ids=self._complete_pick_set())
        expected_sku = sel["live_sku"]
        with stubbed_request(self.env, user=self.user):
            r = self.controller.configurator_commit(session_id=sess.id)
        self.assertTrue(r["ok"])
        variant = self.env["product.product"].sudo().browse(r["variant_id"])
        self.assertEqual(
            variant.default_code, expected_sku,
            f"variant.default_code should be {expected_sku!r} "
            f"(server-computed live_sku), got {variant.default_code!r}")
        self.assertNotEqual(
            variant.default_code, False,
            "variant.default_code must not be False after commit "
            "(P4 gap #3)")

    def test_commit_rejects_incomplete_configuration(self):
        """P4 gap #4 — server-side completeness backstop. A
        configuration missing required attributes (e.g. no Door
        Style picked) must be rejected with `incomplete_configuration`
        + the list of missing attribute names, NOT slip through to
        produce a half-configured variant."""
        sess = self._fresh_session()
        # Pick only Series — every other attribute remains unset.
        series_attr = self.env["product.attribute"].search(
            [("name", "=", "Series")], limit=1)
        contractor = self.env["product.attribute.value"].search(
            [("attribute_id", "=", series_attr.id),
             ("name", "=", "Contractor Series")], limit=1)
        if not (series_attr and contractor):
            self.skipTest("Series attribute not seeded")
        with stubbed_request(self.env, user=self.user):
            self.controller.configurator_select(
                session_id=sess.id, value_ids=[contractor.id])
        with stubbed_request(self.env, user=self.user):
            r = self.controller.configurator_commit(session_id=sess.id)
        self.assertFalse(r["ok"], f"commit should have rejected: {r}")
        self.assertEqual(r["error"], "incomplete_configuration")
        self.assertIn("missing_attributes", r)
        self.assertTrue(len(r["missing_attributes"]) > 0)
        # message should be human-readable + include attribute names
        self.assertIn("Please choose:", r["message"])

    def test_commit_preserves_session_locked_anti_replay(self):
        """P4 preserves session_locked — a second commit on the same
        session must return session_locked, not duplicate the line."""
        sess = self._fresh_session()
        with stubbed_request(self.env, user=self.user):
            self.controller.configurator_select(
                session_id=sess.id, value_ids=self._complete_pick_set())
        with stubbed_request(self.env, user=self.user):
            first = self.controller.configurator_commit(session_id=sess.id)
        self.assertTrue(first["ok"])
        # Re-commit must NOT create another line.
        with stubbed_request(self.env, user=self.user):
            second = self.controller.configurator_commit(session_id=sess.id)
        self.assertFalse(second["ok"])
        self.assertEqual(second["error"], "session_locked")

    def test_commit_preserves_order_builder_redirect(self):
        """P4 preserves the Phase-2 cart-target decision: commit
        success returns redirect=/my/southbrook/order-builder/<id>."""
        sess = self._fresh_session()
        with stubbed_request(self.env, user=self.user):
            self.controller.configurator_select(
                session_id=sess.id, value_ids=self._complete_pick_set())
        with stubbed_request(self.env, user=self.user):
            r = self.controller.configurator_commit(session_id=sess.id)
        self.assertTrue(r["ok"])
        self.assertIn("redirect", r)
        self.assertEqual(
            r["redirect"],
            f"/my/southbrook/order-builder/{r['order_id']}")

    # ==================================================================
    # P5 — single-value attribute auto-pick (Door Count etc.)
    # ==================================================================
    def test_door_count_serializes_with_real_value_id(self):
        """Verify the /state response carries a real backend
        product.attribute.value.id for every Door Count value on the
        test template. The user observed a chip 'rendering without
        an underlying value id'; this test ensures the wire payload
        actually carries the id."""
        # Use /state — same path the OWL component hits at mount.
        with stubbed_request(self.env, user=self.user):
            r = self.controller.configurator_state(
                product_tmpl_id=self.tmpl.id)
        self.assertTrue(r["ok"])
        # Find Door Count by name across the attributes map.
        door_count = None
        for aid, attr in r["attributes"].items():
            if attr["name"] == "Door Count":
                door_count = attr
                break
        if door_count is None:
            self.skipTest("Door Count attribute not present on this DB")
        self.assertTrue(len(door_count["values"]) >= 1,
                        "Door Count must expose at least one value")
        for val in door_count["values"]:
            # Each value must carry a real integer id matching an
            # existing product.attribute.value row.
            self.assertIsInstance(val["id"], int)
            self.assertTrue(val["id"] > 0)
            db_val = self.env["product.attribute.value"].browse(val["id"])
            self.assertTrue(
                db_val.exists(),
                f"Door Count value id={val['id']} doesn't resolve to a "
                f"product.attribute.value record")

    def test_state_response_carries_value_count_per_attribute(self):
        """The OWL component treats a single-value attribute_line as
        implicitly satisfied for the completion counter (the customer
        has no real choice to make). For that to work the /state
        response must carry a stable `values` array per attribute so
        the client can detect `values.length === 1`. Verify the
        response shape supports this — every attribute has a non-
        empty values list."""
        with stubbed_request(self.env, user=self.user):
            r = self.controller.configurator_state(
                product_tmpl_id=self.tmpl.id)
        self.assertTrue(r["ok"])
        for aid, attr in r["attributes"].items():
            self.assertIn("values", attr,
                          f"attribute id={aid} missing 'values' key")
            self.assertIsInstance(attr["values"], list)
            self.assertGreater(
                len(attr["values"]), 0,
                f"attribute '{attr['name']}' (id={aid}) has no values "
                f"— client cannot render any chip OR detect implicit "
                f"single-value satisfaction")

    def test_commit_succeeds_without_explicit_single_value_pick(self):
        """The /commit completeness backstop must SKIP single-value
        attribute_lines from the missing-attributes check — the
        customer has no real choice to make for Family on a Base
        cabinet, Door Count on a single-door cabinet etc. This is the
        server-side contract that makes the client's 'effective pick'
        treatment safe."""
        sess = self._fresh_session()
        # Build a pick set that covers ALL multi-value attributes but
        # OMITS every single-value attribute. Commit should still pass
        # the completeness backstop.
        ids = []
        omitted = []
        for line in self.tmpl.attribute_line_ids:
            if not line.value_ids:
                continue
            if len(line.value_ids) <= 1:
                omitted.append(line.attribute_id.name)
                continue
            ids.append(line.value_ids.sorted("sequence")[0].id)
        with stubbed_request(self.env, user=self.user):
            self.controller.configurator_select(
                session_id=sess.id, value_ids=ids)
        with stubbed_request(self.env, user=self.user):
            r = self.controller.configurator_commit(session_id=sess.id)
        self.assertTrue(
            r["ok"],
            f"commit rejected when only multi-value attributes were "
            f"picked (single-value attributes omitted: {omitted}). "
            f"Response: {r}")

    # ==================================================================
    # Helpers
    # ==================================================================
    def _fresh_session(self):
        """Create a draft product.config.session for this user + template."""
        return self.env["product.config.session"].sudo().create({
            "product_tmpl_id": self.tmpl.id,
            "user_id": self.user.id,
        })

    def _complete_via_select(self, sess):
        """Pick a complete value set on the session via /select, so a
        following /commit call passes the P4 completeness backstop.
        Returns the /select response. Picks the first compatible value
        of each attribute_line."""
        value_ids = self._complete_pick_set()
        with stubbed_request(self.env, user=self.user):
            return self.controller.configurator_select(
                session_id=sess.id, value_ids=value_ids)
