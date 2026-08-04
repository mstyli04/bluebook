"""Lease schedule: right-of-use (ROU) asset and lease liability roll-forwards.

Pure function of opening ROU asset, opening lease liability, revenue and the
lease drivers. Does not import the other schedule modules (working_capital,
fixed_assets) — each schedule is independent and gets wired together
downstream in the linked three-statement model.

Note: ``drivers.rou_depreciation_rate`` is calibrated against
``depreciation_rou`` in the historicals, which includes that year's net ROU
impairment charge (see ``inputs/greggs.py`` module docstring). The
depreciation this schedule produces therefore also represents
depreciation-plus-impairment, not textbook straight-line depreciation alone.
This is a deliberate upstream ruling, not something to correct here.

--------------------------------------------------------------------------
Implied average lease term — derivation
--------------------------------------------------------------------------
The brief sketches lease principal repayment as:

    principal_paid = opening_liability / implied_term_years + additions * 0.1

with `implied_term_years` to be sourced from the lease liability maturity
table in the filings rather than assumed. That table is disclosed in Note 11
"Leases" of the FY2025 Annual Report (FY2025 AR p.154), which gives the
*undiscounted* contractual lease cash flows by time band:

    Less than one year        79.1
    One to two years          75.1
    Two to three years        66.9
    Three to four years       59.2
    Four to five years        51.8
    Five to ten years        171.0
    Ten to twenty years       65.0
    More than twenty years    14.2
    Total undiscounted       582.3

(all £m, FY2025 column; FY2025 AR p.154, Note 11).

Rather than eyeballing a maturity band, the implied average remaining lease
term is derived as:

    implied_term_years = total undiscounted lease cash flows
                          / undiscounted cash flows due within one year

This is a "total over near-term run-rate" ratio, not a true weighted-average
life (WAL) — a true WAL timing-weights every band by its midpoint and would
land near 5.8 years here, dragged down by the very wide 5-10yr and 10-20yr
bands. The ratio used instead assumes the undiscounted repayment stream
stays level at the near-term run-rate, in which case it is exactly the
number of years it would take to run the book off. It uses only figures
printed on the same table, with no invented number:

    IMPLIED_LEASE_TERM_YEARS = 582.3 / 79.1 ≈ 7.36 years

This was cross-checked against the brief's own sketch formula and the
`lease_principal_paid` actually reported in `inputs/greggs.py` (Sourced,
each with its own filing page), which this module does not otherwise use:

    FY2025: opening_liability (FY2024 closing) = 415.1, additions = 74.8
        415.1 / 7.36 + 74.8 * 0.1 = 56.4 + 7.5 = 63.9
        vs. actual FY2025 lease_principal_paid = 63.3  (FY2025 AR p.132)
    FY2024: opening_liability (FY2023 closing) = 319.6, additions = 143.8
        319.6 / 7.36 + 143.8 * 0.1 = 43.4 + 14.4 = 57.8
        vs. actual FY2024 lease_principal_paid = 56.7  (FY2024 AR p.132)

Both come out within ~2% of the actual reported cash principal repayment,
which is strong evidence the derived term is the right order of magnitude
and that the brief's sketched formula (kept as-is below) is a reasonable
model of principal repayment, not just a plausible-looking guess.

--------------------------------------------------------------------------
Additions coefficient (the "* 0.1" in the sketch) — derivation
--------------------------------------------------------------------------
The brief's sketch left `additions * 0.1` as a bare literal alongside the
named, cited `implied_term_years`. It is promoted below to
`LEASE_ADDITIONS_PRINCIPAL_RATE`, an empirical fit rather than a
Greggs-disclosed figure: it approximates the extra partial-year principal
amortisation contributed by leases signed *during* the year (a full year's
`additions / implied_term_years` would overstate their pay-down, since a
lease added mid-year has only had part of a year to amortise).

Fixing `IMPLIED_LEASE_TERM_YEARS` at the value derived above, the two
historical years with both an opening liability and a reported
`lease_principal_paid` in `inputs/greggs.py` (FY2024 and FY2025) give two
equations in one remaining unknown, k:

    opening_liability / T + additions * k = lease_principal_paid

    FY2024: 319.6 / 7.36 + 143.8 * k = 56.7  ->  k ≈ 0.093
    FY2025: 415.1 / 7.36 +  74.8 * k = 63.3  ->  k ≈ 0.092

Solving the two simultaneously (rather than picking one) for the
least-squares-consistent (T, k) pair gives T ≈ 7.361 years and k ≈ 0.0924 —
the T that falls out of this joint solve lands within 0.01 of the
maturity-table-derived `IMPLIED_LEASE_TERM_YEARS` above, which is
independent corroboration of that figure from a completely different
source (cash principal paid vs. the undiscounted maturity schedule).
`LEASE_ADDITIONS_PRINCIPAL_RATE` is set to the resulting k ≈ 0.0924.
"""

