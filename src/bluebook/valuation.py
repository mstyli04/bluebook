"""Valuation: WACC, unlevered free cash flow, terminal value, EV bridge.

This is the layer the rest of the model exists to feed. It takes a ``Model``
(the linked three-statement forecast) and a ``Drivers`` set, and returns a
discounted cash flow value per share.

--------------------------------------------------------------------------
WACC
--------------------------------------------------------------------------
    cost of equity = risk_free_rate + beta x equity_risk_premium
                   = 4.00% + 0.90 x 5.50% = 8.95%
    after-tax cost of debt = cost_of_debt x (1 - tax_rate)
                   = 5.50% x 75% = 4.125%
    WACC = (1 - target_debt_weight) x cost of equity
             + target_debt_weight x after-tax cost of debt
         = 78.7% x 8.95% + 21.3% x 4.125% = 7.9223%

All four market inputs are judgement estimates rather than sourced facts —
``assumptions.py`` says so beside each one — and none of them varies by
scenario, so the WACC is 7.9223% in Bear, Base and Bull alike and the whole
scenario spread is an operating spread. ``test_wacc_is_identical_in_every_
scenario`` pins that, so it becomes visible if a later task changes it.

``target_debt_weight`` is 21.3% and the debt base **includes lease
liabilities**, matching the equity bridge, which deducts them as debt. An
earlier version used 10% on financial debt alone while the bridge deducted
£449.8m of leases — two definitions of debt inside one model. Leases are debt
in both places now. The weight is net debt including leases over the model's
own Base enterprise value, solved as a fixed point; the derivation is written
out beside the driver in ``assumptions.py``.

Including leases in the WACC is also what captures the lease-interest tax
shield, roughly £4.5m a year. Unlevered FCF taxes EBIT and so cannot see it,
and a lease-free debt weight did not see it either, so it was previously
captured nowhere. Note the caveat recorded in ``assumptions.py``:
``cost_of_debt`` is the RCF rate applied to a base that is mostly leases
carried at a lower rate, which leaves the WACC ~22bp high.

Deducting new ROU additions from unlevered FCF (see below) is the third leg of
the same treatment.

--------------------------------------------------------------------------
Unlevered free cash flow
--------------------------------------------------------------------------
    FCF = EBIT x (1 - tax rate)
          + D&A (PP&E depreciation + ROU depreciation + amortisation)
          - capex (total cash capex, PP&E plus intangible)
          - new ROU additions
          - change in net working capital

New ROU additions are an investing outflow because the lease liability is
treated as debt in the bridge. Funding a leased shop is then economically the
same act as funding an owned one: cash out now, asset on the balance sheet,
liability in the bridge. Omitting the deduction while still subtracting lease
liabilities in the bridge would count the same leases twice, once as free
cash flow the business never had and once as debt.

The definition touches nothing below EBIT, so it is genuinely unlevered:
``test_unlevered_fcf_is_unaffected_by_the_financing_drivers`` doubles the
revolver rate and asserts the path is unchanged, which matters here because
the three-statement model is circular and a valuation that reached into net
income would pick the gearing up without saying so.

--------------------------------------------------------------------------
Terminal year — why it is re-based, and how
--------------------------------------------------------------------------
The terminal value is NOT struck on the raw FY2030 forecast year. Doing so
carries two errors of opposite sign, neither visible on its own:

1. **FY2030 is not a steady state.** PP&E/revenue is still 46.9% / 46.3% /
   45.9% (Bear / Base / Bull) against a terminal anchor near 40%, the tail of
   the distribution-centre build programme. The excess decays only at the
   depreciation rate, 14.23%/yr. FCF feels this solely through the tax shield
   on the extra depreciation — EBIT falls by the excess and D&A adds it
   straight back — so FY2030 unlevered FCF is flattered by roughly
   excess x tax rate. Capitalising a decaying item as a perpetuity overstates
   the terminal value.

2. **Larger, and the other way in Base and Bull.** Each scenario's final-year
   capex and ROU drivers were derived to sustain the asset base at that
   scenario's terminal REVENUE growth — 4.5% in Base. The terminal value grows
   at ``perpetuity_growth``, 2%. A slower-growing business needs less
   sustaining investment: total capex 6.852% of revenue at 2% growth against
   the 7.41% FY2030 Base driver, ROU additions 3.691% against 4.06%.

Net of the two, the direction is NOT uniform across scenarios, and reading the
Base case as a general property would be wrong:

    Bear   terminal growth 1.5%  ->  re-based FCF  £77.8m vs raw  £95.8m, -18.8%
    Base   terminal growth 4.5%  ->  re-based FCF £143.4m vs raw £126.4m, +13.4%
    Bull   terminal growth 7.0%  ->  re-based FCF £220.7m vs raw £165.1m, +33.7%

**The sign is not an invariant, and in particular it is not simply
``revenue_growth[-1] > g*``.** Three terms move on re-basing and only one of
them is signed by the growth gap:

  * the **investment** term (capex plus ROU additions) is signed by the growth
    gap — a perpetuity growing slower than the driver path needs less
    sustaining investment, and more if it grows faster;
  * the **D&A tax-shield** term always subtracts, because re-basing always
    strips FY2030's excess depreciation out;
  * the **anchor** term always adds investment, because the terminal PP&E
    anchor (~40%) sits above the 38.68% the capex drivers were built on.

Two of the three are one-signed and negative for FCF, so the crossover sits
strictly ABOVE ``g*`` rather than at it: at a driver growth of exactly ``g*``
the investment term is neutral but re-basing still cuts FCF. No shipped
scenario sits in that band, but an earlier version of this docstring and its
covering test asserted the naive rule as an invariant, which was false.
``test_rebasing_moves_terminal_fcf_against_a_per_scenario_expectation`` now
pins the three scenarios individually and claims nothing beyond them.

The fix is to pick one terminal growth rate ``g*`` — ``perpetuity_growth``,
the same rate the Gordon formula uses — and rebuild the terminal year on it.
For an asset held at intensity ``p`` (asset / revenue) that depreciates at
``d``, the steady state under revenue growth ``g`` satisfies

    p = c (1 + g) / (g + d)      so      c = p (g + d) / (1 + g)

with ``c`` the capex intensity. Depreciation in a steady-state year is
``d`` on the OPENING balance, i.e. ``d x p / (1 + g)`` of the year's revenue.

The ROU anchor ``p`` is the FY2025 actual, 19.20% of revenue. The PP&E anchor
is NOT: it is derived post-programme at roughly 40%, for the reasons set out
in ``terminal_ppe_intensity()``, because FY2025's 38.68% is the top of a
still-rising series rather than a finished state.

``capex_pct_revenue`` is a TOTAL capex ratio while only ``HIST_PPE_CAPEX_
SHARE`` (93.62%) of it reaches PP&E, so the sustaining PP&E requirement is
grossed up by ``1 / HIST_PPE_CAPEX_SHARE`` — the same gross-up
``assumptions.py`` documents, and the same one whose omission was a live bug
there. The intangible remainder drives the terminal amortisation charge,
which on the same steady-state logic is ``c_intangible x a / (g* + a)`` of
revenue.

Working capital contributes ``(NWC / revenue) x g* / (1 + g*)``. Greggs runs
NWC negative (payables dominate), so growth RELEASES cash and this term is a
small inflow.

The terminal year is struck at the FY2030 revenue LEVEL, not FY2031's: it is
"what FY2030 would have looked like in steady state". ``terminal_value_
gordon`` then applies the ``(1 + g)`` step itself, so the perpetuity starts
from a genuine FY2031 cash flow. Building it at FY2031 revenue and passing it
in would grow it twice.

Nothing here extends the forecast horizon. Reaching a true steady state would
take 11 to 17 more years of driver paths that nobody has justified.

--------------------------------------------------------------------------
The excess PP&E, valued explicitly
--------------------------------------------------------------------------
Re-basing removes the FY2029/FY2030 excess PP&E from the perpetuity, but that
excess is a real asset and its depreciation is a real tax shield. It is added
back as its own present value rather than smuggled back into the perpetuity:

    shield = tax_rate x d x E x x / (1 - x),    x = (1 - d) / (1 + WACC)

where ``E`` is the FY2029 closing excess, PP&E less ``anchor x revenue``.
This is the value AT the terminal date of the shields arising in FY2031
onwards, so it is added to the terminal value and discounted on the same
mid-year factor. Base: £27.9m at the terminal date, £19.8m present value,
about 19p per share. The FY2030 shield itself stays where it belongs, inside
the explicit FY2030 free cash flow.

``E`` is measured at FY2029 because the formula decays it once before the
first shield year: its ``k = 1`` term is ``tc x d x E x (1 - d) / (1 + WACC)``,
so ``E x (1 - d)`` is doing duty as the FY2030 excess.

**That step is now approximate, and it is approximate because of the anchor
ruling.** It used to be exact: when the terminal anchor was FY2025's 38.68%,
FY2030 capex was precisely the level that holds PP&E/revenue flat at that
anchor, so the excess decayed at (1 - d) with nothing added. Against the
post-programme anchor near 40%, FY2030 capex no longer sustains the anchor,
and ``E x (1 - d)`` overstates the model's own FY2030 excess by about 4.8%
(Base: 174.0 against 166.0). The shield is therefore ~£1.3m high at the
terminal date, worth about 0.9p per share.
``test_the_fy2029_decay_overstates_the_models_own_fy2030_gap`` measures the
residual rather than asserting a property that is no longer true.

The root cause is worth naming: the explicit-period capex drivers in
``assumptions.py`` are still calibrated to hold PP&E/revenue at 38.68%, while
the perpetuity now anchors near 40%. That inconsistency is flagged in the task
report, not fixed here — ``Drivers`` is out of scope for this task.

Two further approximations, both immaterial and both left alone:

  * the shield's internal terms are discounted year-end within the perpetuity
    (``(1 + WACC) ** k``) while the terminal value they sit beside is struck
    mid-year; mid-year-ising them would scale the shield by
    ``(1 + WACC) ** 0.5``, worth about 0.8p per share;
  * the same argument runs in reverse for ROU assets, which finish BELOW their
    anchor (18.3% against 19.20% in Base), so a symmetric treatment would
    deduct about £4.3m at the terminal date, roughly 3p per share. Not
    deducted: the brief mandates the PP&E add-back only.

--------------------------------------------------------------------------
Discounting
--------------------------------------------------------------------------
Mid-year convention: year ``t`` (1-based) is discounted at
``(1 + WACC) ** (t - 0.5)``, and the terminal value gets the same convention,
``(1 + WACC) ** (n - 0.5)`` — 4.5 years on a five-year forecast. That is the
consistent pairing: a Gordon perpetuity built from mid-year cash flows
discounts to the same 4.5-year point the last explicit year does.

--------------------------------------------------------------------------
The bridge
--------------------------------------------------------------------------
    equity value = EV - net debt - lease liabilities

Both deductions are the OPENING (FY2025 actual) balances, because the DCF
discounts to the FY2025 year end and EV is therefore a value at that date.
Subtracting FY2030 closing debt from a FY2025 present value would charge the
business twice for borrowing that the discounted FCF path already funds.
Greggs is in a net CASH position at FY2025 — £25.0m borrowings against £70.8m
cash, so net debt is -£45.8m and the bridge adds it back — while the £449.8m
lease liability is much the larger item and is deducted in full. Those are the
same two figures the WACC's debt weight is built from, which is the point of
the ruling that put leases in both.

Share price is returned in pence, equity value being in £m.
"""

