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

    def items(self) -> dict[tuple[str, str], int]:
        """A read-only copy of every ``(sheet, key) -> row`` registration.

        Added for `build.py`'s two-pass build, which measures row positions on
        a throwaway pass and then writes the real formulas on a second pass:
        it compares the two passes' registrations to prove they agree before
        saving, so a formula can never point at a row the second pass moved.
        """
        return dict(self._rows)

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
