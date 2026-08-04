import pytest

from bluebook.assumptions import SCENARIOS
from bluebook.inputs.greggs import GREGGS_HISTORICALS
from bluebook.schedules.fixed_assets import fixed_assets
from bluebook.schedules.leases import leases
from bluebook.schedules.working_capital import working_capital

BASE = SCENARIOS["Base"]
REVENUE = [2000.0, 2100.0, 2200.0, 2300.0, 2400.0]
COGS = [760.0, 798.0, 836.0, 874.0, 912.0]


def test_working_capital_uses_day_counts():
    wc = working_capital(REVENUE, COGS, BASE)
    assert wc.inventories[0] == pytest.approx(COGS[0] * BASE.inventory_days / 365)
    assert wc.receivables[0] == pytest.approx(REVENUE[0] * BASE.receivable_days / 365)
    assert wc.payables[0] == pytest.approx(COGS[0] * BASE.payable_days / 365)


def test_net_working_capital_is_current_assets_less_payables():
    wc = working_capital(REVENUE, COGS, BASE)
    assert wc.net_working_capital[0] == pytest.approx(
        wc.inventories[0] + wc.receivables[0] - wc.payables[0]
    )


def test_change_in_nwc_first_year_measures_against_opening():
    wc = working_capital(REVENUE, COGS, BASE, opening_nwc=50.0)
    assert wc.change_in_nwc[0] == pytest.approx(wc.net_working_capital[0] - 50.0)
    assert wc.change_in_nwc[1] == pytest.approx(
        wc.net_working_capital[1] - wc.net_working_capital[0]
    )


def test_ppe_rolls_forward():
    fa = fixed_assets(opening_ppe=1000.0, revenue=REVENUE, drivers=BASE)
    assert fa.capex[0] == pytest.approx(REVENUE[0] * BASE.capex_pct_revenue[0])
    assert fa.depreciation[0] == pytest.approx(1000.0 * BASE.ppe_depreciation_rate)
    assert fa.closing_ppe[0] == pytest.approx(1000.0 + fa.capex[0] - fa.depreciation[0])
    assert fa.depreciation[1] == pytest.approx(fa.closing_ppe[0] * BASE.ppe_depreciation_rate)


def test_lease_liability_rolls_forward_on_additions_and_principal():
    # Interest accrued on the lease liability and interest paid in cash are
    # the same figure in the same period under IFRS 16 (Greggs' FY2025 cash
    # flow statement, p.132, shows "Interest paid on lease liabilities" and
    # "Repayment of principal on lease liabilities" as separate cash lines
    # that net to zero against the balance), so the liability roll-forward
    # does NOT capitalise interest. Capitalising it here previously drove
    # the ROU-to-liability gap from a historical ~-7% to -9% out to -24%+
    # over a five-year forecast (see
    # test_rou_asset_and_liability_stay_within_historical_band below).
    lz = leases(opening_rou=800.0, opening_liability=850.0, revenue=REVENUE, drivers=BASE)
    assert lz.closing_rou[0] == pytest.approx(800.0 + lz.additions[0] - lz.depreciation[0])
    assert lz.closing_liability[0] == pytest.approx(
        850.0 + lz.additions[0] - lz.principal_paid[0]
    )
    # Interest is still computed and returned (Task 8 needs it for the P&L
    # finance cost line) — only its effect on the liability balance changed.
    assert lz.interest[0] == pytest.approx(850.0 * BASE.cost_of_debt)


def test_rou_asset_and_liability_stay_within_historical_band():
    """Regression guard, tightened against a real band instead of a loose
    50% ceiling: Greggs' actual ROU-to-liability gap (rou_assets vs.
    lease_liabilities, both from GREGGS_HISTORICALS) has held stable at
    roughly -7% to -8% across FY2023-25. Forecasting forward off the real
    FY2025 closing balances should stay in the same neighbourhood; a
    regression that capitalises interest into the liability (see
    test_lease_liability_rolls_forward_on_additions_and_principal) drives
    the gap to roughly -13% in year one and -24% by year five, which this
    bound catches immediately.
    """
    historical_gap_pcts = [
        (y.rou_assets.value - y.lease_liabilities.value) / y.lease_liabilities.value
        for y in GREGGS_HISTORICALS
    ]
    lo, hi = min(historical_gap_pcts), max(historical_gap_pcts)
    # Modest margin for multi-year forecast drift beyond the 3-year
    # historical range (a single-digit number of points, not the ~15-30pp
    # a capitalised-interest regression would produce).
    margin = 0.03

    fy2025 = GREGGS_HISTORICALS[-1]
    revenue = []
    r = fy2025.revenue.value
    for g in BASE.revenue_growth:
        r *= 1 + g
        revenue.append(r)

    lz = leases(
        opening_rou=fy2025.rou_assets.value,
        opening_liability=fy2025.lease_liabilities.value,
        revenue=revenue,
        drivers=BASE,
    )
    for rou, liability in zip(lz.closing_rou, lz.closing_liability):
        gap_pct = (rou - liability) / liability
        assert lo - margin <= gap_pct <= hi + margin
