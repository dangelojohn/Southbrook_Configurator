# SPDX-License-Identifier: LGPL-3.0-only
"""P1 regression — the loadError branch must never leak raw error text.

2026-06-22: a template-compile failure dumped raw generated JS onto
the storefront because the previous loadError branch rendered the
error message via t-esc, and the bootstrap mount-failure fallback
interpolated err.message into innerHTML. The fix routes all errors
through console.error and sets state.loadError to a sentinel boolean
that the template only reads for truthiness.

These tests lock that invariant.
"""
import os
import re

from odoo.tests import TransactionCase, tagged


BUNDLE = os.path.join(
    os.path.dirname(__file__),
    "..", "static", "src", "js", "configurator.esm.js",
)


@tagged("post_install", "-at_install", "southbrook_cfg_loaderror")
class TestLoadErrorSafety(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        with open(BUNDLE, "r", encoding="utf-8") as fh:
            cls.js = fh.read()

    def test_loaderror_branch_does_not_tesc_the_value(self):
        """The friendly fallback template must not contain
        t-esc="state.loadError" — that's what leaked the compile
        error / stack trace to customers before the fix."""
        self.assertNotIn(
            't-esc="state.loadError"', self.js,
            "loadError branch still renders the raw error value with "
            "t-esc. A future error could leak server detail or "
            "generated JS to the customer.",
        )
        self.assertNotIn(
            't-out="state.loadError"', self.js,
            "loadError branch uses t-out on the raw error value. "
            "Use a static safe message instead.",
        )

    def test_loaderror_branch_offers_contactus_fallback(self):
        """When the configurator can't load, the customer must have
        an explicit escape hatch — a /contactus link with a meaningful
        subject — so the sale doesn't die at the broken page."""
        # The contactQuoteHref getter produces the URL; the template
        # reads it via t-att-href. Lock both shapes.
        self.assertIn(
            'contactQuoteHref', self.js,
            "Missing the contactQuoteHref getter that powers the "
            "Request-a-quote CTA on the loadError branch.",
        )
        self.assertIn(
            "/contactus?subject=", self.js,
            "loadError fallback no longer links to /contactus.",
        )

    def test_bootstrap_mount_failure_does_not_interpolate_error(self):
        """The bootstrap's try/catch around mount(ConfiguratorV2)
        previously interpolated err.message into innerHTML. That's
        the actual code path that spilled the generated JS chunk."""
        # Find the catch block. Reject any reference to err.message,
        # String(err), or err.stack between the bootstrap's
        # 'await mount(' and the function's closing brace.
        m = re.search(
            r"async function bootstrapConfiguratorV2\(\)\s*\{(.*?)\n\}\n",
            self.js,
            re.DOTALL,
        )
        self.assertIsNotNone(
            m, "Could not locate bootstrapConfiguratorV2() body.",
        )
        body = m.group(1)
        catch_start = body.find("} catch (err)")
        self.assertGreater(
            catch_start, -1,
            "bootstrapConfiguratorV2 has no try/catch around mount().",
        )
        catch_body = body[catch_start:]
        # The console.error line legitimately references err — exclude it.
        catch_lines = [
            line for line in catch_body.split("\n")
            if "console.error" not in line and "// " not in line
        ]
        non_console = "\n".join(catch_lines)
        for forbidden in (
            "err.message", "err.stack", "String(err)", "${err",
        ):
            self.assertNotIn(
                forbidden, non_console,
                "bootstrapConfiguratorV2 mount-failure fallback "
                "interpolates %r into the visible HTML. That's "
                "exactly the path that spilled generated JS to "
                "customers on 2026-06-22." % forbidden,
            )

    def test_loaderror_state_is_sentinel_not_message(self):
        """state.loadError must never hold the error VALUE — only a
        truthy sentinel. The _captureLoadError helper is the single
        write site."""
        # All assignments to state.loadError go through _captureLoadError;
        # direct `this.state.loadError = err.message` style writes are
        # the regression we're guarding against.
        offenders = []
        for line_no, line in enumerate(self.js.split("\n"), start=1):
            if "state.loadError = " not in line:
                continue
            rhs = line.split("state.loadError = ", 1)[1].rstrip(";, \t")
            # The two allowed shapes: assigning a literal (true/false/null)
            # in the setup initial-state block, or assigning the sentinel
            # `true` from _captureLoadError. Anything else is suspect.
            allowed = (
                rhs.startswith("null")
                or rhs.startswith("true")
                or rhs.startswith("false")
            )
            if not allowed:
                offenders.append("Line %d: %s" % (line_no, line.strip()))
        self.assertFalse(
            offenders,
            "Found assignments to state.loadError that carry the "
            "raw error value. Route all error capture through "
            "_captureLoadError so the sentinel pattern stays "
            "intact:\n  " + "\n  ".join(offenders),
        )
