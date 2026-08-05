"""Valuation layer: WACC, unlevered FCF, terminal value, EV bridge.

The first block of tests is the brief's own set, kept verbatim. Everything
after it covers the mandated terminal-year re-basing, which is the substance
of this task and which the brief's set does not reach: those tests all strike
a Gordon terminal value off the RAW final forecast year, which is precisely
the construction the re-basing exists to replace. They are kept because they
still pin the arithmetic of each primitive; they are not the model's own
terminal value.

Where a test could be satisfied by reproducing the formula under test, it is
written to avoid doing so — the steady-state intensity tests iterate the real
schedules forward instead of re-deriving p = c(1 + g)/(g + d), and the
tax-shield test sums the decaying stream year by year instead of re-stating
the closed form. tests/test_assumptions.py records why: a capex error once
survived review inside a test that re-derived the very formula it audited.
"""

import pytest
from dataclasses import replace

from bluebook.assumptions import SCENARIOS
from bluebook.inputs.greggs import GREGGS_HISTORICALS, GREGGS_SHARE_COUNT
from bluebook.reference import build_model
from bluebook.schedules.fixed_assets import fixed_assets
from bluebook.schedules.leases import leases
from bluebook.valuation import (
    after_tax_cost_of_debt, enterprise_value, equity_bridge, implied_share_price,
    terminal_value_exit_multiple, terminal_value_gordon, unlevered_fcf, wacc,
)
from bluebook.valuation import (
    discount_factors, excess_asset_tax_shield, terminal_year, value_model,
)

BASE = SCENARIOS["Base"]


# ---------------------------------------------------------------------------
# The brief's tests, verbatim.
# ---------------------------------------------------------------------------

def test_wacc_is_between_cost_of_debt_and_cost_of_equity():
    rate = wacc(BASE)
    cost_of_equity = BASE.risk_free_rate + BASE.beta * BASE.equity_risk_premium
    after_tax_debt = BASE.cost_of_debt * (1 - BASE.tax_rate)
    assert after_tax_debt < rate < cost_of_equity


def test_gordon_growth_requires_g_below_wacc():
    with pytest.raises(ValueError, match="perpetuity growth"):
        terminal_value_gordon(final_fcf=100.0, wacc_rate=0.05, g=0.06)


def test_gordon_growth_formula():
    assert terminal_value_gordon(100.0, 0.08, 0.02) == pytest.approx(100 * 1.02 / 0.06)


def test_exit_multiple_formula():
    assert terminal_value_exit_multiple(200.0, 8.0) == pytest.approx(1600.0)


def test_enterprise_value_discounts_mid_year_consistently():
    ev = enterprise_value(fcf=[100.0] * 5, tv=1000.0, wacc_rate=0.10)
    assert 0 < ev < sum([100.0] * 5) + 1000.0
    # The brief's assertion above is satisfied by ANY positive discount rate
    # and pins nothing about the convention its own name claims. These pin it.
    # Year t discounts at (1 + r) ** (t - 0.5), and the terminal value shares
    # the final year's factor rather than taking a full-year one.
    assert discount_factors(5, 0.10) == pytest.approx(
        [1.10 ** 0.5, 1.10 ** 1.5, 1.10 ** 2.5, 1.10 ** 3.5, 1.10 ** 4.5]
    )
    assert ev == pytest.approx(
        sum(100.0 / 1.10 ** (t - 0.5) for t in range(1, 6)) + 1000.0 / 1.10 ** 4.5
    )
    # Explicitly NOT the year-end convention, and explicitly not a full five
    # years on the terminal value — the two mistakes this test exists to catch.
    assert ev != pytest.approx(
        sum(100.0 / 1.10 ** t for t in range(1, 6)) + 1000.0 / 1.10 ** 5
    )
    assert ev != pytest.approx(
        sum(100.0 / 1.10 ** (t - 0.5) for t in range(1, 6)) + 1000.0 / 1.10 ** 5
    )


def test_equity_bridge_subtracts_leases_as_debt():
    """Post-IFRS 16: lease liabilities reduce equity value."""
    with_leases = equity_bridge(ev=1000.0, net_debt=100.0, lease_liabilities=200.0)
    without = equity_bridge(ev=1000.0, net_debt=100.0, lease_liabilities=0.0)
    assert with_leases == pytest.approx(700.0)
    assert without - with_leases == pytest.approx(200.0)


def test_implied_share_price_returns_pence():
    # £700m equity over 100m shares = £7.00 = 700p
    assert implied_share_price(700.0, 100.0) == pytest.approx(700.0)


