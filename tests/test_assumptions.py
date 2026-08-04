import pytest

from bluebook.assumptions import FORECAST_YEARS, SCENARIOS



def test_five_forecast_years():
    assert len(FORECAST_YEARS) == 5


def test_three_scenarios():
    assert set(SCENARIOS) == {"Bear", "Base", "Bull"}


def test_scenarios_are_ordered_on_revenue_growth():
    bear, base, bull = SCENARIOS["Bear"], SCENARIOS["Base"], SCENARIOS["Bull"]
    assert bear.revenue_growth[0] < base.revenue_growth[0] < bull.revenue_growth[0]


def test_each_scenario_has_one_rate_per_forecast_year():
    for name, drivers in SCENARIOS.items():
        assert len(drivers.revenue_growth) == len(FORECAST_YEARS), name
        assert len(drivers.gross_margin) == len(FORECAST_YEARS), name


def test_perpetuity_growth_below_wacc_in_every_scenario():
    for name, drivers in SCENARIOS.items():
        assert drivers.perpetuity_growth < drivers.risk_free_rate + 0.02, name


@pytest.mark.parametrize("name", ["Bear", "Base", "Bull"])
def test_rates_are_fractions_not_percentages(name: str):
    drivers = SCENARIOS[name]
    assert 0.0 < drivers.tax_rate < 1.0
    assert all(-0.5 < g < 0.5 for g in drivers.revenue_growth)


# --- Calibration against actuals -------------------------------------------
# These exist because an earlier draft of this plan set opex_pct_revenue to
# 0.50 against a FY2025 actual of ~45.1%, which silently near-halved the
# forecast EBIT margin. Drivers must be anchored to the transcribed
# historicals, and any deliberate divergence must be explicit.

def _last_actual_ratios():
    from bluebook.inputs.greggs import GREGGS_HISTORICALS

    y = GREGGS_HISTORICALS[-1]
    revenue = y.revenue.value
    da = y.depreciation_ppe.value + y.depreciation_rou.value + y.amortisation.value
    ebit = revenue - y.cost_of_sales.value - y.operating_costs.value - da
    return {
        "gross_margin": (revenue - y.cost_of_sales.value) / revenue,
        "opex_pct_revenue": y.operating_costs.value / revenue,
        "da_pct_revenue": da / revenue,
        "ebit_margin": ebit / revenue,
    }


def test_base_gross_margin_anchored_to_last_actual():
    actual = _last_actual_ratios()["gross_margin"]
    assert abs(SCENARIOS["Base"].gross_margin[0] - actual) <= 0.015


def test_base_opex_ratio_anchored_to_last_actual():
    actual = _last_actual_ratios()["opex_pct_revenue"]
    assert abs(SCENARIOS["Base"].opex_pct_revenue[0] - actual) <= 0.015


def test_base_case_year_one_ebit_margin_tracks_last_actual():
    """The base case must not silently re-rate profitability in year one."""
    actual = _last_actual_ratios()
    base = SCENARIOS["Base"]
    implied = base.gross_margin[0] - base.opex_pct_revenue[0] - actual["da_pct_revenue"]
    assert abs(implied - actual["ebit_margin"]) <= 0.015, (
        f"base-case year-1 EBIT margin {implied:.1%} diverges from "
        f"FY2025 actual {actual['ebit_margin']:.1%} by more than 150bp"
    )


# --- Capex path bounds -------------------------------------------------------
# These live here rather than as module-level asserts in assumptions.py
# because (1) `python -O` strips bare asserts, so an import-time assert
# silently stops checking anything under optimised execution, and (2) a
# failing import-time assert surfaces as an opaque crash on `import
# bluebook.assumptions` for any downstream task, with no test name and
# nothing useful in pytest output. Every comparator is derived from
# GREGGS_HISTORICALS, not hardcoded, so none can go stale relative to the
# filings.
#
# They REPLACE two earlier tests — test_base_terminal_capex_within_
# historical_range and test_bear_capex_never_below_historical_low — which
# asserted that terminal capex stays inside [HIST_CAPEX_LOW,
# HIST_CAPEX_HIGH]. That bound was invalid: all three historical years sit
# inside the distribution-centre build programme, so the historical range
# is an expansion-phase range, and requiring a terminal steady-state
# assumption to live inside it assumes the expansion never ends. The tests
# below assert the thing that bound was a bad proxy for — that the terminal
# capex ratio implies a sane long-run asset intensity, and that the
# resulting terminal cash flow is actually positive.


