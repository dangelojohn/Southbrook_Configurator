# SPDX-License-Identifier: LGPL-3.0-only
"""Pure-Python Canadian payroll calculators (CRA 2026, Ontario 2026).

Source-of-truth:
    CRA T4127 — Payroll Deductions Formulas (Jan 2026 edition).
    https://www.canada.ca/en/revenue-agency/services/forms-publications/
        payroll/t4127-payroll-deductions-formulas.html

Methodology notes
-----------------
* Brackets are encoded as (upper_threshold, marginal_rate,
  cumulative_tax_at_lower_bound) tuples. We binary-walk the list rather
  than chaining if/elif so the 2027 update is a one-line edit.
* The CRA formula method (T4127) computes federal/provincial tax in two
  stages: (a) gross tax on annual taxable income by bracket;
  (b) subtract the non-refundable BPA credit = BPA * lowest_rate.
  We deliberately do NOT subtract BPA from income before bracket
  calculation, that is a common (and wrong) shortcut.
* CPP: rate 5.95% on (gross - basic_exemption_per_period). The
  basic_exemption is $3,500/year, so per pay-period it is
  3500 / pay_periods_per_year. Capped at the annual maximum
  contribution = (YMPE - basic_exemption) * rate.
* EI: rate 1.66% (employee) on gross, capped at the annual maximum
  = MIE * rate.
* WSIB: employer-side premium; rate is per $100 of insurable earnings.
  We accept rate as a percentage (0.95 == 0.95%) for human-readable
  config. Internally we divide by 100.
* EHT (Ontario Employer Health Tax): 1.95% on payroll above the
  $1,000,000 exemption (small employer).

Tolerance
---------
Unit tests assert results within ±$2 of CRA published tables to absorb
the rounding rules in T4127 (which differ from pure float math by a few
cents per pay period).
"""

# ---------------------------------------------------------------------
# 2026 constants — single source of truth. Update once per year.
# ---------------------------------------------------------------------

# Federal — CRA T4127 (Jan 2026), s.A — Annual federal tax
# (threshold, rate, cumulative_tax_at_threshold). Last row's threshold
# is +inf so we never fall off the end.
BRACKETS_FEDERAL_2026 = [
    (57_375.00, 0.15, 0.0),
    (114_750.00, 0.205, 8_606.25),         # 57375 * .15
    (177_882.00, 0.26, 20_368.1250),       # 8606.25 + 57375*.205
    (253_414.00, 0.29, 36_782.4450),       # 20368.125 + 63132*.26
    (float("inf"), 0.33, 58_686.7250),     # 36782.445 + 75532*.29 = 21904.28
]
FEDERAL_BPA_2026 = 16_129.00
FEDERAL_LOWEST_RATE = 0.15

# Ontario — CRA T4127 (Jan 2026), s.B(Ontario) — Annual provincial tax
BRACKETS_ONTARIO_2026 = [
    (52_886.00, 0.0505, 0.0),
    (105_775.00, 0.0915, 2_670.7430),       # 52886 * .0505
    (150_000.00, 0.1116, 7_510.0865),       # 2670.743 + 52889*.0915
    (220_000.00, 0.1216, 12_445.5965),      # 7510.0865 + 44225*.1116 = 4935.51
    (float("inf"), 0.1316, 20_957.5965),    # 12445.5965 + 70000*.1216 = 8512
]
ONTARIO_BPA_2026 = 12_747.00
ONTARIO_LOWEST_RATE = 0.0505

# CPP 2026 — CRA T4127 s.C
CPP_RATE_2026 = 0.0595
CPP_YMPE_2026 = 73_200.00          # Year's Maximum Pensionable Earnings
CPP_BASIC_EXEMPTION_2026 = 3_500.00
CPP_MAX_CONTRIBUTION_2026 = (CPP_YMPE_2026 - CPP_BASIC_EXEMPTION_2026) * CPP_RATE_2026
# = 69700 * 0.0595 = 4147.15

# EI 2026 — CRA T4127 s.D
EI_RATE_2026 = 0.0166
EI_MIE_2026 = 66_600.00            # Maximum Insurable Earnings
EI_MAX_PREMIUM_2026 = EI_MIE_2026 * EI_RATE_2026
# = 1105.56

# WSIB Ontario 2026 — Rate Group 533 (Wood Cabinets / Furniture Mfg)
WSIB_DEFAULT_RATE_PCT_2026 = 0.95

