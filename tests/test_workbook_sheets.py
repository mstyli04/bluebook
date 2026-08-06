"""Structure, layout and live-recalculation tests for the generated workbook.

Layout assertions here use LITERAL cell addresses. A test that resolves a row
through `layout.row_of` passes whatever position the writer chose, so it
cannot catch a positional error — which is exactly how a two-row title offset
survived Task 11's own test. Where this file asserts a position, it hardcodes
it.
"""

from pathlib import Path

import openpyxl
import pytest

from bluebook.assumptions import SCENARIOS
from bluebook.inputs.greggs import GREGGS_HISTORICALS
from bluebook.recalc import recalc_values
from bluebook.reference import build_model
from bluebook.workbook.build import build_workbook
from bluebook.workbook.styles import HARDCODE_ALLOWED

FORECAST_COLS = "FGHIJ"


@pytest.fixture(scope="module")
def workbook_path(tmp_path_factory) -> Path:
    """One Base-case workbook, shared — building it is not what is under test."""
    path = tmp_path_factory.mktemp("wb") / "model.xlsx"
    return build_workbook(GREGGS_HISTORICALS, "Base", path)


@pytest.fixture(scope="module")
def workbook(workbook_path):
    return openpyxl.load_workbook(workbook_path)


# --------------------------------------------------------------------------
# Layout: literal addresses, per the plan's global constraints
# --------------------------------------------------------------------------


def test_every_sheet_puts_its_title_in_a1(workbook):
    for name in workbook.sheetnames:
        assert workbook[name]["A1"].value, f"{name} has no title in A1"


def test_year_headers_are_on_row_2_in_the_year_columns(workbook):
    assert workbook["Historicals"]["C2"].value == "FY2023"
    assert workbook["Historicals"]["D2"].value == "FY2024"
    assert workbook["Historicals"]["E2"].value == "FY2025"
    assert workbook["Assumptions"]["F2"].value == "FY2026"
    assert workbook["Assumptions"]["J2"].value == "FY2030"
    # The statements do not hold their own copy of the year labels.
    assert workbook["IS"]["F2"].value == "='Assumptions'!F$2"
    assert workbook["BS"]["J2"].value == "='Assumptions'!J$2"


def test_first_data_row_is_row_3_on_every_written_sheet(workbook):
    expected_first_labels = {
        "Assumptions": "SCENARIO (Bear / Base / Bull)",
        "Historicals": "Revenue",
        "IS": "Revenue",
        "BS": "Property, plant and equipment",
        "CF": "EBITDA",
        "Schedules": "Inventories (cost of sales x inventory days / 365)",
    }
    for sheet, label in expected_first_labels.items():
        assert workbook[sheet]["B3"].value == label, f"{sheet}!B3"


def test_the_scenario_switch_sits_in_c3_and_holds_the_requested_scenario(workbook):
    assert workbook["Assumptions"]["C3"].value == "Base"


def test_the_scenario_switch_is_a_validated_dropdown_over_the_three_scenarios(workbook):
    validations = workbook["Assumptions"].data_validations.dataValidation
    covering = [dv for dv in validations if "C3" in str(dv.sqref)]
    assert len(covering) == 1, f"expected exactly one validation on C3, got {validations}"
    assert covering[0].type == "list"
    assert covering[0].formula1 == '"Bear,Base,Bull"'


def test_historicals_carries_the_reported_figures_and_their_sources(workbook):
    ws = workbook["Historicals"]
    assert ws["C3"].value == pytest.approx(GREGGS_HISTORICALS[0].revenue.value)
    assert ws["E3"].value == pytest.approx(GREGGS_HISTORICALS[-1].revenue.value)
    assert "FY2023 AR p.119" in ws["L3"].value


# --------------------------------------------------------------------------
# The rule the whole task exists for: formulas, not values
# --------------------------------------------------------------------------


@pytest.mark.parametrize("sheet", ["IS", "BS", "CF", "Schedules"])
def test_no_forecast_cell_on_a_calculation_sheet_is_a_constant(workbook, sheet):
    ws = workbook[sheet]
    for row in ws.iter_rows(min_col=6, max_col=10):
        for cell in row:
            if cell.value is not None:
                assert isinstance(cell.value, str) and cell.value.startswith("="), (
                    f"{sheet}!{cell.coordinate} holds a constant: {cell.value!r}"
                )