from __future__ import annotations

from dataclasses import dataclass

from bluebook.assumptions import (
    HIST_INTANGIBLE_CAPEX_SHARE,
    HIST_PPE_CAPEX_SHARE,
    Drivers,
    amortisation_rate,
)
from bluebook.inputs.schema import HistoricalYear
from bluebook.reference import Model

PENCE_PER_POUND = 100.0


# ---------------------------------------------------------------------------
# WACC
# ---------------------------------------------------------------------------

def cost_of_equity(drivers: Drivers) -> float:
    """CAPM: risk-free rate plus beta times the equity risk premium."""
    return drivers.risk_free_rate + drivers.beta * drivers.equity_risk_premium


def after_tax_cost_of_debt(drivers: Drivers) -> float:
    """Pre-tax cost of debt less the interest tax shield."""
    return drivers.cost_of_debt * (1.0 - drivers.tax_rate)


def wacc(drivers: Drivers) -> float:
    """Weighted average cost of capital at the target capital structure.

    Debt weight is financial debt only; leases are handled in the bridge, not
    in the discount rate. See the module docstring.
    """
    equity_weight = 1.0 - drivers.target_debt_weight
    return (
        equity_weight * cost_of_equity(drivers)
        + drivers.target_debt_weight * after_tax_cost_of_debt(drivers)
    )


