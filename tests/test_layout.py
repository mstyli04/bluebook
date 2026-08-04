import pytest

from bluebook.workbook.layout import FCST_COLS, HIST_COLS, Layout


def test_ref_builds_a_qualified_reference():
    layout = Layout()
    layout.register("IS", "revenue", 5)
    assert layout.ref("IS", "revenue", "F") == "'IS'!F5"


def test_column_helpers():
    assert HIST_COLS == ("C", "D", "E")
    assert FCST_COLS == ("F", "G", "H", "I", "J")
    layout = Layout()
    assert layout.col_for_year(0, historical=True) == "C"
    assert layout.col_for_year(2, historical=False) == "H"


def test_duplicate_registration_is_rejected():
    layout = Layout()
    layout.register("IS", "revenue", 5)
    with pytest.raises(ValueError, match="already registered"):
        layout.register("IS", "revenue", 9)


def test_unknown_key_raises_with_a_useful_message():
    layout = Layout()
    layout.register("IS", "revenue", 5)
    with pytest.raises(KeyError, match="gross_profit"):
        layout.row_of("IS", "gross_profit")


def test_two_rows_may_not_share_one_position_on_a_sheet():
    layout = Layout()
    layout.register("IS", "revenue", 5)
    with pytest.raises(ValueError, match="row 5"):
        layout.register("IS", "cost_of_sales", 5)
