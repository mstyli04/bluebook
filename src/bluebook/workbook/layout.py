"""Maps line-item names to workbook rows so formulas never hardcode addresses."""

from __future__ import annotations

HIST_COLS = ("C", "D", "E")
FCST_COLS = ("F", "G", "H", "I", "J")


class Layout:
    def __init__(self) -> None:
        self._rows: dict[tuple[str, str], int] = {}

    def register(self, sheet: str, key: str, row: int) -> None:
        if (sheet, key) in self._rows:
            raise ValueError(f"{sheet}.{key} already registered")
        taken = {r: k for (s, k), r in self._rows.items() if s == sheet}
        if row in taken:
            raise ValueError(f"{sheet} row {row} already holds '{taken[row]}'")
        self._rows[(sheet, key)] = row

    def row_of(self, sheet: str, key: str) -> int:
        try:
            return self._rows[(sheet, key)]
        except KeyError:
            raise KeyError(f"{sheet!r} has no line item {key!r}") from None

    def ref(self, sheet: str, key: str, col: str) -> str:
        return f"'{sheet}'!{col}{self.row_of(sheet, key)}"

    @staticmethod
    def col_for_year(index: int, *, historical: bool) -> str:
        cols = HIST_COLS if historical else FCST_COLS
        return cols[index]
