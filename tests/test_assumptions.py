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
    """Asserts against the real computed WACC, which the name always promised.

    Until Task 9 built ``wacc()`` this checked ``risk_free_rate + 2%`` as a
    proxy. Note what the change does: the proxy bound was 6.0% against a true
    WACC of 7.725%, so this assertion is now LOOSER, not tighter. It is
    nonetheless the right one — a Gordon perpetuity with g >= WACC is
    infinite, and that, not an arbitrary spread over gilts, is the hard bound.
    The proxy also ignored beta, the equity risk premium and the debt weight
    entirely, so it would not have moved if any of them changed; this does.
    """
    from bluebook.valuation import wacc

    for name, drivers in SCENARIOS.items():
        assert drivers.perpetuity_growth < wacc(drivers), name


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


def _steady_state_asset_ratio(
    capex_pct: float,
    growth: float,
    depreciation_rate: float,
    share_reaching_asset: float = 1.0,
) -> float:
    """Long-run asset/revenue ratio implied by a capex ratio.

    With asset base A, revenue R, capex ratio c and depreciation rate d,
    A_t = A_(t-1)(1 - d) + c*R_t. Holding A/R = p and R growing at g:
        p = p(1 - d)/(1 + g) + c   ->   p = c(1 + g)/(g + d)

    ``share_reaching_asset`` is the fraction of the driver ratio that
    actually lands on this asset base. It defaults to 1.0, which is correct
    for ROU additions — ``leases()`` receives the whole of
    ``rou_additions_pct_revenue``. It is NOT correct for PP&E:
    ``capex_pct_revenue`` is a total-capex ratio and ``reference.py`` routes
    only ``HIST_PPE_CAPEX_SHARE`` of it into the fixed-asset schedule. An
    earlier version of this helper had no such parameter and so reproduced
    the same unsplit formula the driver derivation used, which is exactly
    why it certified a terminal capex ratio that in fact starved the PP&E
    line by ~2.4pp of steady-state intensity. A test that shares a blind
    spot with the thing it checks is not a test.
    """
    return capex_pct * share_reaching_asset * (1 + growth) / (growth + depreciation_rate)


def _fy2025_ppe_to_revenue() -> float:
    from bluebook.inputs.greggs import GREGGS_HISTORICALS

    y = GREGGS_HISTORICALS[-1]
    return y.ppe.value / y.revenue.value


def _terminal_ppe_anchor(name: str) -> float:
    """The PP&E/revenue intensity the perpetuity is actually struck on.

    Fix round 2 recalibrated the terminal capex drivers onto this, replacing
    the FY2025 actual. The two are different numbers — ~40.2-41.2% against
    38.68% — and the whole point of that round was that the model must
    converge on the intensity it values. So the tests below compare against
    this, not against the FY2025 actual: a test still pinned to 38.68% would
    now be asserting the very inconsistency the round removed.

    It is read from ``valuation`` rather than restated here so there is one
    definition of the anchor in the codebase. That makes these tests a check
    of the FIXED POINT — capex sets the FY2030 balance sheet, which sets the
    anchor, which must set that same capex back again.
    """
    from bluebook.inputs.greggs import GREGGS_HISTORICALS
    from bluebook.reference import build_model
    from bluebook.valuation import terminal_ppe_intensity

    drivers = SCENARIOS[name]
    return terminal_ppe_intensity(build_model(GREGGS_HISTORICALS, drivers), drivers)


_CONVERGENCE_YEARS = 200


def _iterated_steady_state_ppe_to_revenue(name: str) -> tuple[float, float]:
    """Run the REAL fixed-asset schedule to convergence at terminal drivers.

    Feeds ``fixed_assets()`` a constant-growth revenue path 200 years long
    at the scenario's terminal growth rate and terminal capex ratio, routed
    through ``HIST_PPE_CAPEX_SHARE`` exactly as ``reference.py`` routes it,
    and returns (converged PP&E/revenue, last year-on-year move in it).

    Deliberately starts from opening PP&E of ZERO. The FY2025 actual opening
    balance is already at the anchor being tested, so starting there would
    let a wrong capex ratio hide inside a right starting point; starting at
    zero makes the answer a pure function of the drivers. The roll-forward
    contracts by (1 - d)/(1 + g) ~ 0.80-0.82 per year, so 200 years is ~1e19
    of convergence — the returned move is asserted to confirm it, rather
    than assumed.

    Revenue starts at 1.0 because PP&E/revenue is scale-free; only the
    growth rate matters.
    """
    from dataclasses import replace

    from bluebook.assumptions import HIST_PPE_CAPEX_SHARE
    from bluebook.schedules.fixed_assets import fixed_assets

    drivers = SCENARIOS[name]
    growth = drivers.revenue_growth[-1]
    revenue = [(1.0 + growth) ** (i + 1) for i in range(_CONVERGENCE_YEARS)]
    ppe_drivers = replace(
        drivers,
        capex_pct_revenue=(
            drivers.capex_pct_revenue[-1] * HIST_PPE_CAPEX_SHARE,
        )
        * _CONVERGENCE_YEARS,
    )
    schedule = fixed_assets(0.0, revenue, ppe_drivers)
    ratios = [p / r for p, r in zip(schedule.closing_ppe, revenue)]
    return ratios[-1], abs(ratios[-1] - ratios[-2])


