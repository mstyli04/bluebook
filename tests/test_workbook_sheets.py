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

# Rows checked against `reference.py` after a real LibreOffice recalculation.
# These are the model's acyclic quantities — everything from the revenue build
# through the four asset and working-capital roll-forwards. The financing block
# is deliberately absent: it is circular, and LibreOffice does not resolve a
# chain of circular groups (see sheet_schedules.py's docstring and
# tests/test_libreoffice_iteration_limits.py). Excluding it here keeps this
# test honest about what has actually been verified, rather than quietly
# asserting a weaker tolerance over a block that is wrong.
ACYCLIC_ROWS = (
    ("IS", "Revenue", lambda m: m.income_statement["revenue"]),
    ("IS", "Gross profit", lambda m: m.income_statement["gross_profit"]),
    ("IS", "Cost of sales", lambda m: m.income_statement["cost_of_sales"]),
    ("IS", "Operating costs", lambda m: m.income_statement["operating_costs"]),
    ("IS", "EBITDA", lambda m: m.ebitda),
    ("IS", "Total depreciation and amortisation", lambda m: m.da_total),
    ("IS", "EBIT", lambda m: m.ebit),
    ("Schedules", "Inventories", lambda m: m.working_capital.inventories),
    ("Schedules", "Trade receivables", lambda m: m.working_capital.receivables),
    ("Schedules", "Trade payables", lambda m: m.working_capital.payables),
    ("Schedules", "Increase in net working capital", lambda m: m.working_capital.change_in_nwc),
    ("Schedules", "Closing PP&E", lambda m: m.fixed_assets.closing_ppe),
    ("Schedules", "Total cash capex", lambda m: m.cash_flow["capex"]),
    ("Schedules", "Closing intangibles", lambda m: m.balance_sheet["intangibles"]),
    ("Schedules", "Amortisation", lambda m: m.income_statement["amortisation"]),
    ("Schedules", "Closing right-of-use assets", lambda m: m.leases.closing_rou),
    ("Schedules", "Closing lease liabilities", lambda m: m.leases.closing_liability),
    ("Schedules", "Lease interest", lambda m: m.leases.interest),
    ("Schedules", "Lease principal repaid", lambda m: m.leases.principal_paid),
)


def _row_of(ws, label_prefix: str) -> int:
    for row in range(3, ws.max_row + 1):
        label = ws[f"B{row}"].value
        if label and (label == label_prefix or label.startswith(label_prefix + " ")):
            return row
    raise AssertionError(f"{ws.title} has no row labelled {label_prefix!r}")


def _compare_against_reference(path: Path, scenario: str) -> float:
    values = recalc_values(path)
    formulas = openpyxl.load_workbook(path)
    model = build_model(GREGGS_HISTORICALS, SCENARIOS[scenario])
    worst = 0.0
    for sheet, label, expected_of in ACYCLIC_ROWS:
        row = _row_of(formulas[sheet], label)
        expected = expected_of(model)
        for index, col in enumerate(FORECAST_COLS):
            got = values[sheet][f"{col}{row}"]
            assert isinstance(got, (int, float)), (
                f"{scenario}: {sheet}!{col}{row} ({label}) recalculated to {got!r}"
            )
            assert got == pytest.approx(expected[index], abs=1e-6), (
                f"{scenario}: {sheet}!{col}{row} ({label})"
            )
            worst = max(worst, abs(got - expected[index]))
    return worst


def test_recalculated_workbook_reproduces_the_python_model_as_built(workbook_path):
    assert _compare_against_reference(workbook_path, "Base") < 1e-6


def test_toggling_only_cell_c3_re_drives_the_whole_model(workbook_path, tmp_path):
    """Change one cell, nothing else, and every driven row moves to Bull."""
    wb = openpyxl.load_workbook(workbook_path)
    assert wb["Assumptions"]["C3"].value == "Base"
    wb["Assumptions"]["C3"] = "Bull"
    toggled = tmp_path / "toggled.xlsx"
    wb.save(toggled)

    assert _compare_against_reference(toggled, "Bull") < 1e-6

    # And it really is a different forecast, not a coincidence.
    base = build_model(GREGGS_HISTORICALS, SCENARIOS["Base"])
    bull = build_model(GREGGS_HISTORICALS, SCENARIOS["Bull"])
    assert bull.income_statement["revenue"][-1] > base.income_statement["revenue"][-1] + 300
