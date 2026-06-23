# SPDX-License-Identifier: LGPL-3.0-only
"""P2 regression — bulk-tools bar must be invisible to non-internal users.

The configurator template at views/configurator_template.xml emits a
data-internal-user attribute that the OWL bundle reads to decide whether
to render the Bulk tools bar (Template Layout / Import Product buttons).
A regression that lets share=True (portal / public / trade customer)
users see "1" here would expose internal tooling on the storefront.

The gating chain has four layers — server template default, server
t-att condition, client-side strict "==1" comparison, and OWL prop
falsy default. This test locks the server side (layers 1 + 2) because
that's the one a controller refactor could break.

Run:
    odoo --no-http --test-enable -u southbrook_configurator_ux \\
        -d <db> --stop-after-init
"""
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install",
        "southbrook_cfg_bulkbar", "southbrook_cfg_gating")
class TestBulkBarGating(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # The parent template's xpath target — the v2 body inherits from
        # website_product_configurator.product_configurator and replaces
        # #unique_product_configurator. We render the parent so the
        # inherit is applied and we exercise the real production path.
        cls.template_xmlid = (
            "website_product_configurator.product_configurator"
        )
        # Any configurable Southbrook cabinet works; base_1dr is the
        # canonical fixture used by sibling tests.
        cls.product_tmpl = cls.env.ref("southbrook_estimating.base_1dr")
        # The portal_user group is the canonical "trade customer"
        # surface. Portal users are share=True per Odoo convention.
        cls.portal_user = cls.env["res.users"].create({
            "name": "Trade Customer (test)",
            "login": "test_trade_cust_bulkbar@example.invalid",
            # Odoo 19 renamed res.users.groups_id → group_ids; old name
            # was silently accepted by create() but the M2M write was a
            # no-op, leaving the portal_user as a regular internal user
            # and failing the share=True assertion downstream.
            "group_ids": [(6, 0, [cls.env.ref("base.group_portal").id])],
        })
        # base.user_admin is share=False (internal), the natural
        # opposite for this test.
        cls.internal_user = cls.env.ref("base.user_admin")

    def _render_with_user(self, user):
        """Render the configurator parent template as `user`, returning
        the resulting HTML bytes. Uses ir.qweb so we don't need an HTTP
        round trip — the gating attribute is set at render time."""
        # The QWeb template references `product_tmpl` and `request`. We
        # don't run inside a real http request, so the t-att-data-
        # internal-user expression reads request.env.user. Using
        # _render with sudo + with_user mimics how the website
        # controller would resolve the user.
        env_as_user = self.env(user=user.id)
        return env_as_user["ir.qweb"]._render(
            self.template_xmlid,
            {
                "product_tmpl": self.product_tmpl.with_env(env_as_user),
                # The website templates expect `request` in context;
                # supplying a minimal stub avoids NameError on render.
                "request": type("R", (), {"env": env_as_user})(),
            },
        )

    def test_portal_user_has_no_bulk_bar(self):
        """Non-internal: data-internal-user must be "0" and the bar
        must not be rendered."""
        html = self._render_with_user(self.portal_user)
        self.assertIn(
            'data-internal-user="0"', html,
            "Portal user must NOT be flagged as internal — gating "
            "depends on this attribute being '0'.",
        )
        self.assertNotIn(
            'data-internal-user="1"', html,
            "data-internal-user='1' leaked to a portal user.",
        )
        # The Bulk tools bar is rendered by OWL client-side, but its
        # label text never reaches the server-rendered HTML — so the
        # canonical assertion is on the gating attribute. We still
        # double-check the labels are absent in case a future change
        # moves the bar into server-rendered QWeb.
        self.assertNotIn(
            "Template Layout", html,
            "Bulk-tools 'Template Layout' button leaked to a portal "
            "user's server-rendered HTML.",
        )
        self.assertNotIn(
            "Import Product", html,
            "Bulk-tools 'Import Product' button leaked to a portal "
            "user's server-rendered HTML.",
        )

    def test_public_user_has_no_bulk_bar(self):
        """Anonymous visitor must be treated as non-internal."""
        public_user = self.env.ref("base.public_user")
        html = self._render_with_user(public_user)
        self.assertIn('data-internal-user="0"', html)
        self.assertNotIn('data-internal-user="1"', html)

    def test_internal_user_gets_bulk_bar_gate_open(self):
        """Sanity check the opposite — internal staff DOES see the
        gate flipped to "1". Without this assertion the previous two
        tests could pass with a trivial bug that always emits "0"."""
        html = self._render_with_user(self.internal_user)
        self.assertIn(
            'data-internal-user="1"', html,
            "Internal (share=False) user must be flagged so the OWL "
            "bundle can render the Bulk tools bar for them.",
        )

    def test_jsbundle_strict_internal_user_comparison(self):
        """The OWL bootstrap parses data-internal-user with a strict
        =='1' check. Lock that invariant — anything other than "1"
        (including "true", " 1 ", empty, missing) must read as false.

        Reads the JS bundle as text. A future refactor that loosens
        this comparison (e.g. `Boolean(attr)`, or a truthy check) would
        fail the test because the new shape wouldn't match."""
        import os
        bundle = os.path.join(
            os.path.dirname(__file__),
            "..", "static", "src", "js", "configurator.esm.js",
        )
        with open(bundle, "r", encoding="utf-8") as fh:
            js = fh.read()
        self.assertIn(
            'data-internal-user', js,
            "JS bundle no longer reads the gating attribute — the "
            "server-side test alone is insufficient.",
        )
        self.assertIn(
            '=== "1"', js,
            "JS bundle no longer uses a strict '1' comparison — a "
            "loose check would let truthy non-'1' values flip the "
            "gate open. See bootstrapConfiguratorV2 in "
            "static/src/js/configurator.esm.js.",
        )
