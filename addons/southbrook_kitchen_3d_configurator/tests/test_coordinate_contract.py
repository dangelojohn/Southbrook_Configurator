# SPDX-License-Identifier: LGPL-3.0-only
"""Coordinate-contract compliance for the cabinet mesh builders.

Makes COORDINATE_CONTRACT.md ENFORCEABLE, not just documented: every builder
must consume all four placement fields (x/y/z_position_in + rotation_deg)
with no coordinate overloading. Implemented as a LIVING LEDGER so it is
useful today (mid-migration) and turns into a hard gate automatically:

  * a debt-free (migrated) builder MUST consume all four — hard-enforced;
  * a builder may omit ONLY the fields listed in its known migration debt;
  * dropping a field a builder currently uses (missing > debt) FAILS —
    catching regressions and any NEW coordinate reinterpretation;
  * if a builder quietly becomes compliant, its stale debt entry FAILS —
    forcing the ledger to shrink (auto-signals the renderer migrated it).

As the renderer coordinate-model unification migrates each builder, shrink
its _KNOWN_DEBT entry to set(); full enforcement then turns on for it.
"""
import os

from odoo.tests.common import TransactionCase

_REQUIRED = ("x_position_in", "y_position_in", "z_position_in", "rotation_deg")

# Fields each builder does NOT yet consume, pending the renderer coordinate-
# model unification (see COORDINATE_CONTRACT.md, "Known migration debt").
_KNOWN_DEBT = {
    "base_cabinet.esm.js":   {"y_position_in", "z_position_in", "rotation_deg"},
    "wall_cabinet.esm.js":   {"y_position_in", "rotation_deg"},   # z overloaded as height today
    "other_cabinets.esm.js": {"y_position_in", "rotation_deg"},
}


class TestCoordinateContractCompliance(TransactionCase):

    def _read(self, fname):
        path = os.path.join(os.path.dirname(__file__), "..", "static", "src",
                            "js", "canvas", fname)
        with open(path) as fh:
            return fh.read()

    def _missing(self, fname):
        src = self._read(fname)
        return {f for f in _REQUIRED if f not in src}

    def test_builders_conform_to_coordinate_contract(self):
        for fname, debt in _KNOWN_DEBT.items():
            missing = self._missing(fname)
            regressed = missing - debt
            self.assertEqual(
                regressed, set(),
                "%s dropped contract field(s) %s not in known debt — a "
                "coordinate regression (COORDINATE_CONTRACT.md)"
                % (fname, sorted(regressed)))
            if not debt:
                self.assertEqual(
                    missing, set(),
                    "%s is debt-free but omits %s" % (fname, sorted(missing)))

    def test_no_stale_debt_entries(self):
        """A builder that quietly became compliant leaves a stale debt entry.
        Fail so the ledger is shrunk (this is how the renderer migration
        auto-turns-on enforcement per builder)."""
        stale = []
        for fname, debt in _KNOWN_DEBT.items():
            now_used = debt - self._missing(fname)
            if now_used:
                stale.append((fname, sorted(now_used)))
        self.assertEqual(
            stale, [],
            "stale migration-debt entries — builder now consumes these; "
            "remove from _KNOWN_DEBT: %s" % stale)