# ---------------------------------------------------------------------------
# Unlevered free cash flow
# ---------------------------------------------------------------------------

def unlevered_fcf(model: Model, drivers: Drivers) -> list[float]:
    """Unlevered FCF for each explicit forecast year, £m.

    ``model.cash_flow["capex"]`` is TOTAL cash capex (PP&E plus intangible) on
    the same definition ``inputs/greggs.py`` records, so both halves of the
    investment are deducted exactly once.
    """
    return [
        ebit * (1.0 - drivers.tax_rate) + da - capex - rou_additions - change_in_nwc
        for ebit, da, capex, rou_additions, change_in_nwc in zip(
            model.ebit,
            model.da_total,
            model.cash_flow["capex"],
            model.leases.additions,
            model.working_capital.change_in_nwc,
        )
    ]


# ---------------------------------------------------------------------------
# Terminal year
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class TerminalYear:
    """A steady-state-consistent restatement of the final forecast year.

    Struck at the final forecast year's REVENUE LEVEL, with every investment
    and depreciation intensity re-derived at ``growth`` (the perpetuity growth
    rate) instead of at the driver path's own terminal revenue growth. Feed
    ``fcf`` to ``terminal_value_gordon``, which applies the ``(1 + g)`` step.
    """

    growth: float
    revenue: float
    # Steady-state intensities, all as a fraction of ``revenue``.
    ebitda_margin: float
    capex_pct_revenue: float          # total cash capex, PP&E + intangible
    rou_additions_pct_revenue: float
    da_pct_revenue: float
    nwc_pct_revenue: float
    # Anchors the intensities were derived from, exposed so tests can check
    # the property rather than re-derive the formula.
    ppe_intensity: float              # post-programme, see terminal_ppe_intensity()
    rou_intensity: float              # FY2025 actual ROU assets / revenue
    ppe_capex_share: float
    # £m at ``revenue``.
    ebitda: float
    da: float
    ebit: float
    capex: float
    rou_additions: float
    change_in_nwc: float
    fcf: float


