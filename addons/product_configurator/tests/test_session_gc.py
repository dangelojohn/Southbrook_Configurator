# Copyright 2026 OdooIQ
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
#
# Tests for product.config.session._gc_draft_sessions and its ir.cron
# wiring. Closes the [REF] (d) gap surfaced in the gap analysis: the
# table grows unbounded for any storefront deployment without
# periodic GC.

from datetime import timedelta

from odoo import fields
from odoo.tests import tagged

from .common import ProductConfiguratorTestCases


class TestSessionGC(ProductConfiguratorTestCases):
    def _make_session(self, *, state, days_old):
        """Create a session in the requested state with the right
        write_date to be either eligible or ineligible for GC.

        Two ORM concerns we work around:
        - write_date is auto-stamped on every update; we age it via
          direct SQL after creation. Acceptable scope for a GC unit
          test where rewinding the clock is the whole point.
        - The ``_check_product_id`` constraint requires
          ``state='done'`` sessions to have a ``product_id``. For
          'done' sessions in this test we create a stub variant and
          write both fields together in one ``write`` so the
          constraint is satisfied.
        """
        session = self.env["product.config.session"].create(
            {
                "product_tmpl_id": self.config_product.id,
                "user_id": self.env.user.id,
            }
        )
        if state == "done":
            # Constraint requires product_id when state=done; create
            # a stub variant of the template and write both fields
            # together in one transaction so _check_product_id sees
            # them simultaneously.
            stub_variant = (
                self.env["product.product"]
                .sudo()
                .search(
                    [("product_tmpl_id", "=", self.config_product.id)],
                    limit=1,
                )
            )
            if not stub_variant:
                stub_variant = (
                    self.env["product.product"]
                    .sudo()
                    .create({"product_tmpl_id": self.config_product.id})
                )
            session.write({"state": "done", "product_id": stub_variant.id})
        else:
            session.state = state
        # Force write_date via direct SQL — the ORM doesn't let you
        # set write_date through write(); it's auto-stamped on every
        # update. Acceptable scope for a unit test of a GC method.
        self.env.cr.execute(
            "UPDATE product_config_session SET write_date = %s WHERE id = %s",
            (fields.Datetime.now() - timedelta(days=days_old), session.id),
        )
        session.invalidate_recordset(["write_date"])
        return session

    def test_gc_collects_stale_draft(self):
        """A draft session older than the threshold is collected."""
        stale = self._make_session(state="draft", days_old=10)
        stale_id = stale.id
        deleted = self.env["product.config.session"]._gc_draft_sessions(days=7)
        self.assertGreaterEqual(deleted, 1)
        self.assertFalse(
            self.env["product.config.session"].browse(stale_id).exists(),
            "Stale draft session should be deleted",
        )

    def test_gc_preserves_fresh_draft(self):
        """A draft session NEWER than the threshold is preserved."""
        fresh = self._make_session(state="draft", days_old=2)
        fresh_id = fresh.id
        self.env["product.config.session"]._gc_draft_sessions(days=7)
        self.assertTrue(
            self.env["product.config.session"].browse(fresh_id).exists(),
            "Fresh draft session (< threshold) must be preserved",
        )

    def test_gc_preserves_done_sessions(self):
        """A 'done'-state session is preserved regardless of age.
        Done sessions reference a resolved product.product and are
        part of the audit trail; they are NEVER eligible for GC."""
        done = self._make_session(state="done", days_old=30)
        done_id = done.id
        self.env["product.config.session"]._gc_draft_sessions(days=7)
        self.assertTrue(
            self.env["product.config.session"].browse(done_id).exists(),
            "'done'-state session must be preserved regardless of age",
        )

    def test_gc_refuses_invalid_threshold(self):
        """A misconfigured threshold (< 1 day) must be refused —
        never delete sessions younger than a day. Guards against a
        zero-or-negative param value wiping live in-flight sessions."""
        stale = self._make_session(state="draft", days_old=5)
        deleted = self.env["product.config.session"]._gc_draft_sessions(days=0)
        self.assertEqual(
            deleted, 0, "GC must refuse days<1 to avoid wiping live sessions"
        )
        self.assertTrue(
            stale.exists(),
            "Session should be untouched when GC is refused",
        )

    def test_gc_uses_config_parameter_default(self):
        """When called with no argument, GC reads the threshold from
        the ir.config_parameter 'product_configurator.session_gc_days'."""
        self.env["ir.config_parameter"].sudo().set_param(
            "product_configurator.session_gc_days", "3"
        )
        stale_just_over = self._make_session(state="draft", days_old=4)
        fresh_just_under = self._make_session(state="draft", days_old=2)
        fresh_id = fresh_just_under.id
        stale_id = stale_just_over.id

        self.env["product.config.session"]._gc_draft_sessions()

        self.assertFalse(
            self.env["product.config.session"].browse(stale_id).exists(),
            "Session older than the param-configured threshold should be collected",
        )
        self.assertTrue(
            self.env["product.config.session"].browse(fresh_id).exists(),
            "Session newer than the param-configured threshold should be preserved",
        )


@tagged("post_install", "-at_install")
class TestSessionGCPostInstall(TestSessionGC):
    """Post-install GC tests that need cross-module models loaded.

    The base TestSessionGC class runs at-install (during
    product_configurator's own load phase), when add-on modules like
    product_configurator_sale haven't yet registered their models
    (sale.order.line in particular). This subclass re-runs as a
    post-install pass so the cart-reference branch of the GC method
    can be exercised on environments where _sale is installed.

    The subclass IS empty besides this docstring — it inherits the
    parent's tests AND adds the cart-reference test. When _sale is
    NOT installed, the cart-reference test skips itself via the
    in-method registry check.
    """

    def test_gc_preserves_sessions_referenced_by_cart(self):
        """A draft session referenced by a sale.order.line is preserved
        even if it would otherwise be eligible. Deleting it would
        orphan the cart line's config_session_id FK."""
        if "sale.order.line" not in self.env.registry.models:
            self.skipTest(
                "product_configurator_sale not installed; "
                "cart-protection branch is a no-op in this environment"
            )
        stale_referenced = self._make_session(state="draft", days_old=10)
        stale_referenced_id = stale_referenced.id

        # Create a cart line referencing the session
        partner = self.env["res.partner"].create({"name": "GC test buyer"})
        order = self.env["sale.order"].create({"partner_id": partner.id})
        self.env["sale.order.line"].create(
            {
                "order_id": order.id,
                "name": "GC test line",
                "product_id": self.config_product.product_variant_id.id
                or self.env["product.product"]
                .search(
                    [("product_tmpl_id", "=", self.config_product.id)], limit=1
                )
                .id,
                "config_session_id": stale_referenced.id,
                "product_uom_qty": 1.0,
            }
        )

        self.env["product.config.session"]._gc_draft_sessions(days=7)
        self.assertTrue(
            self.env["product.config.session"].browse(stale_referenced_id).exists(),
            "Draft session referenced by a sale.order.line MUST be "
            "preserved (deleting would orphan the cart line)",
        )