@pytest.mark.parametrize("name", ["Bear", "Base", "Bull"])
def test_terminal_value_is_not_an_implausible_share_of_ev(name):
    """Terminal concentration, measured on the construction the model uses.

    Two changes from the brief's version, both of which it needed:

    1. **The clock.** It discounted the TV at ``(1 + rate) ** 5`` while
       ``enterprise_value`` discounts it at ``** 4.5``, understating the share
       by 3.8%. Base's 0.895 "just inside the 0.9 bound" was an artefact of
       comparing two different discount clocks; corrected, the naive figure is
       0.9284 and the 0.9 bound fails in all three scenarios.
    2. **The construction.** It struck Gordon off the RAW final forecast year.
       The model does not use that number anywhere. A bound on a construction
       the model does not use cannot catch a regression in the one it does.

    **This is the sanity bound only.** It was one test doing two jobs and
    doing neither well: a 0.97 ceiling on the terminal share lets the explicit
    period fall to 3% of EV, and Bear's is 4.82% (£50.4m), so the explicit
    period could have lost ~38% of its value with nothing failing. Fix round 2
    moved concentration by 0.4-0.7pp and this test did not notice. The
    step-change job now belongs to
    ``test_terminal_share_of_ev_regression_pin`` below.

    Stated on the explicit period rather than on the terminal share, because
    that is the side with the economics in it. Two claims:

      * the explicit period's PV is **positive** — five years that consume more
        cash than they generate, in present-value terms, would mean the whole
        valuation rests on the perpetuity and the forecast is pure cost;
      * it is at least **3% of EV** — a floor, not a target. Concentration this
        high is a real property of a five-year window whose first two years of
        FCF are negative while the distribution-centre programme runs off, and
        the honest reading is that it is structurally high, not that it is
        comfortable.
    """
    drivers = SCENARIOS[name]
    model = build_model(GREGGS_HISTORICALS, drivers)
    valuation = value_model(model, drivers, GREGGS_HISTORICALS, GREGGS_SHARE_COUNT.value)
    explicit_pv = sum(valuation.pv_fcf)
    assert explicit_pv > 0.0, (
        f"{name}: the explicit five years have a negative present value "
        f"({explicit_pv:.1f}), so the entire valuation is the perpetuity"
    )
    assert explicit_pv / valuation.enterprise_value > 0.03, (
        f"{name}: explicit-period PV is {explicit_pv / valuation.enterprise_value:.2%} "
        f"of EV"
    )
    # The two components must foot to EV — otherwise the share above could be
    # measured against something that is not the whole.
    assert explicit_pv + valuation.pv_terminal_value == pytest.approx(
        valuation.enterprise_value
    )


@pytest.mark.parametrize(
    "name,recorded_share",
    # RECORDED, not derived. These are the terminal shares the committed model
    # produces; there is no principle that says they should be these numbers.
    # Their job is to make a step-change in concentration visible, which the
    # sanity bound above is far too wide to do — it did not react when fix
    # round 2 moved every one of these by 0.4-0.7pp.
    [("Bear", 0.9518), ("Base", 0.9399), ("Bull", 0.9306)],
)
def test_terminal_share_of_ev_regression_pin(name, recorded_share):
    """Tight pin on terminal concentration. Expected to be edited, deliberately.

    +/-0.5pp. If a change moves these, that is a finding to look at and then
    re-record with the reason, not a failure to widen the band around. Any
    round that edits these numbers should say in its report why concentration
    moved and by how much.
    """
    drivers = SCENARIOS[name]
    model = build_model(GREGGS_HISTORICALS, drivers)
    valuation = value_model(model, drivers, GREGGS_HISTORICALS, GREGGS_SHARE_COUNT.value)
    share = valuation.pv_terminal_value / valuation.enterprise_value
    assert share == pytest.approx(recorded_share, abs=0.005), (
        f"{name}: terminal value is {share:.2%} of EV against a recorded "
        f"{recorded_share:.2%} — concentration has moved, say why"
    )


def test_bull_case_values_higher_than_bear():
    prices = {}
    for name in ("Bear", "Bull"):
        drivers = SCENARIOS[name]
        model = build_model(GREGGS_HISTORICALS, drivers)
        fcf = unlevered_fcf(model, drivers)
        rate = wacc(drivers)
        tv = terminal_value_gordon(fcf[-1], rate, drivers.perpetuity_growth)
        prices[name] = enterprise_value(fcf, tv, rate)
    assert prices["Bull"] > prices["Bear"]


# ---------------------------------------------------------------------------
# WACC
# ---------------------------------------------------------------------------