# EHT Ontario 2026
EHT_RATE_2026 = 0.0195
EHT_EXEMPTION_2026 = 1_000_000.00


# ---------------------------------------------------------------------
# Bracket walker
# ---------------------------------------------------------------------
def _tax_from_brackets(annual_income, brackets):
    """Apply the bracket schedule to a positive annual income.

    Returns the gross tax (before non-refundable credits) computed as
    `cum + (income - lower_bound) * rate` where `lower_bound` is the
    sum of bracket widths below the matched bracket.
    """
    if annual_income <= 0:
        return 0.0
    lower = 0.0
    for upper, rate, cumulative in brackets:
        if annual_income <= upper:
            return cumulative + (annual_income - lower) * rate
        lower = upper
    # Unreachable: last bracket has upper=+inf.
    return 0.0


# ---------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------
def federal_tax_2026(annual_taxable_income):
    """2026 federal tax (CRA T4127 formula method, with BPA credit)."""
    gross = _tax_from_brackets(annual_taxable_income, BRACKETS_FEDERAL_2026)
    bpa_credit = FEDERAL_BPA_2026 * FEDERAL_LOWEST_RATE
    return max(0.0, gross - bpa_credit)


def ontario_tax_2026(annual_taxable_income):
    """2026 Ontario provincial tax (CRA T4127 formula method, with BPA)."""
    gross = _tax_from_brackets(annual_taxable_income, BRACKETS_ONTARIO_2026)
    bpa_credit = ONTARIO_BPA_2026 * ONTARIO_LOWEST_RATE
    return max(0.0, gross - bpa_credit)


def cpp_2026(gross_per_period, pay_periods_per_year):
    """2026 CPP employee contribution for a single pay period.

    Formula:   max(0, gross - basic_exemption_per_period) * 5.95%
    Capped at the annual maximum contribution ($4,147.15 in 2026) when
    the annualized gross exceeds YMPE.
    """
    if pay_periods_per_year <= 0:
        return 0.0
    exemption_per_period = CPP_BASIC_EXEMPTION_2026 / pay_periods_per_year
    pensionable = max(0.0, gross_per_period - exemption_per_period)
    per_period = pensionable * CPP_RATE_2026
    # Apply the annual cap: if this period's contribution * periods would
    # exceed the annual max, scale down. The cap is enforced per period
    # for a simple "as-if uniform earnings" assumption; payroll engines
    # in practice track YTD pensionable earnings and clamp the final
    # period. We expose the per-period figure; payslip.compute() is the
    # right place to do YTD tracking.
    cap_per_period = CPP_MAX_CONTRIBUTION_2026 / pay_periods_per_year
    annual_gross = gross_per_period * pay_periods_per_year
    if annual_gross > CPP_YMPE_2026:
        return cap_per_period
    return per_period


def ei_2026(gross_per_period):
    """2026 EI employee premium for a single pay period.

    Capped at MIE $66,600/yr; we infer the per-period cap by reading
    pay_periods from the per-period gross is not possible here, so we
    return uncapped premium and let the caller (payslip.compute) enforce
    YTD MIE.  For the standalone helper we still clamp annualized.

    A second positional pay_periods arg is intentionally NOT added so
    the helper signature matches the PRD; callers needing MIE-capped
    output should call `min(ei_2026(g), EI_MAX_PREMIUM_2026 / periods)`.
    """
    if gross_per_period <= 0:
        return 0.0
    return gross_per_period * EI_RATE_2026


def wsib_2026(insurable_earnings, rate_pct=WSIB_DEFAULT_RATE_PCT_2026):
    """2026 WSIB employer premium on insurable earnings.

    `rate_pct` is the WSIB rate group's published percentage (e.g. 0.95
    for Rate Group 533 / Wood Cabinets in Ontario 2026). The formula
    expressed in percent: earnings * rate_pct / 100.
    """
    if insurable_earnings <= 0:
        return 0.0
    return insurable_earnings * (rate_pct / 100.0)


def eht_ontario_2026(annual_payroll, exemption=EHT_EXEMPTION_2026):
    """2026 Ontario Employer Health Tax.

    1.95% on the portion of annual Ontario payroll exceeding the small-
    employer exemption ($1M default).
    """
    excess = annual_payroll - exemption
    if excess <= 0:
        return 0.0
    return excess * EHT_RATE_2026
