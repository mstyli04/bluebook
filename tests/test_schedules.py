import pytest

from bluebook.assumptions import SCENARIOS
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


def test_lease_liability_rolls_forward_with_interest_and_principal():
    lz = leases(opening_rou=800.0, opening_liability=850.0, revenue=REVENUE, drivers=BASE)
    assert lz.closing_rou[0] == pytest.approx(800.0 + lz.additions[0] - lz.depreciation[0])
    assert lz.closing_liability[0] == pytest.approx(
        850.0 + lz.additions[0] + lz.interest[0] - lz.principal_paid[0]
    )


def test_rou_asset_and_liability_stay_within_sight_of_each_other():
    """Sanity guard: a runaway gap means the roll-forward is wrong."""
    lz = leases(opening_rou=800.0, opening_liability=850.0, revenue=REVENUE, drivers=BASE)
    for rou, liability in zip(lz.closing_rou, lz.closing_liability):
        assert abs(rou - liability) < 0.5 * max(rou, liability)