def test_wacc_weights_equity_and_after_tax_debt_at_the_target_structure():
    """Pins the build, not just the ordering the brief's test checks."""
    from bluebook.assumptions import BLENDED_COST_OF_DEBT

    rate = wacc(BASE)
    assert rate == pytest.approx(
        (1 - 0.2075) * (0.04 + 0.90 * 0.055) + 0.2075 * BLENDED_COST_OF_DEBT * 0.75
    )
    assert rate == pytest.approx(0.077311, abs=1e-6)
    # The rate applied to the debt leg must be the blend, not the RCF rate:
    # the base it weights is £449.8m of leases against £25.0m of RCF.
    assert after_tax_cost_of_debt(BASE) == pytest.approx(BLENDED_COST_OF_DEBT * 0.75)
    assert BLENDED_COST_OF_DEBT < 0.055
    # The debt weight must be the one the bridge implies, not financial debt
    # alone. Pinning it here means a silent revert to 10% fails a test rather
    # than quietly re-introducing two definitions of debt.
    last = GREGGS_HISTORICALS[-1]
    net_debt_and_leases = (
        last.borrowings.value - last.cash.value + last.lease_liabilities.value
    )
    valuation = value_model(
        build_model(GREGGS_HISTORICALS, BASE), BASE, GREGGS_HISTORICALS,
        GREGGS_SHARE_COUNT.value,
    )
    assert net_debt_and_leases / valuation.enterprise_value == pytest.approx(
        BASE.target_debt_weight, abs=5e-4
    )


def test_wacc_is_identical_in_every_scenario():
    """Bear/Base/Bull shift operating drivers only; none touches the WACC build.

    Worth pinning: if a later task starts flexing beta or the debt weight by
    scenario, the scenario spread stops being a pure operating spread and this
    test should be the thing that says so.
    """
    rates = {name: wacc(d) for name, d in SCENARIOS.items()}
    assert len(set(round(r, 12) for r in rates.values())) == 1


# ---------------------------------------------------------------------------
# Unlevered FCF
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name", ["Bear", "Base", "Bull"])
def test_unlevered_fcf_reconciles_to_ebitda_less_tax_on_ebit(name):
    """EBIT(1 - t) + D&A is EBITDA - t x EBIT; check the rearrangement holds.

    What this does and does not cover. It pins the tax treatment (tax is
    charged on EBIT, not on EBITDA and not on profit after interest) and the
    deduction set (total capex, ROU additions and the NWC movement, each once).

    It does NOT cover the D&A series, and an earlier docstring wrongly claimed
    it did. ``reference.py`` defines ``ebit = ebitda - da_total``, so
    ``EBIT(1-t) + D&A == EBITDA - t x EBIT`` is an identity for ANY
    ``da_total`` whatsoever; substituting a garbage D&A series changes both
    sides equally and the test still passes. The D&A series is covered
    upstream, by the schedule tests in tests/test_schedules.py.
    """
    drivers = SCENARIOS[name]
    model = build_model(GREGGS_HISTORICALS, drivers)
    fcf = unlevered_fcf(model, drivers)
    expected = [
        e - drivers.tax_rate * ebit - capex - rou - dnwc
        for e, ebit, capex, rou, dnwc in zip(
            model.ebitda,
            model.ebit,
            model.cash_flow["capex"],
            model.leases.additions,
            model.working_capital.change_in_nwc,
        )
    ]
    assert fcf == pytest.approx(expected)


def test_unlevered_fcf_is_unaffected_by_the_financing_drivers():
    """Unlevered means unlevered: doubling the revolver rate must not move it.

    The three-statement model is circular — interest feeds tax feeds cash feeds
    debt — so a valuation that reached into net income rather than EBIT would
    silently pick the financing up. This is the test that catches that.
    """
    geared = replace(BASE, interest_rate_debt=BASE.interest_rate_debt * 2)
    base_fcf = unlevered_fcf(build_model(GREGGS_HISTORICALS, BASE), BASE)
    geared_fcf = unlevered_fcf(build_model(GREGGS_HISTORICALS, geared), geared)
    assert base_fcf == pytest.approx(geared_fcf)
    # ... and the geared model really did differ, so the test is not vacuous.
    assert build_model(GREGGS_HISTORICALS, geared).net_income != pytest.approx(
        build_model(GREGGS_HISTORICALS, BASE).net_income
    )


def test_unlevered_fcf_deducts_rou_additions():
    """Lease liabilities sit in the bridge, so funding the leased asset is capex.

    Dropping the deduction would flatter every year by the full addition.
    """
    model = build_model(GREGGS_HISTORICALS, BASE)
    fcf = unlevered_fcf(model, BASE)
    without_rou = [
        f + rou for f, rou in zip(fcf, model.leases.additions)
    ]
    assert all(w > f for w, f in zip(without_rou, fcf))
    assert without_rou[-1] - fcf[-1] == pytest.approx(model.leases.additions[-1])


