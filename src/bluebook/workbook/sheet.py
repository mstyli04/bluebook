"""SheetWriter: the single path every sheet in the workbook is written through.

It wraps a worksheet and a :class:`~bluebook.workbook.layout.Layout` and
exposes a handful of row methods (`title`, `year_header`, `input_row`,
`formula_row`, `blank`). Each call writes at the writer's internal cursor and
advances it, so callers never track row numbers themselves; `input_row` and
`formula_row` additionally register their key in the `Layout` at the row they
wrote, so later sheets can address the value with `layout.ref(...)` instead
of a hardcoded cell reference.

A `SheetWriter` is single-mode: constructed with `historical=True` it writes
row values into `HIST_COLS` (three historical years), constructed with
`historical=False` (the default) it writes into `FCST_COLS` (five forecast
years). `year_header` alone can override the mode per call (its own
`historical` argument), which lets one writer still label a historical block
of columns it does not itself write values into.

Row 1 is always the sheet title, row 2 the year header (the plan's Global
Constraints state this explicitly) — `title()` and `year_header()` each
advance the cursor by exactly one row, so the first row a caller registers
through `input_row`/`formula_row` lands on row 3.

`formula_row` and `input_row` enforce the hardcode rule from `styles.py`'s
`HARDCODE_ALLOWED` at the point of writing, not just at a later scan: on any
sheet outside that set, `formula_row` rejects any value that is not a
`"="`-prefixed formula string, and `input_row` is rejected outright (its
purpose — writing constants — is only legal on the allowed sheets).
"""

from __future__ import annotations

from typing import Sequence

from openpyxl.styles import Font
from openpyxl.worksheet.worksheet import Worksheet

from bluebook.workbook.layout import Layout
from bluebook.workbook.styles import (
    FORMULA_FONT,
    HARDCODE_ALLOWED,
    HEADER_FONT,
    INPUT_FONT,
    LINK_FONT,
    MONEY_FORMAT,
    TITLE_FONT,
)

LABEL_COL = "B"


class SheetWriter:
    """Writes one worksheet top to bottom, registering rows in a Layout."""

    def __init__(self, worksheet: Worksheet, layout: Layout, *, historical: bool = False) -> None:
        self.ws = worksheet
        self.layout = layout
        self.sheet = worksheet.title
        self.historical = historical
        self.row = 1

    def title(self, text: str) -> None:
        """Write the sheet title in A1. The year header follows immediately on row 2."""
        cell = self.ws[f"A{self.row}"]
        cell.value = text
        cell.font = TITLE_FONT
        self.row += 1

    def year_header(self, labels: Sequence[str], historical: bool | None = None) -> None:
        """Write year labels across the sheet's data columns, bold."""
        use_historical = self.historical if historical is None else historical
        for index, label in enumerate(labels):
            col = self.layout.col_for_year(index, historical=use_historical)
            cell = self.ws[f"{col}{self.row}"]
            cell.value = label
            cell.font = HEADER_FONT
        self.row += 1

    def input_row(
        self,
        key: str,
        label: str,
        values: Sequence,
        fmt: str = MONEY_FORMAT,
    ) -> int:
        """Write a row of hardcoded values in blue and register it in the Layout.

        Raises ValueError if this sheet is not in `HARDCODE_ALLOWED` — writing
        constants at all is only legal on the five sheets that list permits.
        """
        if self.sheet not in HARDCODE_ALLOWED:
            raise ValueError(
                f"sheet {self.sheet!r} is not in HARDCODE_ALLOWED "
                f"{sorted(HARDCODE_ALLOWED)!r}: input_row({key!r}, ...) may not "
                f"write hardcoded constants here"
            )
        return self._write_row(key, label, values, fmt, INPUT_FONT)

    def formula_row(
        self,
        key: str,
        label: str,
        formulas: Sequence[str],
        fmt: str = MONEY_FORMAT,
        *,
        is_link: bool = False,
    ) -> int:
        """Write a row of formulas (black, or green if `is_link`) and register it.

        On any sheet not in `HARDCODE_ALLOWED`, every value must be a
        `"="`-prefixed formula string; a bare constant raises ValueError
        naming the sheet, the key and the offending value, so it is caught
        here rather than by a later scan of the finished workbook.
        """
        if self.sheet not in HARDCODE_ALLOWED:
            for value in formulas:
                if not (isinstance(value, str) and value.startswith("=")):
                    raise ValueError(
                        f"sheet {self.sheet!r}, row {key!r}: formula_row may only "
                        f"write formula strings here, got {value!r}"
                    )
        font = LINK_FONT if is_link else FORMULA_FONT
        return self._write_row(key, label, formulas, fmt, font)

    def blank(self, rows: int = 1) -> None:
        """Advance the cursor without writing anything, leaving `rows` blank."""
        self.row += rows

    def _write_row(
        self,
        key: str,
        label: str,
        values: Sequence,
        fmt: str,
        font: Font,
    ) -> int:
        row = self.row
        self.layout.register(self.sheet, key, row)
        self.ws[f"{LABEL_COL}{row}"] = label
        for index, value in enumerate(values):
            col = self.layout.col_for_year(index, historical=self.historical)
            cell = self.ws[f"{col}{row}"]
            cell.value = value
            cell.font = font
            cell.number_format = fmt
        self.row += 1
        return row