def test_calculation_sheets_hold_no_hardcoded_number_anywhere(workbook):
    """Not just F:J — no numeric constant in any cell of a calculation sheet."""
    for name in workbook.sheetnames:
        if name in HARDCODE_ALLOWED:
            continue
        for row in workbook[name].iter_rows():
            for cell in row:
                assert not isinstance(cell.value, (int, float)), (
                    f"{name}!{cell.coordinate} is a hardcoded number: {cell.value!r}"
                )


def test_driver_rows_choose_between_the_three_scenario_paths(workbook):
    ws = workbook["Assumptions"]
    revenue_growth = next(
        r for r in range(3, ws.max_row + 1) if ws[f"B{r}"].value == "Revenue growth"
    )
    formula = ws[f"F{revenue_growth}"].value
    assert formula.startswith('=CHOOSE(MATCH(\'Assumptions\'!$C$3,{"Bear";"Base";"Bull"},0),')
    # Three arms, one per scenario, all reading column F.
    assert formula.count("'Assumptions'!F") == 3


# --------------------------------------------------------------------------
# Iterative calculation
# --------------------------------------------------------------------------


def test_iterative_calculation_is_enabled_with_the_spikes_settings(workbook):
    """Still pinned even though the workbook is now acyclic.

    The settings are retained on purpose — free on a file with no cycle, and
    they turn a future reintroduced circularity into a converged answer rather
    than `Err:522`. See `build.py`'s docstring. Dropping them would be a silent
    change to how such an edit behaves, so it should have to fail a test.
    """
    assert workbook.calculation.iterate is True
    assert workbook.calculation.iterateCount == 100
    assert workbook.calculation.iterateDelta == pytest.approx(0.0001)


# --------------------------------------------------------------------------
# The build's own guard
# --------------------------------------------------------------------------


def test_build_rejects_an_unknown_scenario(tmp_path):
    with pytest.raises(ValueError, match="scenario_name must be one of"):
        build_workbook(GREGGS_HISTORICALS, "Sideways", tmp_path / "x.xlsx")


def test_build_rejects_an_empty_history(tmp_path):
    with pytest.raises(ValueError, match="at least one reported year"):
        build_workbook([], "Base", tmp_path / "x.xlsx")


# --------------------------------------------------------------------------
# Live recalculation: does Excel agree with the Python model, and does the
# switch re-drive it?
# --------------------------------------------------------------------------