# ---------------------------------------------------------------------------
# Terminal-year re-basing
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name", ["Bear", "Base", "Bull"])
def test_terminal_capex_holds_ppe_to_the_fy2025_anchor_when_iterated(name):
    """Run the real PP&E schedule forward at g* on the terminal capex ratio.

    No closed form anywhere in this test: the assertion is that the schedule
    itself converges to the FY2025 PP&E/revenue anchor, which is the property
    the terminal capex intensity is supposed to have.
    """
    drivers = SCENARIOS[name]
    terminal = terminal_year(build_model(GREGGS_HISTORICALS, drivers), drivers, GREGGS_HISTORICALS)
    g = drivers.perpetuity_growth
    years = 200
    revenue = [1000.0 * (1 + g) ** t for t in range(1, years + 1)]
    ppe_drivers = replace(
        drivers,
        capex_pct_revenue=tuple([terminal.capex_pct_revenue * terminal.ppe_capex_share] * years),
    )
    schedule = fixed_assets(1000.0 * terminal.ppe_intensity, revenue, ppe_drivers)
    assert schedule.closing_ppe[-1] / revenue[-1] == pytest.approx(
        terminal.ppe_intensity, rel=1e-9
    )


@pytest.mark.parametrize("name", ["Bear", "Base", "Bull"])
def test_terminal_rou_additions_hold_rou_to_the_fy2025_anchor_when_iterated(name):
    """Same iteration check for the leased half of the estate."""
    drivers = SCENARIOS[name]
    terminal = terminal_year(build_model(GREGGS_HISTORICALS, drivers), drivers, GREGGS_HISTORICALS)
    g = drivers.perpetuity_growth
    years = 200
    revenue = [1000.0 * (1 + g) ** t for t in range(1, years + 1)]
    lease_drivers = replace(
        drivers,
        rou_additions_pct_revenue=tuple([terminal.rou_additions_pct_revenue] * years),
    )
    schedule = leases(1000.0 * terminal.rou_intensity, 0.0, revenue, lease_drivers)
    assert schedule.closing_rou[-1] / revenue[-1] == pytest.approx(
        terminal.rou_intensity, rel=1e-9
    )


@pytest.mark.parametrize("name", ["Bear", "Base", "Bull"])
def test_terminal_year_is_built_at_the_perpetuity_growth_rate_not_the_driver_path(name):
    """The whole point of the re-basing: one g*, used everywhere.

    Each scenario's final-year capex and ROU ratios were derived at that
    scenario's own terminal REVENUE growth; the terminal value grows at
    ``perpetuity_growth``. The two differ, so the sustaining intensities
    differ — and the direction is set by which growth rate is larger, not by a
    blanket "terminal is lower". Base (4.5%) and Bull (7.0%) sit above 2%, so
    their re-based intensities fall; Bear (1.5%) sits below, so its rise.
    """
    drivers = SCENARIOS[name]
    terminal = terminal_year(build_model(GREGGS_HISTORICALS, drivers), drivers, GREGGS_HISTORICALS)
    assert terminal.growth == drivers.perpetuity_growth
    driver_growth = drivers.revenue_growth[-1]
    if driver_growth > drivers.perpetuity_growth:
        assert terminal.capex_pct_revenue < drivers.capex_pct_revenue[-1]
        assert terminal.rou_additions_pct_revenue < drivers.rou_additions_pct_revenue[-1]
    else:
        assert terminal.capex_pct_revenue > drivers.capex_pct_revenue[-1]
        assert terminal.rou_additions_pct_revenue > drivers.rou_additions_pct_revenue[-1]


@pytest.mark.parametrize("name", ["Bear", "Base", "Bull"])
def test_terminal_year_strips_the_fy2030_excess_depreciation(name):
    """FY2030 D&A carries the tail of the distribution-centre build; the
    terminal year must not.

    PP&E/revenue is still ~46% in FY2030 against a ~38.7% steady state, so a
    steady-state-consistent D&A charge is materially lower.
    """
    drivers = SCENARIOS[name]
    model = build_model(GREGGS_HISTORICALS, drivers)
    terminal = terminal_year(model, drivers, GREGGS_HISTORICALS)
    assert terminal.da < model.da_total[-1]
    assert model.balance_sheet["ppe"][-1] / model.income_statement["revenue"][-1] > (
        terminal.ppe_intensity + 0.05
    )