@pytest.mark.parametrize("name", ["Bear", "Base", "Bull"])
def test_terminal_capex_holds_ppe_to_revenue_when_the_schedule_is_iterated(name: str):
    """Terminal capex is the ratio capitalised in perpetuity, so what it has
    to be defensible against is the asset intensity it implies forever —
    not the range observed during a build programme. That intensity is the
    post-programme anchor the terminal value is struck on (~40.2-41.2%
    depending on scenario); a terminal capex ratio implying a materially
    different steady state means the model converges toward one business and
    values another.

    This measures that steady state by ITERATING ``fixed_assets()`` forward
    to convergence, not by re-deriving p = c(1 + g)/(g + d). That is the
    whole point of the test. The previous version of it evaluated the same
    closed form, with the same derived constants, as the driver comment it
    was checking — algebraically one assertion with two tolerances — so when
    the derivation itself was wrong (the 7.00% ungrossed terminal), the test
    reproduced the error and passed. A test that shares its subject's
    assumptions cannot catch that class of defect. Running the real schedule
    shares no assumption with the formula beyond the drivers themselves.

    The tight closed-form test below is kept alongside it deliberately: this
    one checks the implementation, that one checks the derivation, and if
    the two ever disagree that is a finding, not noise.

    The 1pp band is ~18x the widest drift the committed drivers actually
    produce (5.6bp, Bull) and is checked against two mutations rather than
    assumed to catch them: terminal capex reverted to the 7.00% ungrossed
    figure (2.1pp of drift) and HIST_PPE_CAPEX_SHARE forced to 1.0 (2.7pp).
    Both fail it. The pre-round-1 11.00% terminal (19pp) fails it by miles.
    """
    converged, last_move = _iterated_steady_state_ppe_to_revenue(name)
    assert last_move < 1e-9, (
        f"{name}: the iterated PP&E schedule had not converged after "
        f"{_CONVERGENCE_YEARS} years — last move {last_move:.2e}"
    )
    anchor = _terminal_ppe_anchor(name)
    assert abs(converged - anchor) <= 0.01, (
        f"{name} terminal capex of {SCENARIOS[name].capex_pct_revenue[-1]:.2%} drives "
        f"the fixed-asset schedule to a steady-state PP&E/revenue of {converged:.2%} "
        f"against the terminal anchor {anchor:.2%} the perpetuity is struck on"
    )


@pytest.mark.parametrize("name", ["Bear", "Base", "Bull"])
def test_iterated_schedule_agrees_with_the_closed_form_it_is_derived_from(name: str):
    """Cross-check: the algebra and the code must describe the same thing.

    The drivers are derived from p = c(1 + g)/(g + d), which assumes the
    schedule rolls forward as A_t = A_(t-1)(1 - d) + c*R_t with depreciation
    struck on the OPENING balance. ``fixed_assets()`` is free to change; if
    it ever stops matching that recurrence — depreciating the closing
    balance, say, or capitalising mid-year — every terminal driver in this
    module silently becomes the wrong answer to a question nobody restated.
    This is the test that would say so.
    """
    from bluebook.assumptions import HIST_PPE_CAPEX_SHARE

    converged, _ = _iterated_steady_state_ppe_to_revenue(name)
    drivers = SCENARIOS[name]
    closed_form = _steady_state_asset_ratio(
        drivers.capex_pct_revenue[-1],
        drivers.revenue_growth[-1],
        drivers.ppe_depreciation_rate,
        share_reaching_asset=HIST_PPE_CAPEX_SHARE,
    )
    assert converged == pytest.approx(closed_form, rel=1e-9), (
        f"{name}: iterating fixed_assets() converges to {converged:.6%} but the "
        f"closed form the drivers are derived from says {closed_form:.6%} — the "
        f"schedule and the derivation no longer describe the same roll-forward"
    )


