import openpyxl
import pytest

from bluebook.workbook.layout import Layout
from bluebook.workbook.sheet import SheetWriter
from bluebook.workbook.styles import INPUT_FONT, FORMULA_FONT, LINK_FONT


def test_fonts_use_the_agreed_colours():
    assert INPUT_FONT.color.rgb == "FF0000FF"
    assert FORMULA_FONT.color.rgb == "FF000000"
    assert LINK_FONT.color.rgb == "FF008000"


def test_input_row_writes_values_in_blue_and_registers_its_row():
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Assumptions"
    layout = Layout()
    writer = SheetWriter(ws, layout, historical=False)
    writer.title("Assumptions")
    writer.year_header(["FY2026", "FY2027", "FY2028", "FY2029", "FY2030"])
    writer.input_row("tax_rate", "Tax rate", [0.25] * 5)

    row = layout.row_of("Assumptions", "tax_rate")
    assert ws[f"F{row}"].value == pytest.approx(0.25)
    assert ws[f"F{row}"].font.color.rgb == "FF0000FF"


def test_formula_row_writes_formulas_in_black():
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "IS"
    layout = Layout()
    writer = SheetWriter(ws, layout, historical=False)
    writer.title("Income Statement")
    writer.year_header(["FY2026", "FY2027", "FY2028", "FY2029", "FY2030"])
    writer.formula_row("revenue", "Revenue", ["=1+1"] * 5)

    row = layout.row_of("IS", "revenue")
    assert ws[f"F{row}"].value == "=1+1"
    assert ws[f"F{row}"].font.color.rgb == "FF000000"