@pytest.mark.parametrize(
    "name,expected_pct_change",
    # Re-based terminal FCF against the raw final forecast year, per scenario.
    [("Bear", -10.8), ("Base", 22.1), ("Bull", 41.3)],
)
def test_rebasing_moves_terminal_fcf_against_a_per_scenario_expectation(
    name, expected_pct_change
):
    """Three separate expectations. Deliberately NOT an invariant.

    An earlier version asserted ``(terminal.fcf > raw) ==
    (revenue_growth[-1] > perpetuity_growth)`` as a general rule. That is
    false. Three terms move on re-basing and only the investment term (capex
    plus ROU additions) is signed by the growth gap; the D&A-tax-shield term
    always subtracts, and the anchor uplift always adds investment. Two of the
    three are one-signed against FCF, so the crossover sits strictly ABOVE
    ``g*``, not at it — at a driver growth of exactly ``g*`` the investment
    term is neutral and re-basing still cuts FCF. No shipped scenario sits in
    that band, but a false invariant in a test is worse than no invariant,
    especially one written in the same breath as a correction of somebody
    else's over-general claim.
    """
    drivers = SCENARIOS[name]
    model = build_model(GREGGS_HISTORICALS, drivers)
    terminal = terminal_year(model, drivers, GREGGS_HISTORICALS)
    raw = unlevered_fcf(model, drivers)[-1]
    assert (terminal.fcf / raw - 1.0) * 100 == pytest.approx(expected_pct_change, abs=0.1)


@pytest.mark.parametrize("name", ["Bear", "Base", "Bull"])
def test_terminal_fcf_matches_a_steady_state_reached_by_iterating_the_schedules(name):
    """Independent construction of the terminal year, with no closed forms.

    ``terminal_year()`` computes every intensity from ``p = c(1+g)/(g+d)`` and
    its depreciation corollary. This rebuilds the same cash flow by running the
    REAL ``fixed_assets()`` and ``leases()`` schedules 300 years forward at g*
    on the terminal intensities, plus an explicit intangibles roll-forward, and
    reading the converged FCF/revenue ratio straight off the result.

    It shares no algebra with the thing it checks — only the drivers and the
    definition of unlevered FCF. If the closed forms and the schedules ever
    describe different roll-forwards, this is what says so. It is also what
    makes the recorded percentages in the test below an expectation rather than
    a recording: those numbers are what this construction produces.
    """
    drivers = SCENARIOS[name]
    model = build_model(GREGGS_HISTORICALS, drivers)
    terminal = terminal_year(model, drivers, GREGGS_HISTORICALS)
    g = drivers.perpetuity_growth
    years = 300
    revenue = [(1.0 + g) ** t for t in range(1, years + 1)]

    ppe = fixed_assets(
        0.0,
        revenue,
        replace(
            drivers,
            capex_pct_revenue=(
                terminal.capex_pct_revenue * terminal.ppe_capex_share,
            ) * years,
        ),
    )
    rou = leases(
        0.0,
        0.0,
        revenue,
        replace(
            drivers,
            rou_additions_pct_revenue=(terminal.rou_additions_pct_revenue,) * years,
        ),
    )
    from bluebook.assumptions import HIST_INTANGIBLE_CAPEX_SHARE, amortisation_rate

    amortisation_pct = amortisation_rate(GREGGS_HISTORICALS)
    intangible_capex = terminal.capex_pct_revenue * HIST_INTANGIBLE_CAPEX_SHARE
    balance, amortisation = 0.0, 0.0
    for year_revenue in revenue:
        amortisation = balance * amortisation_pct
        balance += year_revenue * intangible_capex - amortisation

    last_revenue = revenue[-1]
    da = (ppe.depreciation[-1] + rou.depreciation[-1] + amortisation) / last_revenue
    ebitda = terminal.ebitda_margin
    fcf_ratio = (
        (ebitda - da) * (1 - drivers.tax_rate)
        + da
        - terminal.capex_pct_revenue
        - terminal.rou_additions_pct_revenue
        - terminal.nwc_pct_revenue * g / (1 + g)
    )
    assert fcf_ratio == pytest.approx(terminal.fcf / terminal.revenue, rel=1e-9)


def test_terminal_year_reproduces_the_briefed_base_case_figures():
    """Anchor on the numbers the brief states, so a silent drift is caught."""
    drivers = SCENARIOS["Base"]
    model = build_model(GREGGS_HISTORICALS, drivers)
    terminal = terminal_year(model, drivers, GREGGS_HISTORICALS)
    # 6.852% against the 6.575% the brief quotes: the brief's figure was struck
    # on the FY2025 anchor, which the Task 9 review moved to a post-programme
    # ~40%. The ROU intensity is unchanged because its anchor was not moved.
    assert terminal.capex_pct_revenue == pytest.approx(0.069015, abs=5e-6)
    assert terminal.rou_additions_pct_revenue == pytest.approx(0.036910, abs=5e-6)
    assert terminal.fcf == pytest.approx(142.3, abs=0.1)
    assert unlevered_fcf(model, drivers)[-1] == pytest.approx(116.5, abs=0.1)