@pytest.mark.parametrize("name", ["Bear", "Base", "Bull"])
def test_terminal_capex_equals_its_own_grossed_up_sustaining_level(name: str):
    """Reproduces the derivation in the BASE.capex_pct_revenue comment, in
    full, from GREGGS_HISTORICALS — so the stated derivation and the tuple
    cannot disagree.

    The iterated test above measures where the schedule actually settles and
    allows 1pp of drift, which is the right band for "is this ratio sane"
    but still wide enough that a driver could sit ~80-105bp off its own
    stated derivation and pass. This one is tight: each scenario's terminal
    must be the sustaining level at its OWN terminal growth and its OWN
    post-programme anchor, grossed up for the intangible split, to within 5bp
    of rounding (the committed tuples sit 0.2-0.4bp off). It is the test that
    catches a comment claiming 7.41% over a tuple that says 7.00%.

    Since round 2 this is also the fixed-point test: the anchor is read off
    the model built from these very drivers, so it asserts that raising capex
    to sustain the anchor does not move the anchor out from under it.

    The two are not redundant. This one asks whether the number matches the
    stated derivation; the iterated one asks whether the derivation matches
    the model. Round 3's defect passed a test of the first kind that had
    been written as though it were the second.
    """
    from bluebook.assumptions import HIST_PPE_CAPEX_SHARE

    drivers = SCENARIOS[name]
    g = drivers.revenue_growth[-1]
    sustaining_ppe_capex = (
        _terminal_ppe_anchor(name) * (g + drivers.ppe_depreciation_rate) / (1 + g)
    )
    expected_total_capex = sustaining_ppe_capex / HIST_PPE_CAPEX_SHARE
    assert drivers.capex_pct_revenue[-1] == pytest.approx(expected_total_capex, abs=0.0005), (
        f"{name} terminal capex is {drivers.capex_pct_revenue[-1]:.4%} but its own "
        f"derivation gives {expected_total_capex:.4%}"
    )


def _fy2025_rou_to_revenue() -> float:
    from bluebook.inputs.greggs import GREGGS_HISTORICALS

    y = GREGGS_HISTORICALS[-1]
    return y.rou_assets.value / y.revenue.value


@pytest.mark.parametrize("name", ["Bear", "Base", "Bull"])
def test_terminal_rou_additions_hold_rou_to_revenue_near_the_last_actual(name: str):
    """The leased estate is governed by the same principle as the owned one.

    Greggs runs one shop estate across two balance sheet lines. Setting
    terminal capex to hold PP&E/revenue flat while letting ROU/revenue drift
    would mean two asset bases under two different rules, which is exactly
    the asymmetry this test exists to prevent. The 1pp band still catches
    the previous 3.40% terminal, which implied 16.1% against a 19.2%
    actual. This one evaluates the closed form directly rather than
    iterating leases(): unlike capex, the whole of
    rou_additions_pct_revenue reaches the ROU line, so there is no split for
    a closed-form check to be blind to — and the ROU terminals are derived
    directly rather than shifted, so it is the derivation that needs
    policing here.
    """
    drivers = SCENARIOS[name]
    implied = _steady_state_asset_ratio(
        drivers.rou_additions_pct_revenue[-1],
        drivers.revenue_growth[-1],
        drivers.rou_depreciation_rate,
    )
    actual = _fy2025_rou_to_revenue()
    assert abs(implied - actual) <= 0.01, (
        f"{name} terminal ROU additions of {drivers.rou_additions_pct_revenue[-1]:.2%} "
        f"imply a steady-state ROU/revenue of {implied:.1%} against the FY2025 actual "
        f"{actual:.1%}"
    )


def test_both_asset_bases_are_set_on_the_same_principle():
    """Whatever the two terminal ratios are, each must be the level that
    sustains its own asset base at its own anchor.

    Measured against each base's OWN anchor rather than against a common one.
    That distinction became load-bearing in fix round 2: the PP&E anchor moved
    to a derived post-programme intensity while the ROU anchor stayed at the
    FY2025 actual (ROU/revenue had already plateaued, so there was no
    build-ahead to absorb). Different anchors, same rule — and it is the rule
    this test polices, not the anchors.
    """
    from bluebook.assumptions import HIST_PPE_CAPEX_SHARE

    for name, drivers in SCENARIOS.items():
        ppe_implied = _steady_state_asset_ratio(
            drivers.capex_pct_revenue[-1],
            drivers.revenue_growth[-1],
            drivers.ppe_depreciation_rate,
            share_reaching_asset=HIST_PPE_CAPEX_SHARE,
        )
        rou_implied = _steady_state_asset_ratio(
            drivers.rou_additions_pct_revenue[-1],
            drivers.revenue_growth[-1],
            drivers.rou_depreciation_rate,
        )
        ppe_drift = ppe_implied - _terminal_ppe_anchor(name)
        rou_drift = rou_implied - _fy2025_rou_to_revenue()
        assert abs(ppe_drift - rou_drift) <= 0.02, (
            f"{name}: PP&E intensity drifts {ppe_drift:+.1%} from its terminal anchor "
            f"while ROU drifts {rou_drift:+.1%} from the FY2025 actual — the two asset "
            f"bases are being governed by different rules"
        )
        # Both should be near zero, not merely near each other: "same rule"
        # has to mean each ratio actually sustains its own base, not that the
        # two miss by the same amount in the same direction.
        assert abs(ppe_drift) <= 0.005, f"{name}: PP&E drift {ppe_drift:+.2%}"
        assert abs(rou_drift) <= 0.005, f"{name}: ROU drift {rou_drift:+.2%}"


