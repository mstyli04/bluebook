from pathlib import Path

import openpyxl
import pytest

from bluebook.recalc import recalc_values


@pytest.fixture
def simple_workbook(tmp_path: Path) -> Path:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    ws["A1"] = 2.0
    ws["A2"] = 3.0
    ws["A3"] = "=A1*A2"
    ws["A4"] = "=SUM(A1:A2)"
    path = tmp_path / "simple.xlsx"
    wb.save(path)
    return path


def test_openpyxl_writes_no_cached_value(simple_workbook: Path):
    """Baseline: the generated file has formulas but no computed results."""
    wb = openpyxl.load_workbook(simple_workbook, data_only=True)
    assert wb["Sheet1"]["A3"].value is None


def test_recalc_values_computes_formulas(simple_workbook: Path):
    values = recalc_values(simple_workbook)
    assert values["Sheet1"]["A3"] == pytest.approx(6.0)
    assert values["Sheet1"]["A4"] == pytest.approx(5.0)
