# SPDX-License-Identifier: LGPL-3.0-only
"""shared/southbrook_dims.py <-> shared/southbrook_dims.js parity gate.

Static parser: reads the eight geometric constants out of each file with
regex and asserts byte-identical values. Catches the most likely drift
mode — someone updates a Python constant and forgets to update the JS
counterpart (or vice versa) — without needing Node.js inside the Odoo
container.

A future iteration runs both implementations against canonical shapes
via a Node subprocess for formula-level parity (Node 26.3 is on the
host but not in sami-odoo); this test covers the constants which is
where every numerical drift originates.
"""
import re
from pathlib import Path

from odoo.tests.common import TransactionCase, tagged


# /srv/shared on PYTHONPATH; .js lives next to .py on the same mount.
SHARED_DIR = Path("/srv/shared")

CONSTANT_NAMES = (
    "BOX_TH", "BACK_TH", "RABBET", "DOOR_TH",
    "DOOR_REVEAL", "SHELF_TOL", "SHELF_VENT_GAP", "TOEKICK_H",
)


def _extract_python_constants(source: str) -> dict:
    """Pull `NAME: float = NUMBER` style declarations out of southbrook_dims.py."""
    out = {}
    for name in CONSTANT_NAMES:
        m = re.search(
            rf"^{re.escape(name)}\s*(?::\s*float\s*)?=\s*([0-9.]+)\b",
            source, re.MULTILINE,
        )
        if m:
            out[name] = float(m.group(1))
    return out


def _extract_js_constants(source: str) -> dict:
    """Pull `export const NAME = NUMBER;` declarations out of southbrook_dims.js."""
    out = {}
    for name in CONSTANT_NAMES:
        m = re.search(
            rf"^export\s+const\s+{re.escape(name)}\s*=\s*([0-9.]+)\s*;",
            source, re.MULTILINE,
        )
        if m:
            out[name] = float(m.group(1))
    return out


@tagged("post_install", "-at_install", "southbrook", "g1", "dims_parity")
class TestDimsJsParity(TransactionCase):
    """Constants-only parity between the .py and .js sources of truth."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        py_path = SHARED_DIR / "southbrook_dims.py"
        js_path = SHARED_DIR / "southbrook_dims.js"
        if not py_path.exists() or not js_path.exists():
            cls.skipTest_reason = (
                f"shared/southbrook_dims.{{py,js}} not mounted at {SHARED_DIR}"
            )
            cls._py_consts = cls._js_consts = {}
            return
        cls._py_consts = _extract_python_constants(py_path.read_text())
        cls._js_consts = _extract_js_constants(js_path.read_text())

    def test_all_eight_constants_present_in_both_files(self):
        for name in CONSTANT_NAMES:
            self.assertIn(name, self._py_consts,
                          f"{name} missing from southbrook_dims.py")
            self.assertIn(name, self._js_consts,
                          f"{name} missing from southbrook_dims.js")

    def test_constants_byte_identical(self):
        for name in CONSTANT_NAMES:
            self.assertEqual(
                self._py_consts.get(name), self._js_consts.get(name),
                f"{name} drift: py={self._py_consts.get(name)} "
                f"js={self._js_consts.get(name)}",
            )