def test_terminal_value_is_struck_on_the_rebased_year_not_the_raw_one():
    drivers = SCENARIOS["Base"]
    model = build_model(GREGGS_HISTORICALS, drivers)
    valuation = value_model(model, drivers, GREGGS_HISTORICALS, GREGGS_SHARE_COUNT.value)
    rate = wacc(drivers)
    g = drivers.perpetuity_growth
    assert valuation.terminal_value_gordon == pytest.approx(
        terminal_value_gordon(valuation.terminal.fcf, rate, g)
    )
    assert valuation.terminal_value_gordon != pytest.approx(
        terminal_value_gordon(unlevered_fcf(model, drivers)[-1], rate, g)
    )


# ---------------------------------------------------------------------------
# Excess PP&E tax shield
# ---------------------------------------------------------------------------

def test_excess_asset_tax_shield_matches_a_year_by_year_sum():
    """Closed form checked against the stream it claims to sum.

    The shield is valued AT the terminal date, so year k (k = 1 for the first
    year after the terminal year) is discounted k times — year-end within the
    perpetuity, which is a known ~0.8p inconsistency against the mid-year
    terminal value it sits beside (see the module docstring).
    """
    excess, rate, tax, rate_wacc = 245.9, 0.1423, 0.25, 0.0773113
    explicit = 0.0
    carried = excess
    for k in range(1, 600):
        carried *= 1 - rate
        explicit += tax * rate * carried / (1 + rate_wacc) ** k
    assert excess_asset_tax_shield(excess, rate, tax, rate_wacc) == pytest.approx(explicit)


@pytest.mark.parametrize("name", ["Bear", "Base", "Bull"])
def test_the_fy2029_decay_lands_on_the_models_own_fy2030_gap(name):
    """The convergence check for fix round 2, and its whole point.

    The shield's closed form decays the FY2029 excess once at (1 - d) to stand
    in for the FY2030 excess, which is exact only if FY2030 capex exactly
    sustains the terminal anchor.

    History of this assertion, because the sign of it is the diagnostic:

      * Round 0-1a: exact. The anchor was FY2025's 38.68% and the capex
        drivers were calibrated to hold precisely that.
      * Round 1: **broken, by +4.0% to +5.4%**. The anchor moved to the
        post-programme intensity while the capex drivers still targeted
        38.68%, so FY2030 capex under-sustained the anchor and the decayed
        excess ran high. That drift was the measurable symptom of the model
        converging on one steady state while valuing another.
      * Round 2: **closed**. The capex drivers were recalibrated onto the
        anchor, so FY2030 capex sustains it again.

    The residual is now two orders of magnitude smaller and is pure rounding:
    the driver tuples carry 4 decimal places while the fixed point does not
    land on one. Its SIGN tracks the rounding direction of the driver exactly
    — a driver rounded up buys more FY2030 capex, a larger true FY2030 excess,
    and therefore a negative residual — which is asserted below, because "the
    number got small" is a weaker claim than "what is left is only the
    rounding, and it points the way rounding would".
    """
    from bluebook.assumptions import HIST_PPE_CAPEX_SHARE

    drivers = SCENARIOS[name]
    model = build_model(GREGGS_HISTORICALS, drivers)
    valuation = value_model(model, drivers, GREGGS_HISTORICALS, GREGGS_SHARE_COUNT.value)
    anchor = valuation.terminal.ppe_intensity
    revenue = model.income_statement["revenue"]
    actual_fy2030_excess = model.balance_sheet["ppe"][-1] - anchor * revenue[-1]
    decayed = valuation.excess_ppe * (1 - drivers.ppe_depreciation_rate)
    residual = decayed / actual_fy2030_excess - 1.0

    assert abs(residual) < 0.001, (
        f"{name}: the FY2029 excess decayed at (1 - d) gives {decayed:.2f} against "
        f"the model's own FY2030 excess of {actual_fy2030_excess:.2f}, a "
        f"{residual:+.3%} gap — the capex drivers and the terminal anchor have "
        f"come apart again"
    )

    # The rounding gap in the driver, in the same units as the cause.
    g = drivers.revenue_growth[-1]
    unrounded_driver = (
        anchor * (g + drivers.ppe_depreciation_rate) / (1 + g) / HIST_PPE_CAPEX_SHARE
    )
    rounding = drivers.capex_pct_revenue[-1] - unrounded_driver
    assert abs(rounding) < 0.00005, f"{name}: driver is {rounding:+.6f} off its own level"
    # Rounded up -> more FY2030 capex -> bigger true excess -> negative residual.
    assert (rounding > 0) == (residual < 0), (
        f"{name}: driver rounding {rounding:+.6f} and shield residual {residual:+.5%} "
        f"do not point the way rounding would — the residual is not just rounding"
    )