def terminal_ppe_intensity(model: Model, drivers: Drivers) -> float:
    """Post-programme PP&E/revenue anchor for the perpetuity.

    **The principle, in one sentence:** capacity built ahead of demand should
    be measured against the revenue it is sized to serve, and demand catches up
    at the perpetuity growth rate over the asset base's own average life, so
    the terminal anchor is the final forecast year's PP&E intensity discounted
    by one average-asset-life of perpetuity-rate growth.

        anchor = (PP&E_FY2030 / revenue_FY2030) / (1 + g*) ** (1 / d_ppe)

    ``1 / d_ppe`` = 1 / 14.23% = 7.03 years is the average remaining life the
    depreciation rate itself implies, and it is the right horizon because an
    asset built ahead of demand is by construction absorbed over the life of
    that asset — a distribution centre commissioned today is sized for the
    volume it will carry across its service life, not for this year's.

    **Why not the FY2025 actual (38.68%), which is what everything else in
    this model anchors on.** Owner ruling, Task 9 review: FY2025 is not a
    steady state. It is the top of a steeply rising series — 28.20% / 33.00% /
    38.68% across FY2023-25 — and it is the last *observed* year of the very
    distribution-centre programme that is still running. Anchoring the
    perpetuity there asserts that a permanent step-change in supply-chain
    capital intensity reverses itself, which is not what a completed build
    does.

    **Why not the model's own FY2030 (46.33% Base) either.** That is a
    transitional peak: intensity peaks in FY2028 at 48.21% and is already
    falling by FY2030, because capex is being tapered while the over-build
    depreciates off. Capitalising the peak assumes the transitional excess is
    permanent.

    The rule therefore lands strictly between the two, which is the ruling:
    Bear 40.84%, Base 40.31%, Bull 39.94%. It is scenario-dependent because
    each scenario finishes with its own estate against its own revenue, and
    the ordering is economically right — Bear grows slowest, so the same
    estate stays heaviest relative to sales.

    **Why the same treatment is NOT applied to the ROU anchor.** The premise
    does not hold for the leased estate: it is not mid-step-change. ROU/revenue
    ran 16.39% / 19.22% / 19.20% across FY2023-25 — it stepped up once and has
    been flat for two years — and the forecast never builds a transitional peak
    over it (Base runs 18.42% / 18.03% / 17.93% / 18.05% / 18.29%, entirely
    *below* the FY2025 actual, with no hump to unwind). There is no
    build-ahead to absorb, so FY2025 is already the plateau and the FY2025
    actual stands as the ROU anchor.

    **What judgement this embeds.** The split between permanent capacity and
    transitional over-build is not recoverable in closed form from anything in
    the repo — the schema has no distribution-centre capex line, and any
    intensity ``p`` is internally consistent with the capex ratio it implies,
    so the anchor cannot be derived from the capex logic without circularity.
    The absorption horizon is what does the work, and ``1 / d_ppe`` is the one
    horizon the data supplies rather than the modeller.
    """
    revenue = model.income_statement["revenue"][-1]
    final_intensity = model.balance_sheet["ppe"][-1] / revenue
    average_asset_life = 1.0 / drivers.ppe_depreciation_rate
    return final_intensity / (1.0 + drivers.perpetuity_growth) ** average_asset_life


