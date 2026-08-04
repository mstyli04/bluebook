import pytest

from bluebook.assumptions import SCENARIOS
from bluebook.inputs.greggs import GREGGS_HISTORICALS
from bluebook.reference import build_model

SCENARIO_NAMES = ["Bear", "Base", "Bull"]


@pytest.fixture
def model():
    return build_model(GREGGS_HISTORICALS, SCENARIOS["Base"])


@pytest.mark.parametrize("name", SCENARIO_NAMES)
def test_balance_sheet_balances_every_forecast_year(name: str):
    m = build_model(GREGGS_HISTORICALS, SCENARIOS[name])
    for i in range(5):
        assets = m.balance_sheet["total_assets"][i]
        claims = m.balance_sheet["total_liabilities_and_equity"][i]
        assert assets == pytest.approx(claims, abs=0.01), f"{name} year {i}"


@pytest.mark.parametrize("name", SCENARIO_NAMES)
def test_cash_flow_ties_to_balance_sheet_cash(name: str):
    m = build_model(GREGGS_HISTORICALS, SCENARIOS[name])
    for i in range(5):
        closing = m.cash_flow["closing_cash"][i]
        assert closing == pytest.approx(m.balance_sheet["cash"][i], abs=0.01)


def test_ebitda_excludes_all_depreciation_and_amortisation(model):
    for i in range(5):
        assert model.ebitda[i] == pytest.approx(
            model.ebit[i] + model.da_total[i], abs=0.01
        )


def test_retained_earnings_move_by_net_income_less_dividends(model):
    for i in range(1, 5):
        movement = (
            model.balance_sheet["equity"][i] - model.balance_sheet["equity"][i - 1]
        )
        expected = model.net_income[i] - model.cash_flow["dividends_paid"][i]
        assert movement == pytest.approx(expected, abs=0.01)


def test_bull_case_produces_higher_revenue_than_bear():
    bull = build_model(GREGGS_HISTORICALS, SCENARIOS["Bull"])
    bear = build_model(GREGGS_HISTORICALS, SCENARIOS["Bear"])
    assert bull.income_statement["revenue"][-1] > bear.income_statement["revenue"][-1]


def test_first_forecast_year_grows_off_the_last_historical(model):
    last_actual = GREGGS_HISTORICALS[-1].revenue.value
    expected = last_actual * (1 + SCENARIOS["Base"].revenue_growth[0])
    assert model.income_statement["revenue"][0] == pytest.approx(expected, abs=0.01)


def test_no_line_item_is_silently_missing(model):
    for statement in (model.income_statement, model.balance_sheet, model.cash_flow):
        for key, series in statement.items():
            assert len(series) == 5, key
            assert all(v is not None for v in series), key


# ---------------------------------------------------------------------------
# Additional tests beyond the brief's set.
#
# The brief's own test_balance_sheet_balances_every_forecast_year is only as
# strong as the way the two totals are built: if either total were derived
# from the other, or carried an "other"/plug line absorbing a residual, it
# would still pass. The tests below close that hole, and pin the three
# linkage decisions this task was most likely to get wrong (opening NWC,
# opening balances, cash-flow footing).
# ---------------------------------------------------------------------------

LAST = GREGGS_HISTORICALS[-1]

ASSET_LINES = [
    "ppe",
    "rou_assets",
    "intangibles",
    "inventories",
    "trade_receivables",
    "cash",
    "other_assets",
]
CLAIM_LINES = [
    "trade_payables",
    "lease_liabilities",
    "borrowings",
    "other_liabilities",
    "equity",
]


@pytest.mark.parametrize("name", SCENARIO_NAMES)
def test_balance_sheet_totals_are_the_sum_of_their_own_components(name: str):
    """No plug: each total foots to its itemised lines independently.

    Together with test_balance_sheet_balances_every_forecast_year this means
    the balance sheet balances because the linkage is right, not because a
    total was set equal to the other side or a residual was parked in an
    "other" line.
    """
    m = build_model(GREGGS_HISTORICALS, SCENARIOS[name])
    for i in range(5):
        assets = sum(m.balance_sheet[k][i] for k in ASSET_LINES)
        claims = sum(m.balance_sheet[k][i] for k in CLAIM_LINES)
        assert m.balance_sheet["total_assets"][i] == pytest.approx(assets, abs=1e-9)
        assert m.balance_sheet["total_liabilities_and_equity"][i] == pytest.approx(
            claims, abs=1e-9
        )


