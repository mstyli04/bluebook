"""Forecast driver assumptions and bull/base/bear scenarios for the Greggs model.

Every operating driver below is anchored to a ratio computed from
``GREGGS_HISTORICALS`` (see ``src/bluebook/inputs/greggs.py``), not to a
round-number guess. The ``HIST_*`` constants defined below are computed from
that data at import time — the driver comments reference those names rather
than restating the historical numbers as prose, precisely so a comment
cannot silently drift out of sync with the data it describes (three
consecutive review rounds each caught exactly that kind of drift: a stated
delta, a stated position within a range, and a stated count of years, all
wrong in ways nothing but a human re-check would catch). Where a comment
still states a number for readability, it is checked against the ``HIST_*``
constant it is describing.

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

from bluebook.inputs.greggs import GREGGS_HISTORICALS

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
# Historical ratios, derived from GREGGS_HISTORICALS — computed here, not
# hardcoded, so they can never go stale relative to the underlying data.
# Index order matches GREGGS_HISTORICALS: [FY2023, FY2024, FY2025]. The
# *_RATE / *_GROWTH pairs below have only 2 entries (FY23->24, FY24->25),
# since each needs an opening-year reference.
# ---------------------------------------------------------------------------


def _pbt(year) -> float:
    """Profit before tax for one HistoricalYear, £m."""
    ebit = (
        year.revenue.value
        - year.cost_of_sales.value
        - year.operating_costs.value
        - (year.depreciation_ppe.value + year.depreciation_rou.value + year.amortisation.value)
    )
    return ebit - year.finance_costs.value + year.finance_income.value


HIST_GROSS_MARGIN = tuple(
    (y.revenue.value - y.cost_of_sales.value) / y.revenue.value for y in GREGGS_HISTORICALS
)
HIST_OPEX_PCT_REVENUE = tuple(
    y.operating_costs.value / y.revenue.value for y in GREGGS_HISTORICALS
)
HIST_EFFECTIVE_TAX_RATE = tuple(y.tax_expense.value / _pbt(y) for y in GREGGS_HISTORICALS)
HIST_NET_INCOME = tuple(_pbt(y) - y.tax_expense.value for y in GREGGS_HISTORICALS)
HIST_DIVIDEND_PAYOUT = tuple(
    y.dividends_paid.value / ni for y, ni in zip(GREGGS_HISTORICALS, HIST_NET_INCOME)
)
HIST_CAPEX_PCT_REVENUE = tuple(y.capex.value / y.revenue.value for y in GREGGS_HISTORICALS)
HIST_CAPEX_LOW = min(HIST_CAPEX_PCT_REVENUE)
HIST_CAPEX_HIGH = max(HIST_CAPEX_PCT_REVENUE)
HIST_ROU_ADDITIONS_PCT_REVENUE = tuple(
    y.rou_additions.value / y.revenue.value for y in GREGGS_HISTORICALS
)
HIST_INVENTORY_DAYS = tuple(
    y.inventories.value / y.cost_of_sales.value * 365 for y in GREGGS_HISTORICALS
)
HIST_RECEIVABLE_DAYS = tuple(
    y.trade_receivables.value / y.revenue.value * 365 for y in GREGGS_HISTORICALS
)
HIST_PAYABLE_DAYS = tuple(
    y.trade_payables.value / y.cost_of_sales.value * 365 for y in GREGGS_HISTORICALS
)
HIST_REVENUE_GROWTH = tuple(
    (b.revenue.value - a.revenue.value) / a.revenue.value
    for a, b in zip(GREGGS_HISTORICALS[:-1], GREGGS_HISTORICALS[1:])
)
HIST_PPE_DEPRECIATION_RATE = tuple(
    b.depreciation_ppe.value / a.ppe.value
    for a, b in zip(GREGGS_HISTORICALS[:-1], GREGGS_HISTORICALS[1:])
)
HIST_ROU_DEPRECIATION_RATE = tuple(
    b.depreciation_rou.value / a.rou_assets.value
    for a, b in zip(GREGGS_HISTORICALS[:-1], GREGGS_HISTORICALS[1:])
)


BASE = Drivers(
    # Decelerating from HIST_REVENUE_GROWTH[-1] (FY2024->FY2025 actual,
    # +6.79%), itself down from HIST_REVENUE_GROWTH[0] (FY2023->FY2024,
    # +11.32%), toward a mid-single-digit long-run rate as the shop estate
    # matures and like-for-like growth normalises.
    revenue_growth=(0.06, 0.055, 0.05, 0.045, 0.045),

    # Year 1 anchored exactly to HIST_GROSS_MARGIN[-1] (FY2025 actual,
    # 61.46%). HIST_GROSS_MARGIN was roughly flat across FY2023-25 (within a
    # ~100bp band). Base case models a modest improvement to 62.00% by
    # FY2030 from supply-chain investment (new distribution centres)
    # reaching scale.
    gross_margin=(0.6146, 0.6165, 0.6180, 0.6190, 0.6200),

    # Year 1 anchored exactly to HIST_OPEX_PCT_REVENUE[-1] (FY2025 actual,
    # 45.13%). HIST_OPEX_PCT_REVENUE rose across FY2023-25, driven by wage
    # inflation and the front-loaded cost of new DC capacity coming online.
    # Base case assumes that capacity reaching utilisation partially offsets
    # the rising trend, easing to 44.30% by FY2030 rather than reversing it
    # entirely.
    opex_pct_revenue=(0.4513, 0.4480, 0.4460, 0.4445, 0.4430),

    # Year 1 anchored exactly to HIST_CAPEX_PCT_REVENUE[-1] (FY2025 actual,
    # 13.27%, also HIST_CAPEX_HIGH). HIST_CAPEX_PCT_REVENUE rose across
    # FY2023-25 through the Derby/Kettering/Balliol Park distribution-centre
    # build programme, from HIST_CAPEX_LOW (FY2023, 10.95%) to
    # HIST_CAPEX_HIGH. Base case tapers to 11.00% by FY2030 — just above
    # HIST_CAPEX_LOW, i.e. inside the historical range, not below it — as
    # that programme completes: the DC build moderates capex intensity but
    # doesn't eliminate the ongoing store/estate capex sitting under it.
    # This is the terminal-year driver that FCF gets capitalised on in
    # perpetuity, so ending below HIST_CAPEX_LOW (as an earlier draft did,
    # at 8.5%) would understate terminal value; owner ruling, see
    # task-4-report.md fix log.
    capex_pct_revenue=(0.1327, 0.1250, 0.1180, 0.1130, 0.1100),

    # Year 1 anchored (rounded) to HIST_ROU_ADDITIONS_PCT_REVENUE[-1]
    # (FY2025 actual, 3.48%). HIST_ROU_ADDITIONS_PCT_REVENUE was volatile
    # across FY2023-25 (lumpy lease signings), so held near the recent level
    # with a slight uptick consistent with Greggs' guided ~140-160 net new
    # shops/year.
    rou_additions_pct_revenue=(0.035, 0.037, 0.038, 0.040, 0.040),

    # Anchored to HIST_INVENTORY_DAYS[-1] (FY2025 actual, ~24.5 days),
    # broadly stable across FY2023-25; held flat.
    inventory_days=24.5,

    # Anchored to HIST_RECEIVABLE_DAYS[-1] (FY2025 actual, ~11.8 days), a
    # mild rising trend across FY2023-25; held flat.
    receivable_days=11.8,

    # Anchored to HIST_PAYABLE_DAYS[-1] (FY2025 actual, ~120 days), which
    # rose across FY2023-25 as buying power lengthened supplier terms; held
    # flat rather than extrapolating the trend further, since indefinite
    # extension of payable terms is not a realistic steady state.
    payable_days=120.0,

    # Anchored to HIST_PPE_DEPRECIATION_RATE[-1] (FY2025 depreciation_ppe /
    # FY2024 opening PP&E, 14.23%).
    ppe_depreciation_rate=0.1423,

    # Anchored to HIST_ROU_DEPRECIATION_RATE[-1] (FY2025 depreciation_rou /
    # FY2024 opening ROU assets, 17.61%).
    rou_depreciation_rate=0.1761,

    # UK statutory main corporation tax rate since April 2023.
    # HIST_EFFECTIVE_TAX_RATE was more volatile across FY2023-25 than this
    # single rate; the forward-run rate uses the statutory rate rather than
    # the trailing effective rate.
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
    # weight is used. This is financial debt only: FY2025 lease_liabilities
    # of £449.8m are deliberately excluded from the WACC debt base here (they
    # are financed at the lease discount rate embedded in finance_costs, not
    # at cost_of_debt), so target_debt_weight understates total balance-sheet
    # leverage including leases.
    target_debt_weight=0.10,

    # Long-run UK inflation/nominal-GDP proxy, consistent with the BoE's 2%
    # inflation target; stays below risk_free_rate + 2% as required.
    perpetuity_growth=0.02,
    # Judgement estimate for a UK quick-service bakery retail exit multiple;
    # not an independently sourced live market comp.
    exit_ev_ebitda=10.0,

    # Same basis as cost_of_debt - approximate rate on the drawn RCF.
    interest_rate_debt=0.055,
    # FY2023-25 actual cash balances fell from £195.3m to £70.8m (as the
    # capex and dividend programme stepped up, alongside a £25m RCF draw in
    # FY2025). The floor is set at £50m, below the FY2025 actual: it is a
    # hard minimum the forecast is tested against to flag when the business
    # would need external financing (e.g. a further revolver draw) to keep
    # operating, not a target buffer the model tries to hold cash above.
    minimum_cash=50.0,
    # Greggs' stated ordinary dividend policy targets ~50% of underlying
    # post-tax profit. HIST_DIVIDEND_PAYOUT was volatile across FY2023-25
    # (42.7% / 69.6% / 57.5%) due to special dividends, so the base case
    # uses the stated ordinary policy rate rather than the volatile trailing
    # actual.
    dividend_payout_ratio=0.50,
)

# Base's terminal capex staying within [HIST_CAPEX_LOW, HIST_CAPEX_HIGH] is
# covered by test_base_terminal_capex_within_historical_range in
# tests/test_assumptions.py, not by an assert here — see that file for why.


def _scenario(
    base: Drivers,
    *,
    growth_delta: float,
    margin_delta: float,
    opex_delta: float,
    exit_ev_ebitda: float,
    capex_delta: float | None = None,
    capex_pct_revenue: tuple[float, ...] | None = None,
) -> Drivers:
    """Derive a scenario by shifting operating drivers off the base case.

    capex_pct_revenue is either a uniform capex_delta applied to every year
    of the base path, or an explicit tuple supplied by the caller (used for
    Bear, whose capex path is a floored uniform shift — see the comment
    beside BEAR_CAPEX_PCT_REVENUE below).
    """
    if capex_pct_revenue is None:
        if capex_delta is None:
            raise ValueError("supply either capex_delta or capex_pct_revenue")
        capex_pct_revenue = tuple(c + capex_delta for c in base.capex_pct_revenue)
    return replace(
        base,
        revenue_growth=tuple(g + growth_delta for g in base.revenue_growth),
        gross_margin=tuple(m + margin_delta for m in base.gross_margin),
        opex_pct_revenue=tuple(o + opex_delta for o in base.opex_pct_revenue),
        capex_pct_revenue=capex_pct_revenue,
        exit_ev_ebitda=exit_ev_ebitda,
    )


# Bear capex path: what it plainly is — Base minus 100bp/year, eased until
# it reaches HIST_CAPEX_LOW, then held there. Not an independently derived
# path, just that rule applied and stated honestly:
#
# Applying capex_delta=-0.010 to every year of BASE.capex_pct_revenue
# uniformly gives (12.27%, 11.50%, 10.80%, 10.30%, 10.00%). Three of those
# five years — FY2028, FY2029 and FY2030 — fall below HIST_CAPEX_LOW
# (10.95%). A bear-case terminal capex ratio below the historical low
# mechanically inflates terminal FCF, which would partly undercut the
# stress this scenario is meant to depict — the same terminal-value
# reasoning that governs BASE's capex path above.
#
# So the first two years keep the uniform -100bp shift (12.27%, 11.50%: a
# slower store rollout under demand/cost pressure is a reasonable near-term
# stress read), and FY2028 onward is floored at HIST_CAPEX_LOW instead of
# continuing to taper down. The result is still below Base in every
# forecast year (tighter capex discipline than Base), just never below the
# level Greggs has actually run at historically.
#
# Bear capex never falling below HIST_CAPEX_LOW is covered by
# test_bear_capex_never_below_historical_low in tests/test_assumptions.py,
# not by an assert here — see that file for why.
BEAR_CAPEX_PCT_REVENUE = (0.1227, 0.1150, 0.1095, 0.1095, 0.1095)

SCENARIOS = {
    # Consumer-slowdown / cost-inflation case: growth decelerates further,
    # gross margin compresses under input-cost pressure, opex ratio worsens
    # (less operating leverage), capex intensity eases but is floored at
    # HIST_CAPEX_LOW rather than falling below it (see BEAR_CAPEX_PCT_REVENUE
    # above), and the exit multiple de-rates.
    "Bear": _scenario(
        BASE,
        growth_delta=-0.03,
        margin_delta=-0.015,
        opex_delta=0.010,
        capex_pct_revenue=BEAR_CAPEX_PCT_REVENUE,
        exit_ev_ebitda=8.5,
    ),
    "Base": BASE,
    # Continued strong footfall/expansion case: growth holds up better,
    # margin expands on scale/mix, opex ratio improves further with
    # operating leverage, capex intensity rises with a faster rollout (a
    # uniform +1.0pp over Base raises no floor/ceiling concern here, and
    # keeps Bull's capex path strictly above Base's at every year, which is
    # what funding faster growth than Base should imply), and the exit
    # multiple re-rates up.
    "Bull": _scenario(
        BASE,
        growth_delta=0.025,
        margin_delta=0.015,
        opex_delta=-0.010,
        capex_delta=0.010,
        exit_ev_ebitda=11.5,
    ),
}
