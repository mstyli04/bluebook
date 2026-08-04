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
# Kept as descriptive statistics of the observed range, and used to anchor
# the FIRST forecast year. They are explicitly NOT a bound on the terminal
# year: all three historical years sit inside the distribution-centre build
# programme, so [HIST_CAPEX_LOW, HIST_CAPEX_HIGH] is an expansion-phase
# range, and constraining a steady-state assumption to it assumes the
# expansion never ends. See BASE.capex_pct_revenue below.
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
    # 13.27%, also HIST_CAPEX_HIGH), tapering to 7.00% by FY2030. The taper
    # IS the story: the Derby/Kettering/Balliol Park distribution-centre
    # programme that drove HIST_CAPEX_PCT_REVENUE up across FY2023-25 (from
    # HIST_CAPEX_LOW, 10.95%, to HIST_CAPEX_HIGH, 13.27%) is completing, so
    # capex intensity falls back to the level that merely sustains the
    # estate. It is a programme finishing, not a permanent step-down in
    # investment.
    #
    # The terminal figure is the one that matters, because it is the ratio
    # FCF gets capitalised on in perpetuity, and it is derived rather than
    # picked. In steady state with revenue growth g and depreciation rate d,
    # a capex ratio c holds PP&E/revenue at
    #     p = c * (1 + g) / (g + d)
    # Inverting at the FY2025 actual PP&E/revenue (832.1 / 2151.2 = 38.7%),
    # g = 4.5% terminal growth and d = ppe_depreciation_rate (14.23%):
    #     c = 0.387 * (0.045 + 0.1423) / 1.045 = 6.94%, i.e. ~7.0%
    # So 7.0% is exactly the capex intensity that keeps the asset base a
    # constant share of sales. Holding capex at the previous 11.00% instead
    # would drive PP&E/revenue to 61%+ in perpetuity — a business quietly
    # assumed to keep getting more capital-intensive forever, with no
    # revenue benefit modelled for it.
    #
    # This REVERSES the earlier ruling that terminal capex must stay inside
    # [HIST_CAPEX_LOW, HIST_CAPEX_HIGH]. That ruling was wrong twice over.
    # Its stated justification — that ending below HIST_CAPEX_LOW "would
    # understate terminal value" — has the sign backwards: lower capex means
    # higher free cash flow and therefore a HIGHER terminal value, so the
    # old constraint was inflating capex against the model's own interest,
    # not guarding against it. And the bound itself was never valid: all
    # three historical years sit inside the DC build programme, so the
    # historical range is an expansion-phase range. Bounding a terminal
    # steady-state assumption by it assumes the expansion never ends.
    capex_pct_revenue=(0.1327, 0.1200, 0.1040, 0.0870, 0.0700),

    # Year 1 anchored (rounded) to HIST_ROU_ADDITIONS_PCT_REVENUE[-1]
    # (FY2025 actual, 3.48%). HIST_ROU_ADDITIONS_PCT_REVENUE was volatile
    # across FY2023-25 (3.89% / 7.14% / 3.48% — lumpy lease signings), so
    # the path is held at the recent level rather than extrapolated, easing
    # to a 3.40% terminal as the shop estate matures and net new openings
    # slow: the same story the capex taper above tells, on the leased half
    # of the estate.
    #
    # Unlike terminal capex, 3.40% is NOT the hold-flat level. Applying the
    # same steady-state formula with d = rou_depreciation_rate (17.61%) and
    # g = 4.5%, holding ROU/revenue at the FY2025 actual (413.0 / 2151.2 =
    # 19.2%) would need 4.06%. At 3.40% the ROU book instead drifts down to
    # ~16.1% of revenue by the terminal year. That is deliberate — a
    # maturing estate signs proportionally fewer new leases, and it is the
    # conservative direction for the lease liability — but it is a
    # judgement, not a derivation, and is stated as such.
    rou_additions_pct_revenue=(0.035, 0.035, 0.035, 0.034, 0.034),

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

# What the capex paths must satisfy is covered by
# test_terminal_capex_holds_ppe_to_revenue_near_the_last_actual and
# test_capex_paths_are_ordered_bull_above_base_above_bear in
# tests/test_assumptions.py, not by asserts here — see that file for why.


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
    of the base path, or an explicit tuple supplied by the caller. Both
    Bear and Bull now use a uniform delta; the explicit-tuple path is kept
    because the scenario capex paths are the assumption most likely to need
    a bespoke shape later, and because it costs nothing.
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


# The rule that floored Bear's capex at HIST_CAPEX_LOW is void. Its premise
# was that a terminal capex ratio below the historical low "mechanically
# inflates terminal FCF" and so understates the stress — the same
# expansion-phase fallacy corrected in BASE.capex_pct_revenue above. Bear
# and Bull are now both plain uniform shifts off the Base path, and each
# terminal level is checked against the same steady-state test Base is.

SCENARIOS = {
    # Consumer-slowdown / cost-inflation case: growth decelerates further,
    # gross margin compresses under input-cost pressure, opex ratio worsens
    # (less operating leverage), capex intensity runs 100bp below Base in
    # every year, and the exit multiple de-rates.
    #
    # The -100bp capex shift is not just "Base, but less". Bear's terminal
    # revenue growth is 1.5% against Base's 4.5%, and a slower-growing
    # estate needs less investment to sustain itself: the steady-state
    # formula in BASE.capex_pct_revenue at g = 1.5% gives
    #     0.387 * (0.015 + 0.1423) / 1.015 = 6.00%
    # which is precisely Base's 7.00% terminal less the 100bp shift. So
    # Bear's terminal capex holds PP&E/revenue at the same FY2025 38.7% that
    # Base's does; the two scenarios differ in growth and margin, not in how
    # capital-intensive the business is assumed to become. Capex being lower
    # in the bear case than the base case is what a genuine demand slowdown
    # looks like, and the resulting FCF relief is real, not a modelling
    # artefact to be suppressed.
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
    # operating leverage, capex intensity runs 100bp above Base in every
    # year (funding faster growth than Base must cost more, not less), and
    # the exit multiple re-rates up.
    #
    # By the same steady-state arithmetic, Bull's 7.0% terminal growth would
    # need 0.387 * (0.07 + 0.1423) / 1.07 = 7.68% to hold PP&E/revenue flat,
    # so the uniform +100bp (8.00%) sits ~30bp above the hold-flat level and
    # lets the asset base grow a little faster than sales — to 40.3% of
    # revenue against the FY2025 38.7%. That is the intended reading of a
    # bull case: the estate is being built out ahead of the demand it is
    # betting on, and the model pays for it.
    "Bull": _scenario(
        BASE,
        growth_delta=0.025,
        margin_delta=0.015,
        opex_delta=-0.010,
        capex_delta=0.010,
        exit_ev_ebitda=11.5,
    ),
}