def terminal_year(
    model: Model, drivers: Drivers, historicals: list[HistoricalYear]
) -> TerminalYear:
    """Rebuild the final forecast year on the perpetuity growth rate.

    Every input is derived — from ``historicals`` for the asset intensity
    anchors and the amortisation rate, from ``drivers`` for the depreciation
    rates, margins and tax, and from ``model`` for the revenue level and the
    working capital intensity. No literals. See the module docstring for the
    derivation and for why the raw final year cannot be used.
    """
    g = drivers.perpetuity_growth
    last = historicals[-1]

    ppe_intensity = terminal_ppe_intensity(model, drivers)
    # The leased estate keeps its FY2025 actual intensity — see
    # terminal_ppe_intensity() for why the owned estate does not, and why that
    # reasoning does not carry across to leases.
    rou_intensity = last.rou_assets.value / last.revenue.value

    # c = p (g + d) / (1 + g), grossed up for the share of total capex that
    # never reaches PP&E.
    sustaining_ppe_capex = ppe_intensity * (g + drivers.ppe_depreciation_rate) / (1.0 + g)
    capex_pct_revenue = sustaining_ppe_capex / HIST_PPE_CAPEX_SHARE
    rou_additions_pct_revenue = (
        rou_intensity * (g + drivers.rou_depreciation_rate) / (1.0 + g)
    )

    # Steady-state charges those intensities imply: depreciation is d on the
    # opening balance, and the opening balance is p x prior-year revenue.
    depreciation_ppe_pct = drivers.ppe_depreciation_rate * ppe_intensity / (1.0 + g)
    depreciation_rou_pct = drivers.rou_depreciation_rate * rou_intensity / (1.0 + g)
    # Intangibles reach their own steady state off the intangible slice of
    # terminal capex: balance = c_int (1 + g) / (g + a), charge = a x opening,
    # which collapses to c_int x a / (g + a) of revenue.
    intangible_capex_pct = capex_pct_revenue * HIST_INTANGIBLE_CAPEX_SHARE
    amortisation_pct_of_opening = amortisation_rate(historicals)
    amortisation_pct = (
        intangible_capex_pct
        * amortisation_pct_of_opening
        / (g + amortisation_pct_of_opening)
    )
    da_pct_revenue = depreciation_ppe_pct + depreciation_rou_pct + amortisation_pct

    revenue = model.income_statement["revenue"][-1]
    # Operating margin is the final forecast year's, unchanged: the re-basing
    # is about the investment and depreciation intensities, which FY2030 gets
    # wrong, not about the P&L margin, which is already a settled steady-state
    # judgement in the drivers.
    ebitda_margin = drivers.gross_margin[-1] - drivers.opex_pct_revenue[-1]
    nwc_pct_revenue = model.working_capital.net_working_capital[-1] / revenue

    ebitda = ebitda_margin * revenue
    da = da_pct_revenue * revenue
    ebit = ebitda - da
    capex = capex_pct_revenue * revenue
    rou_additions = rou_additions_pct_revenue * revenue
    # NWC grows with revenue, so the movement is the intensity times the
    # growth step. Negative for Greggs: payables exceed inventories plus
    # receivables, so growth releases cash.
    change_in_nwc = nwc_pct_revenue * g / (1.0 + g) * revenue

    fcf = (
        ebit * (1.0 - drivers.tax_rate)
        + da
        - capex
        - rou_additions
        - change_in_nwc
    )

    return TerminalYear(
        growth=g,
        revenue=revenue,
        ebitda_margin=ebitda_margin,
        capex_pct_revenue=capex_pct_revenue,
        rou_additions_pct_revenue=rou_additions_pct_revenue,
        da_pct_revenue=da_pct_revenue,
        nwc_pct_revenue=nwc_pct_revenue,
        ppe_intensity=ppe_intensity,
        rou_intensity=rou_intensity,
        ppe_capex_share=HIST_PPE_CAPEX_SHARE,
        ebitda=ebitda,
        da=da,
        ebit=ebit,
        capex=capex,
        rou_additions=rou_additions,
        change_in_nwc=change_in_nwc,
        fcf=fcf,
    )


