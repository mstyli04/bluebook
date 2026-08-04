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
def intangible_capex_share(historicals) -> float:
    """Share of total cash capex that is intangible additions, not PP&E.

    Lives here rather than in ``reference.py`` because the terminal capex
    driver below is derived from it: ``capex_pct_revenue`` is a TOTAL capex
    ratio, but only ``1 - this`` reaches PP&E, so the level that sustains
    PP&E must be grossed up by ``1 / (1 - intangible_capex_share)``. One
    definition, read by both the driver derivation and the model that
    consumes it, so the two cannot drift apart.

    Aggregated across every year that has a prior-year balance to roll off,
    rather than taken from the latest year alone: FY2025 on its own implies
    7.99% (22.8 / 285.4) against this aggregate's 6.38%, the year Greggs'
    intangible additions more than doubled (10.8 -> 22.8 implied, 10.9 ->
    22.1 as reported), and a terminal assumption should not inherit one
    year's spike.

    Implied additions = closing intangibles - opening intangibles +
    amortisation, because the schema carries only total capex. Reconciles to
    the PP&E/intangible split disclosed in the cash flow statements — FY2024
    implies 10.8 against 10.9 reported, FY2025 22.8 against 22.1 — the
    residual being disposals and reclassifications the balance movement
    cannot see.

    This is a two-year aggregate rather than the three-year one, because
    FY2023's intangible capex is not recoverable: implied additions need a
    prior-year balance and FY2022 is not in ``GREGGS_HISTORICALS``. The
    disclosed three-year split (41.6 / 724.4 = 5.74%) exists only in prose
    comments in ``inputs/greggs.py`` — ``capex`` is a single field — so it
    cannot be derived, and hardcoding it would put a figure here that no
    test could tie back to the filings. Owner ruling: derivation wins.
    Closing the 64bp gap needs a ``capex_intangible`` field in the schema.
    """
    pairs = list(zip(historicals[:-1], historicals[1:]))
    additions = sum(
        later.intangibles.value - earlier.intangibles.value + later.amortisation.value
        for earlier, later in pairs
    )
    total_capex = sum(later.capex.value for _, later in pairs)
    return additions / total_capex


def amortisation_rate(historicals) -> float:
    """Amortisation as a rate on opening intangibles, from the last actual.

    ``Drivers`` has no amortisation field and is frozen, so the rate is
    derived here alongside the other filing-derived ratios. Anchored on the
    most recent year exactly as ``ppe_depreciation_rate`` and
    ``rou_depreciation_rate`` are: FY2025 amortisation over FY2024 closing
    intangibles, 4.7 / 24.9 = 18.9%.
    """
    return historicals[-1].amortisation.value / historicals[-2].intangibles.value


