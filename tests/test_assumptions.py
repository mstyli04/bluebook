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