@pytest.mark.parametrize("name", ["Bear", "Base", "Bull"])
def test_terminal_ppe_anchor_sits_between_the_last_actual_and_the_forecast_peak(name):
    """The owner's ruling, asserted directly.

    FY2025's 38.68% is the top of a rising 28.20 / 33.00 / 38.68 series and is
    not a finished state; the model's own final-year intensity is a
    transitional peak inflated by the capex taper. The post-programme anchor
    must sit strictly between them.
    """
    drivers = SCENARIOS[name]
    model = build_model(GREGGS_HISTORICALS, drivers)
    anchor = terminal_year(model, drivers, GREGGS_HISTORICALS).ppe_intensity
    last = GREGGS_HISTORICALS[-1]
    fy2025_intensity = last.ppe.value / last.revenue.value
    final_forecast_intensity = (
        model.balance_sheet["ppe"][-1] / model.income_statement["revenue"][-1]
    )
    assert fy2025_intensity < anchor < final_forecast_intensity
    # Historical series is rising throughout, which is why its last point is
    # not a steady state. Checked here so the premise is not just asserted.
    intensities = [y.ppe.value / y.revenue.value for y in GREGGS_HISTORICALS]
    assert intensities == sorted(intensities)
    assert intensities[-1] == pytest.approx(fy2025_intensity)


def test_terminal_ppe_anchor_absorbs_one_average_asset_life_of_growth():
    """Pins the derivation: final intensity discounted by (1 + g*) ** (1 / d).

    Re-derives the closed form, which is normally the anti-pattern this file
    avoids — justified here because the number is a judgement rule rather than
    an emergent property, so there is no independent behaviour to check it
    against. The independent checks are the bracketing test above and the
    schedule-iteration tests below, which confirm the anchor is one the real
    fixed-asset schedule actually holds.
    """
    drivers = SCENARIOS["Base"]
    model = build_model(GREGGS_HISTORICALS, drivers)
    anchor = terminal_year(model, drivers, GREGGS_HISTORICALS).ppe_intensity
    final_intensity = (
        model.balance_sheet["ppe"][-1] / model.income_statement["revenue"][-1]
    )
    life = 1.0 / drivers.ppe_depreciation_rate
    assert anchor == pytest.approx(
        final_intensity / (1 + drivers.perpetuity_growth) ** life
    )
    assert anchor == pytest.approx(0.406045, abs=5e-6)
    assert life == pytest.approx(7.028, abs=0.001)


@pytest.mark.parametrize("name", ["Bear", "Base", "Bull"])
def test_the_model_converges_on_the_intensity_it_values(name):
    """Fix round 2, stated as one assertion.

    The explicit period's final capex driver and the perpetuity's anchor have
    to describe the same business. Extend the model's own final year forward
    at its own terminal REVENUE growth on its own terminal capex driver, and
    PP&E/revenue must settle at the anchor the terminal value is struck on.

    Before round 2 it settled at 38.68% while the perpetuity valued ~40.3% —
    the model converged toward one steady state and valued another. The
    covering evidence for that defect was the shield-decay drift measured in
    ``test_the_fy2029_decay_lands_on_the_models_own_fy2030_gap``; this is the
    same claim asserted directly rather than through its symptom.
    """
    from bluebook.assumptions import HIST_PPE_CAPEX_SHARE

    drivers = SCENARIOS[name]
    model = build_model(GREGGS_HISTORICALS, drivers)
    anchor = terminal_year(model, drivers, GREGGS_HISTORICALS).ppe_intensity
    growth = drivers.revenue_growth[-1]
    years = 300
    revenue = [(1.0 + growth) ** t for t in range(1, years + 1)]
    schedule = fixed_assets(
        0.0,
        revenue,
        replace(
            drivers,
            capex_pct_revenue=(
                drivers.capex_pct_revenue[-1] * HIST_PPE_CAPEX_SHARE,
            ) * years,
        ),
    )
    settled = schedule.closing_ppe[-1] / revenue[-1]
    # 3bp of intensity. The residual is entirely the 4-decimal rounding of the
    # capex tuples: a driver rounded by dc moves the settled intensity by
    # dc x HIST_PPE_CAPEX_SHARE x (1 + g) / (g + d), which for the committed
    # tuples (0.2-0.4bp of rounding) is 1.0-2.3bp of intensity. Actuals are
    # Bear +2.05bp, Base -2.10bp, Bull +0.98bp, each signed the same way its
    # driver was rounded.
    assert settled == pytest.approx(anchor, abs=3e-4), (
        f"{name}: the terminal capex driver settles PP&E/revenue at {settled:.4%} "
        f"but the perpetuity is struck on {anchor:.4%}"
    )


