# SPDX-License-Identifier: LGPL-3.0-only
"""P0 regression — the OWL configurator template must compile clean.

2026-06-22: a single `or`/`not` (Python-style word operator) inside an
OWL t-att-* expression broke EVERY product detail page site-wide. The
compile error surfaced only at runtime in the browser, so no Python /
QWeb test caught it.

These tests scan the JS bundle that ships the OWL template and assert
no Python-style bare-word logical operators (`and`, `or`, `not`)
appear inside template attribute expressions. They also lock the
specific Add-to-Quote button's disabled binding so a future regression
on that exact line trips the test immediately.

Run:
    odoo --no-http --test-enable -u southbrook_configurator_ux \\
        -d <db> --stop-after-init
"""
import os
import re

from odoo.tests import TransactionCase, tagged


BUNDLE = os.path.join(
    os.path.dirname(__file__),
    "..", "static", "src", "js", "configurator.esm.js",
)

# Matches:   t-<any-attr>="...<space>(and|or|not)<space>..."
# Captures the line so a failing case prints what we found.
TATTR_WITH_WORD_OP = re.compile(
    r't-(?:if|elif|att|att-[a-z-]+|on-[a-z-]+|foreach|key)="[^"]*'
    r'\b(and|or|not)\s+[a-zA-Z_$][^"]*"',
    re.IGNORECASE,
)


@tagged("post_install", "-at_install", "southbrook_cfg_template_compile")
class TestConfiguratorTemplateCompile(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        with open(BUNDLE, "r", encoding="utf-8") as fh:
            cls.js = fh.read()
        cls.lines = cls.js.split("\n")

    def test_no_python_word_operators_in_template_attrs(self):
        """OWL compiles attribute expressions to JavaScript. Bare-word
        operators emit as identifiers and break the bundle. Sweep every
        t-* attribute expression in the file."""
        offenders = []
        for idx, line in enumerate(self.lines, start=1):
            m = TATTR_WITH_WORD_OP.search(line)
            if m:
                offenders.append(
                    "Line %d: bare '%s' inside a t-* expression: %s"
                    % (idx, m.group(1), line.strip())
                )
        self.assertFalse(
            offenders,
            "OWL template attribute(s) use Python-style word operators "
            "instead of JS (||, &&, !). The bundle will fail to "
            "compile at runtime:\n  "
            + "\n  ".join(offenders),
        )

    def test_add_to_quote_button_uses_js_operators(self):
        """Lock the exact binding that broke 2026-06-22. A regression
        on this specific line is the most likely repeat."""
        m = re.search(
            r't-att-disabled="\(state\.adding\s*'
            r'(\|\||or)\s*'
            r'(!|not\s+)state\.addToQuoteEnabled\)',
            self.js,
        )
        self.assertIsNotNone(
            m,
            "Could not find the Add-to-Quote disabled binding. It "
            "must read (state.adding || !state.addToQuoteEnabled).",
        )
        op_or, op_not = m.group(1), m.group(2)
        self.assertEqual(
            op_or, "||",
            "Add-to-Quote disabled binding uses 'or' (Python word "
            "operator) instead of '||' (JS). The bundle will fail to "
            "compile site-wide. See configurator.esm.js around the "
            'sb_cfg_btn_primary "Add to Quote" button.',
        )
        self.assertEqual(
            op_not, "!",
            "Add-to-Quote disabled binding uses 'not ' (Python word "
            "operator) instead of '!' (JS). The bundle will fail to "
            "compile site-wide.",
        )

    def test_add_to_quote_aria_disabled_matches_visual_disabled(self):
        """A11y consistency: aria-disabled must mirror the visual
        disabled state. Previously the binding only checked
        addToQuoteEnabled and missed the in-flight `adding` window."""
        m = re.search(
            r't-att-aria-disabled="\(state\.adding\s*\|\|\s*'
            r'!state\.addToQuoteEnabled\)\s*\?\s*'
            r"'true'\s*:\s*null",
            self.js,
        )
        self.assertIsNotNone(
            m,
            "Add-to-Quote aria-disabled binding does not match the "
            "visual disabled state. Both must read "
            "(state.adding || !state.addToQuoteEnabled).",
        )