from __future__ import annotations

from dataclasses import dataclass

from bluebook.assumptions import Drivers

# See "Implied average lease term — derivation" above.
# Source: FY2025 AR p.154 (Note 11, "Leases" — remaining maturities of lease
# liabilities, gross and undiscounted, FY2025 column).
GREGGS_LEASE_MATURITY_TOTAL_UNDISCOUNTED = 582.3  # FY2025 AR p.154, Note 11
GREGGS_LEASE_MATURITY_LESS_THAN_1YR = 79.1  # FY2025 AR p.154, Note 11
IMPLIED_LEASE_TERM_YEARS = (
    GREGGS_LEASE_MATURITY_TOTAL_UNDISCOUNTED / GREGGS_LEASE_MATURITY_LESS_THAN_1YR
)  # ~7.36 years

# See "Additions coefficient" derivation above. Empirical fit, not a
# Greggs-disclosed figure: solved jointly with IMPLIED_LEASE_TERM_YEARS
# against the two years of inputs/greggs.py that carry both an opening
# lease liability and an actual reported lease_principal_paid (FY2024 and
# FY2025). Approximates partial-year principal amortisation on in-year
# lease additions.
LEASE_ADDITIONS_PRINCIPAL_RATE = 0.0924


@dataclass(frozen=True)
class Leases:
    additions: list[float]
    depreciation: list[float]
    closing_rou: list[float]
    interest: list[float]
    principal_paid: list[float]
    closing_liability: list[float]


def leases(
    opening_rou: float,
    opening_liability: float,
    revenue: list[float],
    drivers: Drivers,
) -> Leases:
    additions: list[float] = []
    depreciation: list[float] = []
    closing_rou: list[float] = []
    interest: list[float] = []
    principal_paid: list[float] = []
    closing_liability: list[float] = []

    rou = opening_rou
    liability = opening_liability
    for year_revenue, additions_pct in zip(revenue, drivers.rou_additions_pct_revenue):
        year_additions = year_revenue * additions_pct
        year_depreciation = rou * drivers.rou_depreciation_rate
        rou = rou + year_additions - year_depreciation

        # Interest is computed and returned below (Task 8 needs it for the
        # P&L finance cost line), but it does NOT capitalise into the
        # liability balance. Under IFRS 16 the interest accrued on the
        # lease liability and the interest paid in cash are the same
        # figure in the same period (Greggs' FY2025 cash flow statement,
        # p.132, shows "Interest paid on lease liabilities" and
        # "Repayment of principal on lease liabilities" as separate cash
        # lines), so they net to zero in the liability roll-forward. Adding
        # year_interest here without an offsetting cash reduction
        # double-counts it and drives the ROU-to-liability gap far outside
        # its historical -7% to -9% band over a multi-year forecast (see
        # test_rou_asset_and_liability_stay_within_historical_band below).
        year_interest = liability * drivers.cost_of_debt
        year_principal_paid = (
            liability / IMPLIED_LEASE_TERM_YEARS + year_additions * LEASE_ADDITIONS_PRINCIPAL_RATE
        )
        liability = liability + year_additions - year_principal_paid

        additions.append(year_additions)
        depreciation.append(year_depreciation)
        closing_rou.append(rou)
        interest.append(year_interest)
        principal_paid.append(year_principal_paid)
        closing_liability.append(liability)

    return Leases(additions, depreciation, closing_rou, interest, principal_paid, closing_liability)