# Every row of the model that `reference.py` also computes, checked against it
# after a real LibreOffice recalculation. The financing block is included: since
# `INTEREST_BASIS` became "opening" the workbook has no circular reference, so
# there is nothing here that LibreOffice cannot resolve and no reason to hold
# any row back. Both balance sheet totals and the balance check are included
# too, which is what makes this a test of the model rather than of a subset.
CHECKED_ROWS = (
    ("IS", "Revenue", lambda m: m.income_statement["revenue"]),
    ("IS", "Gross profit", lambda m: m.income_statement["gross_profit"]),
    ("IS", "Cost of sales", lambda m: m.income_statement["cost_of_sales"]),
    ("IS", "Operating costs", lambda m: m.income_statement["operating_costs"]),
    ("IS", "EBITDA", lambda m: m.ebitda),
    ("IS", "Depreciation of PP&E", lambda m: m.income_statement["depreciation_ppe"]),
    ("IS", "Depreciation of ROU assets", lambda m: m.income_statement["depreciation_rou"]),
    ("IS", "Amortisation", lambda m: m.income_statement["amortisation"]),
    ("IS", "Total depreciation and amortisation", lambda m: m.da_total),
    ("IS", "EBIT", lambda m: m.ebit),
    ("IS", "Lease interest", lambda m: m.income_statement["lease_interest"]),
    ("IS", "Interest on borrowings", lambda m: m.income_statement["debt_interest"]),
    ("IS", "Profit before tax", lambda m: m.income_statement["profit_before_tax"]),
    ("IS", "Tax charge", lambda m: m.income_statement["tax"]),
    ("IS", "Net income", lambda m: m.net_income),
    ("BS", "Property, plant and equipment", lambda m: m.balance_sheet["ppe"]),
    ("BS", "Right-of-use assets", lambda m: m.balance_sheet["rou_assets"]),
    ("BS", "Intangible assets", lambda m: m.balance_sheet["intangibles"]),
    ("BS", "Inventories", lambda m: m.balance_sheet["inventories"]),
    ("BS", "Trade and other receivables", lambda m: m.balance_sheet["trade_receivables"]),
    ("BS", "Cash and cash equivalents", lambda m: m.balance_sheet["cash"]),
    ("BS", "Other assets", lambda m: m.balance_sheet["other_assets"]),
    ("BS", "Total assets", lambda m: m.balance_sheet["total_assets"]),
    ("BS", "Trade and other payables", lambda m: m.balance_sheet["trade_payables"]),
    ("BS", "Lease liabilities", lambda m: m.balance_sheet["lease_liabilities"]),
    ("BS", "Borrowings", lambda m: m.balance_sheet["borrowings"]),
    ("BS", "Other liabilities", lambda m: m.balance_sheet["other_liabilities"]),
    ("BS", "Total equity", lambda m: m.balance_sheet["equity"]),
    (
        "BS",
        "Total liabilities and equity",
        lambda m: m.balance_sheet["total_liabilities_and_equity"],
    ),
    ("BS", "Balance check", lambda m: [0.0] * len(m.years)),
    ("CF", "EBITDA", lambda m: m.cash_flow["ebitda"]),
    (
        "CF",
        "Increase in working capital",
        lambda m: m.cash_flow["change_in_working_capital"],
    ),
    ("CF", "Tax paid", lambda m: m.cash_flow["tax_paid"]),
    ("CF", "Cash from operations", lambda m: m.cash_flow["cash_from_operations"]),
    ("CF", "Capital expenditure", lambda m: m.cash_flow["capex"]),
    ("CF", "of which PP&E", lambda m: m.cash_flow["capex_ppe"]),
    ("CF", "of which intangible", lambda m: m.cash_flow["capex_intangible"]),
    ("CF", "Lease interest paid", lambda m: m.cash_flow["lease_interest_paid"]),
    ("CF", "Lease principal repaid", lambda m: m.cash_flow["lease_principal_paid"]),
    ("CF", "Interest paid on borrowings", lambda m: m.cash_flow["debt_interest_paid"]),
    ("CF", "Repayment of borrowings", lambda m: m.cash_flow["debt_repayment"]),
    ("CF", "Revolver draw", lambda m: m.cash_flow["revolver_draw"]),
    ("CF", "Dividends paid", lambda m: m.cash_flow["dividends_paid"]),
    ("CF", "Net change in cash", lambda m: m.cash_flow["net_change_in_cash"]),
    ("CF", "Opening cash", lambda m: m.cash_flow["opening_cash"]),
    ("CF", "Closing cash", lambda m: m.cash_flow["closing_cash"]),
    ("Schedules", "Inventories", lambda m: m.working_capital.inventories),
    ("Schedules", "Trade receivables", lambda m: m.working_capital.receivables),
    ("Schedules", "Trade payables", lambda m: m.working_capital.payables),
    (
        "Schedules",
        "Net working capital",
        lambda m: m.working_capital.net_working_capital,
    ),
    ("Schedules", "Increase in net working capital", lambda m: m.working_capital.change_in_nwc),
    ("Schedules", "PP&E capex", lambda m: m.fixed_assets.capex),
    ("Schedules", "Depreciation of PP&E", lambda m: m.fixed_assets.depreciation),
    ("Schedules", "Closing PP&E", lambda m: m.fixed_assets.closing_ppe),
    ("Schedules", "Intangible additions", lambda m: m.cash_flow["capex_intangible"]),
    ("Schedules", "Amortisation", lambda m: m.income_statement["amortisation"]),
    ("Schedules", "Closing intangibles", lambda m: m.balance_sheet["intangibles"]),
    ("Schedules", "Total cash capex", lambda m: m.cash_flow["capex"]),
    ("Schedules", "New ROU asset additions", lambda m: m.leases.additions),
    ("Schedules", "Depreciation of ROU assets", lambda m: m.leases.depreciation),
    ("Schedules", "Closing right-of-use assets", lambda m: m.leases.closing_rou),
    ("Schedules", "Lease interest", lambda m: m.leases.interest),
    ("Schedules", "Lease principal repaid", lambda m: m.leases.principal_paid),
    ("Schedules", "Closing lease liabilities", lambda m: m.leases.closing_liability),
    ("Schedules", "Dividends declared", lambda m: m.cash_flow["dividends_paid"]),
    ("Schedules", "Closing shareholders' equity", lambda m: m.balance_sheet["equity"]),
    ("Schedules", "Opening borrowings", lambda m: m.debt.opening),
    ("Schedules", "Interest on borrowings", lambda m: m.debt.interest),
    ("Schedules", "Repayment of borrowings", lambda m: m.debt.repayment),
    ("Schedules", "Revolver draw", lambda m: m.debt.revolver_draw),
    ("Schedules", "Closing borrowings", lambda m: m.debt.closing),
    ("Schedules", "Closing cash", lambda m: m.debt.cash_balance),
)