HIST_INTANGIBLE_CAPEX_SHARE = intangible_capex_share(GREGGS_HISTORICALS)
HIST_AMORTISATION_RATE = amortisation_rate(GREGGS_HISTORICALS)
# Share of total capex that actually reaches the PP&E line, and therefore
# the factor the sustaining-capex derivation below has to gross up by.
HIST_PPE_CAPEX_SHARE = 1.0 - HIST_INTANGIBLE_CAPEX_SHARE

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
    # 13.27%, also HIST_CAPEX_HIGH), tapering to 7.41% by FY2030. The taper
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
    # capex reaching an asset base at a ratio c_ppe holds PP&E/revenue at
    #     p = c_ppe * (1 + g) / (g + d)
    # Inverting at the FY2025 actual PP&E/revenue (832.1 / 2151.2 = 38.68%),
    # g = 4.5% terminal growth and d = ppe_depreciation_rate (14.23%):
    #     c_ppe = 0.386807 * (0.045 + 0.1423) / 1.045 = 6.9329%
    #
    # But c_ppe is NOT the driver. capex_pct_revenue is a ratio of TOTAL
    # cash capex — PP&E plus intangible additions, the basis on which
    # inputs/greggs.py records `capex` — and reference.py routes only
    # HIST_PPE_CAPEX_SHARE (93.62%) of it into the fixed-asset schedule, the
    # rest going to intangibles. The sustaining requirement must therefore
    # be grossed up by 1 / HIST_PPE_CAPEX_SHARE:
    #     c = 6.9329% / 0.936158 = 7.4057%  ->  0.0741
    #
    # Both figures are named constants derived from GREGGS_HISTORICALS, not
    # literals, so the driver and the split cannot drift apart — see
    # intangible_capex_share() above and
    # test_terminal_capex_equals_its_own_grossed_up_sustaining_level, which
    # reproduces this whole derivation including the gross-up. A second
    # test, test_terminal_capex_holds_ppe_to_revenue_when_the_schedule_is_
    # iterated, checks the same claim WITHOUT the closed form, by running
    # fixed_assets() forward to convergence — because the 7.00% error below
    # survived a round of review inside a test that re-derived the very
    # formula it was meant to be auditing.
    #
    # An earlier round set this to 7.00%, which was the ungrossed c_ppe used
    # as if it were a total-capex ratio. That silently starved the PP&E line
    # of the intangible share and drove Base's true steady-state
    # PP&E/revenue to 36.56%, ~2.1pp below the anchor the derivation claimed
    # to hold (Bear 36.24%, Bull 37.75%, on the same error). It was
    # invisible because the covering test reproduced the same unsplit
    # formula.
    #
    # Holding capex at the pre-round-1 11.00% instead would drive
    # PP&E/revenue to 57%+ in perpetuity — a business quietly assumed to
    # keep getting more capital-intensive forever, with no revenue benefit
    # modelled for it.
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
    capex_pct_revenue=(0.1327, 0.1210, 0.1060, 0.0900, 0.0741),

    # Year 1 anchored (rounded) to HIST_ROU_ADDITIONS_PCT_REVENUE[-1]
    # (FY2025 actual, 3.48%), gliding to a 4.06% terminal.
    #
    # The terminal figure is derived on EXACTLY the same principle as
    # terminal capex above — the level that holds the asset base at its
    # FY2025 share of revenue — because Greggs runs one estate on two
    # balance sheet lines, and the owned half and the leased half should not
    # be governed by two different rules. Inverting p = c(1 + g)/(g + d)
    # with p = the FY2025 actual ROU/revenue (413.0 / 2151.2 = 19.20%),
    # d = rou_depreciation_rate (17.61%) and g = 4.5% terminal growth:
    #     c = 0.1920 * (0.045 + 0.1761) / 1.045 = 4.06%
    #
    # This REPLACES a 3.40% terminal that was a judgement rather than a
    # derivation. 3.40% implied ROU/revenue drifting down to ~16.1% — the
    # leased estate quietly shrinking relative to sales while the owned
    # estate was being held flat by construction, an asymmetry with no
    # stated reason behind it.
    #
    # Note the direction: 4.06% is ABOVE the FY2025 actual of 3.48%, so the
    # path glides up, not down. That is what the arithmetic says and it is
    # not an aggressive read — FY2025's lease signings were the low end of a
    # volatile run (HIST_ROU_ADDITIONS_PCT_REVENUE = 3.89% / 7.14% / 3.48%),
    # and 4.06% sits inside that observed range and below the three-year
    # aggregate of 4.84% (288.9 / 5975.2). Sustaining the current leased
    # estate needs slightly more lease signing than FY2025 alone delivered.
    rou_additions_pct_revenue=(0.0350, 0.0364, 0.0378, 0.0392, 0.0406),

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

# What the capex and ROU-addition paths must satisfy is covered by
# test_terminal_capex_holds_ppe_to_revenue_when_the_schedule_is_iterated,
# test_terminal_capex_equals_its_own_grossed_up_sustaining_level,
# test_terminal_rou_additions_hold_rou_to_revenue_near_the_last_actual and
# test_investment_paths_are_ordered_bull_above_base_above_bear in
# tests/test_assumptions.py, not by asserts here — see that file for why.