def _steady_state_asset_ratio(capex_pct: float, growth: float, depreciation_rate: float) -> float:
    """Long-run asset/revenue ratio implied by a capex ratio.

    With asset base A, revenue R, capex ratio c and depreciation rate d,
    A_t = A_(t-1)(1 - d) + c*R_t. Holding A/R = p and R growing at g:
        p = p(1 - d)/(1 + g) + c   ->   p = c(1 + g)/(g + d)
    """
    return capex_pct * (1 + growth) / (growth + depreciation_rate)


def _fy2025_ppe_to_revenue() -> float:
    from bluebook.inputs.greggs import GREGGS_HISTORICALS

    y = GREGGS_HISTORICALS[-1]
    return y.ppe.value / y.revenue.value


@pytest.mark.parametrize("name", ["Bear", "Base", "Bull"])
def test_terminal_capex_holds_ppe_to_revenue_near_the_last_actual(name: str):
    """Terminal capex is the ratio capitalised in perpetuity, so what it has
    to be defensible against is the asset intensity it implies forever —
    not the range observed during a build programme.

    The FY2025 actual PP&E/revenue is ~38.7%. A terminal capex ratio that
    implies a wildly different steady state is asserting, silently, that the
    business becomes structurally more (or less) capital-intensive than it
    has ever been. The 5pp band is deliberately wide enough to allow a
    genuine scenario difference — Bull does build ahead of demand — and
    narrow enough to catch the previous 11.00% terminal, which implied 61%+.
    """
    drivers = SCENARIOS[name]
    implied = _steady_state_asset_ratio(
        drivers.capex_pct_revenue[-1],
        drivers.revenue_growth[-1],
        drivers.ppe_depreciation_rate,
    )
    actual = _fy2025_ppe_to_revenue()
    assert abs(implied - actual) <= 0.05, (
        f"{name} terminal capex of {drivers.capex_pct_revenue[-1]:.2%} implies a "
        f"steady-state PP&E/revenue of {implied:.1%} against the FY2025 actual "
        f"{actual:.1%}"
    )


def test_capex_paths_are_ordered_bull_above_base_above_bear():
    """Funding faster growth must cost more, in every year. This is the
    ordering the old Bear floor broke once Bear's path hit HIST_CAPEX_LOW.
    """
    bear, base, bull = SCENARIOS["Bear"], SCENARIOS["Base"], SCENARIOS["Bull"]
    for i, year in enumerate(FORECAST_YEARS):
        assert bear.capex_pct_revenue[i] < base.capex_pct_revenue[i], year
        assert base.capex_pct_revenue[i] < bull.capex_pct_revenue[i], year


def test_capex_tapers_from_the_last_actual_rather_than_stepping_down():
    """The taper is the story — a build programme completing — so year one
    stays at the FY2025 actual and the decline is monotonic from there. A
    scenario that jumped straight to the terminal ratio would be claiming
    the programme stopped the day the forecast starts.
    """
    from bluebook.assumptions import HIST_CAPEX_PCT_REVENUE

    for name, drivers in SCENARIOS.items():
        path = drivers.capex_pct_revenue
        assert path[0] > path[-1], name
        assert all(a >= b for a, b in zip(path, path[1:])), f"{name} not monotonic: {path}"
    assert SCENARIOS["Base"].capex_pct_revenue[0] == pytest.approx(
        HIST_CAPEX_PCT_REVENUE[-1], abs=0.0005
    )


@pytest.mark.parametrize("name", ["Bear", "Base", "Bull"])
def test_terminal_unlevered_free_cash_flow_is_positive(name: str):
    """The test that actually protects the valuation.

    A terminal year whose unlevered FCF is negative would be capitalised
    into a negative terminal value, and no amount of reasoning about capex
    ranges saves a DCF from that. Uses the full linked model rather than
    driver arithmetic, so it also catches a lease or working-capital path
    that consumes the cash the capex taper frees up.
    """
    from bluebook.inputs.greggs import GREGGS_HISTORICALS
    from bluebook.reference import build_model

    drivers = SCENARIOS[name]
    m = build_model(GREGGS_HISTORICALS, drivers)
    ufcf = (
        m.ebit[-1] * (1 - drivers.tax_rate)
        + m.da_total[-1]
        - m.cash_flow["capex"][-1]
        - m.leases.additions[-1]
        - m.working_capital.change_in_nwc[-1]
    )
    assert ufcf > 0, f"{name} terminal unlevered FCF is {ufcf:.1f}"