def test_rou_anchor_is_still_the_fy2025_actual_because_it_already_plateaued():
    """The PP&E treatment deliberately does not carry across to leases.

    ROU/revenue stepped up once (16.39% -> 19.22%) and has been flat since
    (19.20%), and the forecast never builds a transitional peak over it — the
    whole Base path runs BELOW the FY2025 actual. No build-ahead, nothing to
    absorb, so FY2025 is already the plateau.
    """
    drivers = SCENARIOS["Base"]
    model = build_model(GREGGS_HISTORICALS, drivers)
    terminal = terminal_year(model, drivers, GREGGS_HISTORICALS)
    last = GREGGS_HISTORICALS[-1]
    assert terminal.rou_intensity == pytest.approx(
        last.rou_assets.value / last.revenue.value
    )
    # The premise: flat over the last two actuals, unlike PP&E which is rising.
    rou = [y.rou_assets.value / y.revenue.value for y in GREGGS_HISTORICALS]
    assert rou[2] == pytest.approx(rou[1], rel=0.005)
    assert rou[1] > rou[0] * 1.10
    # And no forecast hump to unwind: every year sits below the anchor.
    forecast = [
        p / r
        for p, r in zip(model.balance_sheet["rou_assets"], model.income_statement["revenue"])
    ]
    assert all(f < terminal.rou_intensity for f in forecast)


def test_excess_ppe_shield_is_a_terminal_date_value_and_is_discounted_as_one():
    drivers = SCENARIOS["Base"]
    model = build_model(GREGGS_HISTORICALS, drivers)
    valuation = value_model(model, drivers, GREGGS_HISTORICALS, GREGGS_SHARE_COUNT.value)
    assert valuation.excess_ppe_tax_shield == pytest.approx(27.1, abs=0.1)
    # Same mid-year factor the terminal value gets: 4.5 years, not 5.
    assert valuation.enterprise_value == pytest.approx(
        enterprise_value(
            valuation.fcf,
            valuation.terminal_value_gordon + valuation.excess_ppe_tax_shield,
            valuation.wacc,
        )
    )


# ---------------------------------------------------------------------------
# Bridge and share price
# ---------------------------------------------------------------------------

def test_bridge_uses_the_opening_balance_sheet_not_the_forecast_closing_one():
    """EV is a present value at the FY2025 year end, so the bridge is too.

    Subtracting FY2030 net debt from a value discounted to FY2025 would
    double-count five years of borrowing that the FCF path already funds.
    """
    drivers = SCENARIOS["Base"]
    model = build_model(GREGGS_HISTORICALS, drivers)
    valuation = value_model(model, drivers, GREGGS_HISTORICALS, GREGGS_SHARE_COUNT.value)
    last = GREGGS_HISTORICALS[-1]
    assert valuation.net_debt == pytest.approx(last.borrowings.value - last.cash.value)
    assert valuation.lease_liabilities == pytest.approx(last.lease_liabilities.value)
    assert valuation.net_debt != pytest.approx(
        model.balance_sheet["borrowings"][-1] - model.balance_sheet["cash"][-1]
    )


def test_greggs_is_in_a_net_cash_position_so_the_bridge_adds_it_back():
    drivers = SCENARIOS["Base"]
    valuation = value_model(
        build_model(GREGGS_HISTORICALS, drivers), drivers, GREGGS_HISTORICALS,
        GREGGS_SHARE_COUNT.value,
    )
    # The second half of this test used to assert
    #   equity_value > enterprise_value - lease_liabilities
    # which is algebraically implied by net_debt < 0 given the bridge, so it
    # tested nothing the first line did not. Removed.
    assert valuation.net_debt < 0


def test_implied_share_price_is_ordered_bull_above_base_above_bear():
    prices = {}
    for name, drivers in SCENARIOS.items():
        model = build_model(GREGGS_HISTORICALS, drivers)
        prices[name] = value_model(
            model, drivers, GREGGS_HISTORICALS, GREGGS_SHARE_COUNT.value
        ).share_price_pence
    assert prices["Bear"] < prices["Base"] < prices["Bull"]


# ---------------------------------------------------------------------------
# The exit-multiple disagreement — flagged for Task 10, not fixed here.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name", ["Bear", "Base", "Bull"])
def test_gordon_implies_a_far_lower_exit_multiple_than_the_driver(name):
    """Documents the open disagreement rather than papering over it.

    `exit_ev_ebitda` is set against pre-IFRS-16 intuition; post-IFRS 16 EBITDA
    adds rent back, so the coherent multiple is structurally lower. Task 10's
    comps sheet supplies the market-based number to reconcile against. If that
    task recalibrates `exit_ev_ebitda`, this test is the one that should
    change, and it should change deliberately.
    """
    drivers = SCENARIOS[name]
    model = build_model(GREGGS_HISTORICALS, drivers)
    valuation = value_model(model, drivers, GREGGS_HISTORICALS, GREGGS_SHARE_COUNT.value)
    implied = valuation.terminal_value_gordon / model.ebitda[-1]
    assert implied < drivers.exit_ev_ebitda
    assert valuation.terminal_value_exit_multiple / valuation.terminal_value_gordon > 1.5