def test_other_asset_and_liability_lines_are_held_flat_not_used_as_plugs(model):
    """The two "other" lines are the obvious place to hide a residual."""
    for i in range(5):
        assert model.balance_sheet["other_assets"][i] == pytest.approx(
            LAST.other_assets.value, abs=1e-9
        )
        assert model.balance_sheet["other_liabilities"][i] == pytest.approx(
            LAST.other_liabilities.value, abs=1e-9
        )


@pytest.mark.parametrize("name", SCENARIO_NAMES)
def test_year_one_working_capital_movement_uses_the_actual_opening_balances(name: str):
    """Guards the opening_nwc=0.0 default trap in working_capital().

    With the default, change_in_nwc[0] would be the whole FY2026 NWC balance
    (~-156) rather than the movement off FY2025's actual (~-9).
    """
    m = build_model(GREGGS_HISTORICALS, SCENARIOS[name])
    opening_nwc = (
        LAST.inventories.value + LAST.trade_receivables.value - LAST.trade_payables.value
    )
    closing_nwc = (
        m.balance_sheet["inventories"][0]
        + m.balance_sheet["trade_receivables"][0]
        - m.balance_sheet["trade_payables"][0]
    )
    assert m.cash_flow["change_in_working_capital"][0] == pytest.approx(
        closing_nwc - opening_nwc, abs=1e-9
    )


def test_first_forecast_year_rolls_off_the_last_historical_balance_sheet(model):
    """Every opening balance is the last actual, not a fresh start."""
    assert model.balance_sheet["ppe"][0] == pytest.approx(
        LAST.ppe.value + model.cash_flow["capex"][0]
        - model.income_statement["depreciation_ppe"][0],
        abs=1e-9,
    )
    assert model.balance_sheet["rou_assets"][0] == pytest.approx(
        LAST.rou_assets.value + model.leases.additions[0]
        - model.income_statement["depreciation_rou"][0],
        abs=1e-9,
    )
    assert model.balance_sheet["lease_liabilities"][0] == pytest.approx(
        LAST.lease_liabilities.value + model.leases.additions[0]
        - model.cash_flow["lease_principal_paid"][0],
        abs=1e-9,
    )
    assert model.balance_sheet["intangibles"][0] == pytest.approx(
        LAST.intangibles.value - model.income_statement["amortisation"][0], abs=1e-9
    )
    assert model.balance_sheet["equity"][0] == pytest.approx(
        LAST.equity.value + model.net_income[0] - model.cash_flow["dividends_paid"][0],
        abs=1e-9,
    )
    assert model.cash_flow["opening_cash"][0] == pytest.approx(LAST.cash.value, abs=1e-9)
    assert model.debt.opening[0] == pytest.approx(LAST.borrowings.value, abs=1e-9)


@pytest.mark.parametrize("name", SCENARIO_NAMES)
def test_cash_flow_statement_foots(name: str):
    """Every cash flow line adds up to the movement in cash, with nothing left over."""
    m = build_model(GREGGS_HISTORICALS, SCENARIOS[name])
    cf = m.cash_flow
    for i in range(5):
        operating = (
            cf["ebitda"][i] - cf["change_in_working_capital"][i] - cf["tax_paid"][i]
        )
        assert cf["cash_from_operations"][i] == pytest.approx(operating, abs=1e-9)
        net = (
            cf["cash_from_operations"][i]
            - cf["capex"][i]
            - cf["lease_interest_paid"][i]
            - cf["lease_principal_paid"][i]
            - cf["debt_interest_paid"][i]
            - cf["debt_repayment"][i]
            + cf["revolver_draw"][i]
            - cf["dividends_paid"][i]
        )
        assert cf["net_change_in_cash"][i] == pytest.approx(net, abs=1e-9)
        assert cf["closing_cash"][i] == pytest.approx(
            cf["opening_cash"][i] + cf["net_change_in_cash"][i], abs=1e-9
        )
        if i:
            assert cf["opening_cash"][i] == pytest.approx(cf["closing_cash"][i - 1], abs=1e-9)