# The workbook is acyclic, so LibreOffice evaluates every cell in one pass and
# the only difference from Python is floating-point association. 1e-9 is
# therefore a real assertion rather than a nod: under the old average-interest
# basis the tolerance had to leave room for iterative convergence slack
# (~1e-4), and it no longer does.
RECALC_TOLERANCE = 1e-9


def _row_of(ws, label_prefix: str) -> int:
    """The single row on `ws` whose label starts with `label_prefix`.

    Raises if two rows match, because a prefix that matches more than one row
    silently checks the wrong one — "EBIT" matching "EBITDA" cost an hour of
    chasing a phantom defect during this task.
    """
    matches = [
        row
        for row in range(3, ws.max_row + 1)
        # Leading spaces indent the cash flow's memo lines under their total;
        # they are presentation, so they are not part of the label here.
        if (label := (ws[f"B{row}"].value or "").lstrip())
        and (label == label_prefix or label.startswith(label_prefix + " "))
    ]
    assert len(matches) == 1, (
        f"{ws.title}: {label_prefix!r} matches {len(matches)} rows {matches}; "
        f"a prefix must identify exactly one row"
    )
    return matches[0]


def _compare_against_reference(path: Path, scenario: str) -> float:
    values = recalc_values(path)
    formulas = openpyxl.load_workbook(path)
    model = build_model(GREGGS_HISTORICALS, SCENARIOS[scenario])
    worst = 0.0
    for sheet, label, expected_of in CHECKED_ROWS:
        row = _row_of(formulas[sheet], label)
        expected = expected_of(model)
        for index, col in enumerate(FORECAST_COLS):
            got = values[sheet][f"{col}{row}"]
            assert isinstance(got, (int, float)), (
                f"{scenario}: {sheet}!{col}{row} ({label}) recalculated to {got!r}"
            )
            assert got == pytest.approx(expected[index], abs=RECALC_TOLERANCE), (
                f"{scenario}: {sheet}!{col}{row} ({label})"
            )
            worst = max(worst, abs(got - expected[index]))
    return worst


@pytest.mark.parametrize("scenario", ["Bear", "Base", "Bull"])
def test_recalculated_workbook_reproduces_the_python_model(tmp_path, scenario):
    """Every cell of every statement, in every scenario, in real Excel terms."""
    path = build_workbook(GREGGS_HISTORICALS, scenario, tmp_path / f"{scenario}.xlsx")
    assert _compare_against_reference(path, scenario) < RECALC_TOLERANCE


def test_toggling_only_cell_c3_re_drives_the_whole_model(workbook_path, tmp_path):
    """Change one cell, nothing else, and every driven row moves to Bull."""
    wb = openpyxl.load_workbook(workbook_path)
    assert wb["Assumptions"]["C3"].value == "Base"
    wb["Assumptions"]["C3"] = "Bull"
    toggled = tmp_path / "toggled.xlsx"
    wb.save(toggled)

    assert _compare_against_reference(toggled, "Bull") < RECALC_TOLERANCE

    # And it really is a different forecast, not a coincidence.
    base = build_model(GREGGS_HISTORICALS, SCENARIOS["Base"])
    bull = build_model(GREGGS_HISTORICALS, SCENARIOS["Bull"])
    assert bull.income_statement["revenue"][-1] > base.income_statement["revenue"][-1] + 300