def excess_asset_tax_shield(
    excess: float, depreciation_rate: float, tax_rate: float, wacc_rate: float
) -> float:
    """Value at the terminal date of tax shields on a decaying asset excess.

        shield = tax_rate x d x E x x / (1 - x),   x = (1 - d) / (1 + WACC)

    ``excess`` is the FY2029 closing excess over the steady-state asset base;
    the formula decays it once before the first shield year, so ``E x (1 - d)``
    stands in for the FY2030 excess. The stream summed is the shields arising
    in FY2031 onwards — FY2030's shield is a legitimate explicit-period cash
    flow and is already inside the FY2030 FCF.

    Returns a TERMINAL-DATE value, so the caller discounts it on the same
    factor as the terminal value. Terms inside the sum are discounted
    year-end; see the module docstring for that and for the ~4.8% overstatement
    the FY2029 decay now carries against the post-programme anchor.
    """
    x = (1.0 - depreciation_rate) / (1.0 + wacc_rate)
    return tax_rate * depreciation_rate * excess * x / (1.0 - x)


# ---------------------------------------------------------------------------
# Terminal value
# ---------------------------------------------------------------------------

def terminal_value_gordon(final_fcf: float, wacc_rate: float, g: float) -> float:
    """Gordon growth perpetuity, struck at the end of the explicit period.

    ``final_fcf`` is the last explicit-period-level cash flow; the ``(1 + g)``
    step to the first perpetuity year is applied here, so callers must NOT
    pre-grow it.
    """
    if g >= wacc_rate:
        raise ValueError(
            f"perpetuity growth ({g}) must be below WACC ({wacc_rate}): a "
            "perpetuity growing at or above its discount rate is infinite"
        )
    return final_fcf * (1.0 + g) / (wacc_rate - g)


def terminal_value_exit_multiple(final_ebitda: float, multiple: float) -> float:
    """EV/EBITDA exit multiple applied to the final forecast year's EBITDA.

    Post-IFRS 16 EBITDA, so rent is added back and the coherent multiple is
    structurally lower than a pre-IFRS-16 one. ``drivers.exit_ev_ebitda`` has
    not been recalibrated for that — see the task report and Task 10.
    """
    return final_ebitda * multiple


# ---------------------------------------------------------------------------
# Discounting and the bridge
# ---------------------------------------------------------------------------

def discount_factors(periods: int, wacc_rate: float) -> list[float]:
    """Mid-year discount factors for years 1..periods."""
    return [(1.0 + wacc_rate) ** (t - 0.5) for t in range(1, periods + 1)]