def _scenario(
    base: Drivers,
    *,
    growth_delta: float,
    margin_delta: float,
    opex_delta: float,
    exit_ev_ebitda: float,
    rou_delta: float,
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
        rou_additions_pct_revenue=tuple(
            r + rou_delta for r in base.rou_additions_pct_revenue
        ),
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
    # estate needs less investment to sustain itself. The shift is sized off
    # the same grossed-up derivation as Base: at Bear's 1.5% terminal
    # growth, sustaining PP&E/revenue at 38.68% needs
    #     c_ppe = 0.386807 * (0.015 + 0.1423) / 1.015 = 5.995%
    # which grossed up by 1 / HIST_PPE_CAPEX_SHARE is 6.403%. Base's
    # terminal less 100bp gives 6.41% — 0.7bp above Bear's own sustaining
    # level. So Bear's terminal capex holds PP&E/revenue at the same FY2025
    # 38.7% that Base's does; the two scenarios differ in growth and margin,
    # not in how capital-intensive the business is assumed to become. Capex
    # being lower in the bear case than the base case is what a genuine
    # demand slowdown looks like, and the resulting FCF relief is real, not
    # a modelling artefact to be suppressed.
    #
    # ROU additions shift by -40bp on the same reasoning, and the size of
    # the shift is set the same way: holding ROU/revenue at the FY2025
    # 19.20% at Bear's 1.5% terminal growth needs
    #     0.1920 * (0.015 + 0.1761) / 1.015 = 3.61%
    # against Base's terminal 4.06%, a 45bp gap. A uniform -40bp lands
    # Bear's terminal at 3.66%, 4.5bp above its own hold-flat level, while
    # keeping the path strictly below Base in every year.
    #
    # The ROU shift is smaller in magnitude than the capex shift (-100bp)
    # mainly because the leased asset base is about half the size of the
    # owned one relative to revenue (19.20% against 38.68%). The sustaining
    # ratio's sensitivity to growth, d(sust)/dg = p(1 - d)/(1 + g)^2, is
    # proportional to p, so the same change in growth moves the ROU rate
    # roughly half as far: ~14.5bp per pp of growth against ~32.5bp for
    # capex. Faster lease depreciation does damp it further, but only via
    # the (1 - d) factor, worth ~4% of the difference; the capex gross-up
    # for the intangible split adds another ~7%.
    "Bear": _scenario(
        BASE,
        growth_delta=-0.03,
        margin_delta=-0.015,
        opex_delta=0.010,
        capex_delta=-0.010,
        rou_delta=-0.004,
        exit_ev_ebitda=8.5,
    ),
    "Base": BASE,
    # Continued strong footfall/expansion case: growth holds up better,
    # margin expands on scale/mix, opex ratio improves further with
    # operating leverage, capex intensity runs 80bp above Base in every
    # year (funding faster growth than Base must cost more, not less), and
    # the exit multiple re-rates up.
    #
    # The shift is +80bp rather than +100bp, and it is derived, not a fudge.
    # At Bull's 7.0% terminal growth, sustaining PP&E/revenue at 38.68%
    # needs c_ppe = 0.386807 * (0.07 + 0.1423) / 1.07 = 7.675%, which
    # grossed up by 1 / HIST_PPE_CAPEX_SHARE is 8.198%. Base's terminal plus
    # 80bp gives 8.21%, 1.2bp above Bull's own sustaining level; plus 100bp
    # would have overshot it by ~21bp.
    #
    # Bull's +80bp gap from Base is smaller than Bear's 100bp gap almost
    # entirely because the two scenarios' growth deltas are unequal: -3.0pp
    # for Bear against +2.5pp for Bull. At the sustaining ratio's ~32.5bp
    # per pp of growth around Base, that alone gives 97bp against 81bp.
    # Curvature accounts for the remaining ~2-3bp, and it works the OPPOSITE
    # way to the convexity an earlier round claimed. The sustaining ratio is
    # strictly concave in growth:
    #     sust(g) = (p / s) * [1 - (1 - d) / (1 + g)]
    #     sust''(g) = -2 (p / s) (1 - d) / (1 + g)^3 < 0
    # so the per-pp slope FALLS as growth rises — 33.4bp/pp across Bear's
    # leg, 31.7bp/pp across Bull's. Concavity therefore trims a couple of
    # bp off Bull's gap rather than explaining it; the unequal deltas do
    # all the work.
    #
    # An earlier round used a symmetric +100bp and justified the overshoot
    # (~21bp on these grossed-up numbers) as a bull case "building ahead of
    # demand". That reading is dropped: round 2 established the principle
    # that each scenario lands on its own sustaining level, and applying it
    # here rather than preserving a flourish keeps all six terminal points
    # (capex and ROU, three scenarios) on one rule.
    #
    # ROU additions shift +40bp, sized the same way: at Bull's 7.0% terminal
    # growth, holding ROU/revenue at 19.20% needs
    #     0.1920 * (0.07 + 0.1761) / 1.07 = 4.42%
    # against Base's 4.06%, a 35bp gap, so a uniform +40bp puts Bull's
    # terminal at 4.46% — 4.4bp above its own hold-flat level.
    #
    # Note the two ROU shifts are equal in magnitude (+/-40bp) while the
    # gaps they close are not, and the direction is the reverse of what an
    # earlier round stated: Bull's +40bp is LARGER than its 35bp gap, and it
    # is Bear's -40bp that is smaller than its 45bp gap. Same cause as the
    # capex asymmetry above — the unequal growth deltas — and both land
    # within 5bp, which is the tolerance a single rounded delta buys.
    #
    # A faster rollout signs more leases as well as spending more capex;
    # modelling one without the other would understate what the growth
    # costs.
    "Bull": _scenario(
        BASE,
        growth_delta=0.025,
        margin_delta=0.015,
        opex_delta=-0.010,
        capex_delta=0.008,
        rou_delta=0.004,
        exit_ev_ebitda=11.5,
    ),
}