@pytest.mark.parametrize("name", SCENARIO_NAMES)
def test_cash_flow_agrees_with_the_debt_schedules_own_cash_balance(name: str):
    """Independent cross-check: the statement is built from its components,
    the debt schedule tracks cash itself, and the two must agree."""
    m = build_model(GREGGS_HISTORICALS, SCENARIOS[name])
    for i in range(5):
        assert m.cash_flow["closing_cash"][i] == pytest.approx(
            m.debt.cash_balance[i], abs=1e-6
        )


def test_finance_costs_carry_lease_interest_as_well_as_debt_interest(model):
    """Lease interest does not capitalise into the liability, but it is a
    real P&L finance cost and must reach profit before tax."""
    for i in range(5):
        assert model.income_statement["lease_interest"][i] == pytest.approx(
            model.leases.interest[i], abs=1e-9
        )
        assert model.income_statement["lease_interest"][i] > 0
        assert model.income_statement["profit_before_tax"][i] == pytest.approx(
            model.ebit[i]
            - model.income_statement["lease_interest"][i]
            - model.income_statement["debt_interest"][i],
            abs=1e-9,
        )


@pytest.mark.parametrize("name", SCENARIO_NAMES)
def test_amortisation_is_a_constant_share_of_revenue_from_the_last_actual(name: str):
    m = build_model(GREGGS_HISTORICALS, SCENARIOS[name])
    rate = LAST.amortisation.value / LAST.revenue.value
    for i in range(5):
        assert m.income_statement["amortisation"][i] == pytest.approx(
            m.income_statement["revenue"][i] * rate, abs=1e-9
        )
        assert m.balance_sheet["intangibles"][i] > 0


@pytest.mark.parametrize("name", SCENARIO_NAMES)
def test_tax_and_dividends_are_consistent_between_the_three_statements(name: str):
    m = build_model(GREGGS_HISTORICALS, SCENARIOS[name])
    drivers = SCENARIOS[name]
    for i in range(5):
        assert m.cash_flow["tax_paid"][i] == pytest.approx(
            m.income_statement["tax"][i], abs=1e-9
        )
        assert m.income_statement["tax"][i] == pytest.approx(
            m.income_statement["profit_before_tax"][i] * drivers.tax_rate, abs=1e-9
        )
        assert m.cash_flow["dividends_paid"][i] == pytest.approx(
            m.net_income[i] * drivers.dividend_payout_ratio, abs=1e-9
        )


def test_changing_one_assumption_ripples_through_all_three_statements():
    """The point of the task: a driver change moves the P&L, the balance
    sheet and the cash flow together, and it still balances."""
    from dataclasses import replace

    base = SCENARIOS["Base"]
    heavier_capex = replace(
        base, capex_pct_revenue=tuple(c + 0.02 for c in base.capex_pct_revenue)
    )
    baseline = build_model(GREGGS_HISTORICALS, base)
    stressed = build_model(GREGGS_HISTORICALS, heavier_capex)

    # Balance sheet: more PP&E, funded by more borrowing.
    assert stressed.balance_sheet["ppe"][-1] > baseline.balance_sheet["ppe"][-1]
    assert stressed.balance_sheet["borrowings"][-1] > baseline.balance_sheet["borrowings"][-1]
    # Income statement: more depreciation and more interest, so less profit.
    assert (
        stressed.income_statement["depreciation_ppe"][-1]
        > baseline.income_statement["depreciation_ppe"][-1]
    )
    assert stressed.net_income[-1] < baseline.net_income[-1]
    # Cash flow: bigger capex outflow.
    assert stressed.cash_flow["capex"][-1] > baseline.cash_flow["capex"][-1]
    # And it still balances, with no plug.
    for i in range(5):
        assert stressed.balance_sheet["total_assets"][i] == pytest.approx(
            stressed.balance_sheet["total_liabilities_and_equity"][i], abs=0.01
        )