def enterprise_value(fcf: list[float], tv: float, wacc_rate: float) -> float:
    """PV of the explicit FCF path plus the PV of the terminal value.

    Mid-year convention throughout, including on the terminal value, which is
    discounted at ``(1 + WACC) ** (n - 0.5)`` — the same point in time the
    final explicit year discounts to.
    """
    factors = discount_factors(len(fcf), wacc_rate)
    pv_fcf = sum(f / factor for f, factor in zip(fcf, factors))
    return pv_fcf + tv / factors[-1]


def equity_bridge(ev: float, net_debt: float, lease_liabilities: float) -> float:
    """EV to equity value. Both deductions are opening (FY2025) balances."""
    return ev - net_debt - lease_liabilities


def implied_share_price(equity_value: float, shares: float) -> float:
    """Equity value (£m) over share count (m), returned in pence."""
    return equity_value / shares * PENCE_PER_POUND


# ---------------------------------------------------------------------------
# The assembled valuation
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Valuation:
    """Everything the valuation layer produces for one scenario."""

    wacc: float
    cost_of_equity: float
    after_tax_cost_of_debt: float
    fcf: list[float]
    discount_factors: list[float]
    pv_fcf: list[float]
    terminal: TerminalYear
    terminal_value_gordon: float
    terminal_value_exit_multiple: float
    excess_ppe: float
    excess_ppe_tax_shield: float
    pv_terminal_value: float
    enterprise_value: float
    net_debt: float
    lease_liabilities: float
    equity_value: float
    share_price_pence: float


def value_model(
    model: Model,
    drivers: Drivers,
    historicals: list[HistoricalYear],
    shares: float,
) -> Valuation:
    """Discount the model to an implied share price.

    The headline enterprise value uses the GORDON terminal value on the
    re-based terminal year, plus the explicit excess-PP&E tax shield. The exit
    multiple terminal value is computed alongside and reported, but is not
    used: ``drivers.exit_ev_ebitda`` is a pre-IFRS-16-flavoured judgement that
    disagrees with Gordon by roughly 2x, and reconciling it needs the comps
    sheet Task 10 builds.
    """
    rate = wacc(drivers)
    fcf = unlevered_fcf(model, drivers)
    terminal = terminal_year(model, drivers, historicals)

    tv_gordon = terminal_value_gordon(terminal.fcf, rate, drivers.perpetuity_growth)
    tv_exit = terminal_value_exit_multiple(model.ebitda[-1], drivers.exit_ev_ebitda)

    # Excess PP&E over the steady-state base, measured at FY2029 — see the
    # module docstring for why FY2029 and not FY2030.
    revenue = model.income_statement["revenue"]
    excess_ppe = (
        model.balance_sheet["ppe"][-2] - terminal.ppe_intensity * revenue[-2]
    )
    shield = excess_asset_tax_shield(
        excess_ppe, drivers.ppe_depreciation_rate, drivers.tax_rate, rate
    )

    factors = discount_factors(len(fcf), rate)
    pv_fcf = [f / factor for f, factor in zip(fcf, factors)]
    pv_terminal_value = (tv_gordon + shield) / factors[-1]
    ev = enterprise_value(fcf, tv_gordon + shield, rate)

    # Opening balance sheet: EV is a present value at the FY2025 year end.
    last = historicals[-1]
    net_debt = last.borrowings.value - last.cash.value
    lease_liabilities = last.lease_liabilities.value
    equity_value = equity_bridge(ev, net_debt, lease_liabilities)

    return Valuation(
        wacc=rate,
        cost_of_equity=cost_of_equity(drivers),
        after_tax_cost_of_debt=after_tax_cost_of_debt(drivers),
        fcf=fcf,
        discount_factors=factors,
        pv_fcf=pv_fcf,
        terminal=terminal,
        terminal_value_gordon=tv_gordon,
        terminal_value_exit_multiple=tv_exit,
        excess_ppe=excess_ppe,
        excess_ppe_tax_shield=shield,
        pv_terminal_value=pv_terminal_value,
        enterprise_value=ev,
        net_debt=net_debt,
        lease_liabilities=lease_liabilities,
        equity_value=equity_value,
        share_price_pence=implied_share_price(equity_value, shares),
    )
