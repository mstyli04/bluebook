"""Forecast driver assumptions and bull/base/bear scenarios for the Greggs model.

Every operating driver below is anchored to a ratio computed from
``GREGGS_HISTORICALS`` (see ``src/bluebook/inputs/greggs.py``), not to a
round-number guess. The historical ratio each driver was anchored to is
written in the comment beside it, alongside the reason for any deliberate
drift away from that anchor across the five-year forecast or between
scenarios.

Two things worth knowing about the historicals this module reads:

* ``depreciation_ppe`` and ``depreciation_rou`` each include that year's net
  impairment charge on the relevant asset class (a deliberate modelling
  choice made upstream), so total D&A here runs ~£3.9-6.9m/year above the
  depreciation line shown in Greggs' published cash flow statement. The
  ratios below are calibrated against what this module actually holds.
* ``operating_costs`` is already net of D&A/amortisation/impairment (see the
  schema docstring), so ``gross_margin - opex_pct_revenue - da_pct_revenue``
  reproduces the reported EBIT margin.

Market-rate drivers (risk-free rate, equity risk premium, beta, cost of
debt) are not in any filing. Each is a defensible judgement estimate for a
UK-listed consumer/retail business, with its basis stated in the comment.
None of these four was pulled from a live data feed — treat them as
reasoned estimates, not sourced facts.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

FORECAST_YEARS = ["FY2026", "FY2027", "FY2028", "FY2029", "FY2030"]


@dataclass(frozen=True)
class Drivers:
    """Forecast assumptions. All rates are fractions, not percentages."""

    revenue_growth: tuple[float, ...]      # one per forecast year
    gross_margin: tuple[float, ...]        # gross profit / revenue
    opex_pct_revenue: tuple[float, ...]
    capex_pct_revenue: tuple[float, ...]
    rou_additions_pct_revenue: tuple[float, ...]
    inventory_days: float
    receivable_days: float
    payable_days: float
    ppe_depreciation_rate: float           # of opening PP&E
    rou_depreciation_rate: float           # of opening ROU assets
    tax_rate: float

    # WACC build
    risk_free_rate: float
    equity_risk_premium: float
    beta: float
    cost_of_debt: float
    target_debt_weight: float

    # Terminal value
    perpetuity_growth: float
    exit_ev_ebitda: float

    # Debt
    interest_rate_debt: float
    minimum_cash: float
    dividend_payout_ratio: float


# ---------------------------------------------------------------------------
# Historical ratios (computed from GREGGS_HISTORICALS), for reference:
#
#                        FY2023    FY2024    FY2025
#   gross_margin          60.74%    61.74%    61.46%
#   opex_pct_revenue      42.99%    44.14%    45.13%
#   da_pct_revenue         7.12%     7.20%     7.79%
#   ebit_margin           10.63%    10.40%     8.54%
#   effective tax rate    24.32%    24.77%    27.00%
#   inventory_days         25.1      26.1      24.5
#   receivable_days        10.9      11.3      11.8
#   payable_days          108.4     115.5     120.1
#   capex_pct_revenue     10.95%    11.96%    13.27%
#   rou_additions_pct_rev  3.88%     7.14%     3.48%
#   dividend payout ratio 42.7%     69.6%     57.5%
#
#   ppe_depreciation_rate (dep_ppe / opening PP&E): FY25 94.6 / FY24 664.7 = 14.23%
#   rou_depreciation_rate (dep_rou / opening ROU):  FY25 68.2 / FY24 387.2 = 17.61%
#
# Revenue growth: FY2023->FY2024 = +11.32%, FY2024->FY2025 = +6.79% (decelerating).
# ---------------------------------------------------------------------------

BASE = Drivers(
    # Decelerating from the FY2024->FY2025 actual of +6.79% (itself down from
    # +11.32% the year before) toward a mid-single-digit long-run rate as the
    # shop estate matures and like-for-like growth normalises.
    revenue_growth=(0.06, 0.055, 0.05, 0.045, 0.045),

    # Year 1 anchored exactly to the FY2025 actual (61.46%). FY2023-25 actual
    # was 60.7% / 61.7% / 61.5% - roughly flat within a ~100bp band. Base case
    # models a modest 70bp improvement over 5 years from supply-chain
    # investment (new distribution centres) reaching scale.
    gross_margin=(0.6146, 0.6165, 0.6180, 0.6190, 0.6200),

    # Year 1 anchored exactly to the FY2025 actual (45.13%). FY2023-25 actual
    # was rising (43.0% / 44.1% / 45.1%), driven by wage inflation and the
    # front-loaded cost of new DC capacity coming online. Base case assumes
    # that capacity reaching utilisation partially offsets the rising trend,
    # easing ~90bp over the forecast rather than reversing it entirely.
    opex_pct_revenue=(0.4513, 0.4480, 0.4460, 0.4445, 0.4430),

    # Year 1 anchored exactly to the FY2025 actual (13.27%). FY2023-25 actual
    # was rising (10.9% / 12.0% / 13.3%) through the Derby/Kettering/Balliol
    # Park distribution-centre build programme. Base case tapers back toward
    # the ~11% historical run-rate as that programme completes.
    capex_pct_revenue=(0.1327, 0.1200, 0.1000, 0.0900, 0.0850),

    # Year 1 anchored (rounded) to the FY2025 actual of 3.48%. FY2023-25
    # actual was volatile (3.9% / 7.1% / 3.5%, reflecting lumpy lease
    # signings), so held near the recent level with a slight uptick
    # consistent with Greggs' guided ~140-160 net new shops/year.
    rou_additions_pct_revenue=(0.035, 0.037, 0.038, 0.040, 0.040),

    # FY2025 actual = 24.5 days (FY2023 25.1, FY2024 26.1) - stable; anchored
    # to the latest year and held flat.
    inventory_days=24.5,

    # FY2025 actual = 11.8 days (FY2023 10.9, FY2024 11.3) - mild rising
    # trend; anchored to the latest year and held flat.
    receivable_days=11.8,

    # FY2025 actual = 120.1 days (FY2023 108.4, FY2024 115.5) - rising, as
    # buying power lengthens supplier terms. Anchored to the FY2025 level but
    # held flat rather than extrapolating the trend further, since indefinite
    # extension of payable terms is not a realistic steady state.
    payable_days=120.0,

    # FY2025 depreciation_ppe (94.6) / FY2024 opening PP&E (664.7) = 14.23%;
    # anchored exactly.
    ppe_depreciation_rate=0.1423,

    # FY2025 depreciation_rou (68.2) / FY2024 opening ROU assets (387.2) =
    # 17.61%; anchored exactly.
    rou_depreciation_rate=0.1761,

    # UK statutory main corporation tax rate since April 2023. FY2023-25
    # effective rates (tax_expense / PBT) were 24.3% / 24.8% / 27.0% - the
    # forward-run rate uses the statutory rate rather than the more volatile
    # trailing effective rate (divergence from the FY2025 actual is ~200bp).
    tax_rate=0.25,

    # --- WACC build: none of these four is in a filing; each is a judgement
    # estimate for a UK-listed consumer/retail business, not a sourced fact.
    # Approx. UK 10-year gilt yield in a representative current-rate
    # environment (gilts have broadly traded in a 3.75%-4.5% band through
    # 2024-2026); not fetched from a live feed.
    risk_free_rate=0.04,
    # UK equity risk premium, mid-point of standard estimate ranges (e.g.
    # Damodaran-style UK ERP estimates cluster around 5%-6%).
    equity_risk_premium=0.055,
    # Estimated levered equity beta for a UK defensive high-street
    # bakery/QSR retailer; judgement estimate in the 0.6-0.9 range typically
    # reported for a Greggs-like name, not pulled from a data provider.
    beta=0.75,
    # Estimated pre-tax cost of debt ~ risk_free_rate + ~150bp credit spread
    # for an investment-grade-quality UK retail borrower.
    cost_of_debt=0.055,
    # Greggs is very lightly geared - FY2025 borrowings were only £25m drawn
    # on its £100m RCF against £625.2m of book equity - so a low target
    # weight is used.
    target_debt_weight=0.10,

    # Long-run UK inflation/nominal-GDP proxy, consistent with the BoE's 2%
    # inflation target; stays below risk_free_rate + 2% as required.
    perpetuity_growth=0.02,
    # Judgement estimate for a UK quick-service bakery retail exit multiple;
    # not an independently sourced live market comp.
    exit_ev_ebitda=10.0,

    # Same basis as cost_of_debt - approximate rate on the drawn RCF.
    interest_rate_debt=0.055,
    # FY2023-25 actual cash balances were £195.3m / £125.3m / £70.8m
    # (falling as the capex and dividend programme stepped up). The minimum
    # cash floor is set below the FY2025 low as a conservative liquidity
    # buffer, so the model can flag if forecast cash needs external funding.
    minimum_cash=50.0,
    # Greggs' stated ordinary dividend policy targets ~50% of underlying
    # post-tax profit. FY2023-25 actual cash payout (dividends_paid / net
    # income) was 42.7% / 69.6% / 57.5% - volatile due to special dividends -
    # so the base case uses the stated ordinary policy rate rather than the
    # volatile trailing actual.
    dividend_payout_ratio=0.50,
)


def _scenario(
    base: Drivers,
    *,
    growth_delta: float,
    margin_delta: float,
    opex_delta: float,
    capex_delta: float,
    exit_ev_ebitda: float,
) -> Drivers:
    """Derive a scenario by shifting operating drivers off the base case."""
    return replace(
        base,
        revenue_growth=tuple(g + growth_delta for g in base.revenue_growth),
        gross_margin=tuple(m + margin_delta for m in base.gross_margin),
        opex_pct_revenue=tuple(o + opex_delta for o in base.opex_pct_revenue),
        capex_pct_revenue=tuple(c + capex_delta for c in base.capex_pct_revenue),
        exit_ev_ebitda=exit_ev_ebitda,
    )


SCENARIOS = {
    # Consumer-slowdown / cost-inflation case: growth decelerates further,
    # gross margin compresses under input-cost pressure, opex ratio worsens
    # (less operating leverage), capex intensity eases as store rollout
    # slows, and the exit multiple de-rates.
    "Bear": _scenario(
        BASE,
        growth_delta=-0.03,
        margin_delta=-0.015,
        opex_delta=0.010,
        capex_delta=-0.010,
        exit_ev_ebitda=8.5,
    ),
    "Base": BASE,
    # Continued strong footfall/expansion case: growth holds up better,
    # margin expands on scale/mix, opex ratio improves further with
    # operating leverage, capex intensity rises with a faster rollout, and
    # the exit multiple re-rates up.
    "Bull": _scenario(
        BASE,
        growth_delta=0.025,
        margin_delta=0.015,
        opex_delta=-0.010,
        capex_delta=0.010,
        exit_ev_ebitda=11.5,
    ),
}
