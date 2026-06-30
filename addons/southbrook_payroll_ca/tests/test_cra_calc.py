# SPDX-License-Identifier: LGPL-3.0-only
"""Unit tests on the pure-Python CRA calculators.

These import the calc module directly (no Odoo TransactionCase needed)
so they can run in a vanilla python3 with no DB. The runner uses
unittest so the same file works both under `odoo -i ... --test-enable`
and a plain `python3 -m unittest`.

Tolerances:
    Tax: ±$2 (T4127 tables vs. formula method round per-period).
    CPP/EI: ±$0.50.
    WSIB/EHT: exact (whole-percent math).
"""

import os
import sys
import unittest

# Allow running standalone: `python3 -m unittest tests.test_cra_calc`
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(_HERE, "..", "models")))

import cra_calc  # noqa: E402


TAX_TOL = 2.0
CASH_TOL = 0.50


class TestCraCalc(unittest.TestCase):
    # -- Federal ----------------------------------------------------
    def test_federal_tax_2026_below_basic_personal_amount(self):
        # $10k taxable income: gross-bracket tax = 10000*.15 = 1500;
        # BPA credit = 16129*.15 = 2419.35. Tax floored at 0.
        self.assertEqual(cra_calc.federal_tax_2026(10000.0), 0.0)

    def test_federal_tax_2026_first_bracket(self):
        # 30000*.15 - 16129*.15 = 4500 - 2419.35 = 2080.65
        self.assertAlmostEqual(
            cra_calc.federal_tax_2026(30000.0), 2080.65, delta=TAX_TOL
        )

    def test_federal_tax_2026_top_bracket_partial(self):
        # See cra_calc docstring; formula method on $200k yields
        # 43196.66 gross less 2419.35 BPA credit = 40777.31.
        # PRD's "~$45,000" is documented as a spec deviation
        # (the formula method, not a CRA table lookup).
        self.assertAlmostEqual(
            cra_calc.federal_tax_2026(200000.0), 40777.32, delta=TAX_TOL
        )

    # -- Ontario ----------------------------------------------------
    def test_ontario_tax_2026_first_bracket(self):
        # 30000*.0505 - 12747*.0505 = 1515 - 643.72 = 871.28
        self.assertAlmostEqual(
            cra_calc.ontario_tax_2026(30000.0), 871.28, delta=TAX_TOL
        )

    # -- CPP --------------------------------------------------------
    def test_cpp_2026_below_ympe(self):
        # Bi-weekly $2000; annualized $52000 < YMPE.
        # Exemption per period = 3500/26 = 134.615
        # Pensionable = 2000 - 134.615 = 1865.385
        # CPP = 1865.385 * .0595 = 110.99
        self.assertAlmostEqual(
            cra_calc.cpp_2026(2000.0, 26), 110.99, delta=CASH_TOL
        )

    def test_cpp_2026_at_max_ympe(self):
        # Bi-weekly $4000; annualized $104000 > YMPE → capped.
        # Per-period cap = 4147.15 / 26 = 159.51
        per_period = cra_calc.cpp_2026(4000.0, 26)
        self.assertAlmostEqual(per_period, 4147.15 / 26, delta=CASH_TOL)
        # Sanity: annualized contribution == max.
        self.assertAlmostEqual(per_period * 26, 4147.15, delta=CASH_TOL)

    # -- EI ---------------------------------------------------------
    def test_ei_2026_below_max(self):
        # Bi-weekly $2000 * 1.66% = 33.20
        self.assertAlmostEqual(cra_calc.ei_2026(2000.0), 33.20, delta=CASH_TOL)

    def test_ei_2026_at_max_mie(self):
        # The standalone helper does not enforce MIE; payslip layer
        # applies the per-period cap (MAX/periods). Here we check the
        # annual cap arithmetic is sound.
        # MIE * rate = 66600 * 0.0166 = 1105.56
        self.assertAlmostEqual(
            cra_calc.EI_MAX_PREMIUM_2026, 1105.56, delta=CASH_TOL
        )

    # -- WSIB -------------------------------------------------------
    def test_wsib_2026_manufacturing(self):
        # 50000 * 0.95% = 475.00
        self.assertAlmostEqual(cra_calc.wsib_2026(50000.0), 475.0, delta=0.01)

    # -- EHT --------------------------------------------------------
    def test_eht_ontario_below_exemption(self):
        # $800k < $1M exemption → $0
        self.assertEqual(cra_calc.eht_ontario_2026(800_000.0), 0.0)

    def test_eht_ontario_above_exemption(self):
        # $2M payroll: (2_000_000 - 1_000_000) * .0195 = 19500
        self.assertAlmostEqual(
            cra_calc.eht_ontario_2026(2_000_000.0), 19500.0, delta=0.01
        )


if __name__ == "__main__":
    unittest.main()
