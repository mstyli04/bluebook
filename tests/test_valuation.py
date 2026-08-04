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
    enterprise_value, equity_bridge, implied_share_price,
    terminal_value_exit_multiple, terminal_value_gordon, unlevered_fcf, wacc,
)
from bluebook.valuation import (
    excess_asset_tax_shield, terminal_year, value_model,
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


def test_equity_bridge_subtracts_leases_as_debt():
    """Post-IFRS 16: lease liabilities reduce equity value."""
    with_leases = equity_bridge(ev=1000.0, net_debt=100.0, lease_liabilities=200.0)
    without = equity_bridge(ev=1000.0, net_debt=100.0, lease_liabilities=0.0)
    assert with_leases == pytest.approx(700.0)
    assert without - with_leases == pytest.approx(200.0)


def test_implied_share_price_returns_pence():
    # £700m equity over 100m shares = £7.00 = 700p
    assert implied_share_price(700.0, 100.0) == pytest.approx(700.0)


def test_terminal_value_is_not_an_implausible_share_of_ev():
    model = build_model(GREGGS_HISTORICALS, BASE)
    fcf = unlevered_fcf(model, BASE)
    rate = wacc(BASE)
    tv = terminal_value_gordon(fcf[-1], rate, BASE.perpetuity_growth)
    ev = enterprise_value(fcf, tv, rate)
    discounted_tv = tv / (1 + rate) ** 5
    assert 0.4 < discounted_tv / ev < 0.9


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
    rate = wacc(BASE)
    assert rate == pytest.approx(0.9 * 0.08125 + 0.1 * 0.055 * 0.75)
    assert rate == pytest.approx(0.07725)


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

    Not a restatement of the implementation: it removes D&A from both sides,
    so a wrong D&A series would break it.
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
    # Re-based terminal FCF against the raw final forecast year. Bear's sign is
    # opposite to Base's and Bull's, for the reason given in the test above:
    # its terminal revenue growth is 1.5%, BELOW the 2% perpetuity growth, so
    # re-basing raises its sustaining investment rather than lowering it. Any
    # summary that quotes only the Base figure ("+18%") is quoting a
    # scenario-specific number as if it were a general property.
    [("Bear", -11.7), ("Base", 18.1), ("Bull", 36.8)],
)
def test_rebasing_moves_terminal_fcf_by_the_amount_the_growth_gap_implies(
    name, expected_pct_change
):
    drivers = SCENARIOS[name]
    model = build_model(GREGGS_HISTORICALS, drivers)
    terminal = terminal_year(model, drivers, GREGGS_HISTORICALS)
    raw = unlevered_fcf(model, drivers)[-1]
    assert (terminal.fcf / raw - 1.0) * 100 == pytest.approx(expected_pct_change, abs=0.1)
    # The gap is signed by the growth comparison, not by a fixed direction.
    assert (terminal.fcf > raw) == (drivers.revenue_growth[-1] > drivers.perpetuity_growth)


def test_terminal_year_reproduces_the_briefed_base_case_figures():
    """Anchor on the numbers the brief states, so a silent drift is caught."""
    drivers = SCENARIOS["Base"]
    model = build_model(GREGGS_HISTORICALS, drivers)
    terminal = terminal_year(model, drivers, GREGGS_HISTORICALS)
    assert terminal.capex_pct_revenue == pytest.approx(0.06575, abs=5e-6)
    assert terminal.rou_additions_pct_revenue == pytest.approx(0.03691, abs=5e-6)
    assert terminal.fcf == pytest.approx(149.3, abs=0.1)
    assert unlevered_fcf(model, drivers)[-1] == pytest.approx(126.4, abs=0.1)


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
    year after the terminal year) is discounted k times.
    """
    excess, rate, tax, rate_wacc = 245.9, 0.1423, 0.25, 0.07725
    explicit = 0.0
    carried = excess
    for k in range(1, 600):
        carried *= 1 - rate
        explicit += tax * rate * carried / (1 + rate_wacc) ** k
    assert excess_asset_tax_shield(excess, rate, tax, rate_wacc) == pytest.approx(explicit)


@pytest.mark.parametrize("name", ["Bear", "Base", "Bull"])
def test_excess_ppe_decays_from_fy2029_onto_the_models_own_fy2030_gap(name):
    """Validates using the FY2029 excess with a (1 - d) decay to FY2030.

    The closed form assumes the excess decays purely at the depreciation rate,
    i.e. that FY2030 capex is exactly sustaining. It is: each scenario's final
    capex driver was derived to hold PP&E/revenue flat at its own terminal
    revenue growth, and FY2029 -> FY2030 grows at exactly that rate. So the
    decayed FY2029 excess should land on the model's actual FY2030 excess.
    """
    drivers = SCENARIOS[name]
    model = build_model(GREGGS_HISTORICALS, drivers)
    valuation = value_model(model, drivers, GREGGS_HISTORICALS, GREGGS_SHARE_COUNT.value)
    anchor = valuation.terminal.ppe_intensity
    revenue = model.income_statement["revenue"]
    actual_fy2030_excess = model.balance_sheet["ppe"][-1] - anchor * revenue[-1]
    decayed = valuation.excess_ppe * (1 - drivers.ppe_depreciation_rate)
    assert decayed == pytest.approx(actual_fy2030_excess, rel=0.005)


def test_excess_ppe_shield_is_a_terminal_date_value_and_is_discounted_as_one():
    drivers = SCENARIOS["Base"]
    model = build_model(GREGGS_HISTORICALS, drivers)
    valuation = value_model(model, drivers, GREGGS_HISTORICALS, GREGGS_SHARE_COUNT.value)
    assert valuation.excess_ppe_tax_shield == pytest.approx(34.2, abs=0.1)
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
    assert valuation.net_debt < 0
    assert valuation.equity_value > valuation.enterprise_value - valuation.lease_liabilities


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