def test_assumptions_lease_rate_matches_the_lease_schedule():
    """The one duplicated derivation in the codebase, guarded.

    ``assumptions.LEASE_DISCOUNT_RATE`` re-derives what
    ``schedules/leases.py`` already derives, because that module does
    ``from bluebook.assumptions import Drivers`` and importing it back would
    make the pair import-order-dependent — fine if assumptions is imported
    first, an ImportError if leases is. This test is what makes the
    duplication safe: if either derivation moves, they stop matching here.
    """
    from bluebook.assumptions import LEASE_DISCOUNT_RATE as ASSUMPTIONS_RATE
    from bluebook.schedules.leases import LEASE_DISCOUNT_RATE as SCHEDULE_RATE

    assert ASSUMPTIONS_RATE == SCHEDULE_RATE


def test_blended_cost_of_debt_sits_between_its_two_components():
    """The WACC debt base is mostly leases, so the blend must sit near the
    lease rate, not near the RCF rate.

    Pins the direction as well as the value: a blend that came out above the
    RCF rate, or below the lease rate, would be a weighting error, and one
    that came out near the midpoint would mean the weights had been dropped.
    """
    from bluebook.assumptions import (
        BLENDED_COST_OF_DEBT,
        LEASE_DISCOUNT_RATE,
        RCF_COST_OF_DEBT,
    )

    assert LEASE_DISCOUNT_RATE < BLENDED_COST_OF_DEBT < RCF_COST_OF_DEBT
    # £449.8m of leases against £25.0m of RCF, so the blend sits within 8bp
    # of the lease rate, not near the 4.76% midpoint.
    assert BLENDED_COST_OF_DEBT - LEASE_DISCOUNT_RATE < 0.0008
    assert all(d.cost_of_debt == BLENDED_COST_OF_DEBT for d in SCENARIOS.values())
    # The revolver is deliberately NOT blended: it really does draw at the
    # RCF rate.
    assert all(d.interest_rate_debt == RCF_COST_OF_DEBT for d in SCENARIOS.values())


def test_investment_paths_are_ordered_bull_above_base_above_bear():
    """Funding faster growth must cost more, in every year, on both the
    owned and the leased estate. This is the ordering the old Bear capex
    floor broke once its path hit HIST_CAPEX_LOW, and which the ROU paths
    did not express at all before round 2 (all three scenarios shared one
    path, so a bull case opened shops at the same rate as a bear case).
    """
    bear, base, bull = SCENARIOS["Bear"], SCENARIOS["Base"], SCENARIOS["Bull"]
    for i, year in enumerate(FORECAST_YEARS):
        assert bear.capex_pct_revenue[i] < base.capex_pct_revenue[i], year
        assert base.capex_pct_revenue[i] < bull.capex_pct_revenue[i], year
        assert bear.rou_additions_pct_revenue[i] < base.rou_additions_pct_revenue[i], year
        assert base.rou_additions_pct_revenue[i] < bull.rou_additions_pct_revenue[i], year


def test_terminal_rou_additions_stay_inside_the_observed_range():
    """4.06% is above the FY2025 actual of 3.48%, so the path glides up. That
    is only defensible because FY2025's lease signings were the low end of a
    volatile run — this pins that claim to the data rather than the comment.
    """
    from bluebook.assumptions import HIST_ROU_ADDITIONS_PCT_REVENUE

    terminal = SCENARIOS["Base"].rou_additions_pct_revenue[-1]
    assert min(HIST_ROU_ADDITIONS_PCT_REVENUE) <= terminal <= max(
        HIST_ROU_ADDITIONS_PCT_REVENUE
    )
    from bluebook.inputs.greggs import GREGGS_HISTORICALS

    three_year_aggregate = sum(y.rou_additions.value for y in GREGGS_HISTORICALS) / sum(
        y.revenue.value for y in GREGGS_HISTORICALS
    )
    assert terminal < three_year_aggregate


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
