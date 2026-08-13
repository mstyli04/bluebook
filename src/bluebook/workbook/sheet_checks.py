"""Checks — the integrity tests, as live formulas, on the second tab.

Positioned second so it is impossible to miss: a reader who opens the file
sees the Cover's disclosures and then, immediately, whether the model holds
together. Every result is a live ``=`` formula returning TRUE or FALSE, read
off the rows the other sheets registered, so it re-evaluates whenever the
scenario switch moves or an input changes. A check that cannot fail is worse
than no check, which is why each one is written against the construction the
model actually uses rather than a restatement of it.

`Checks` is one of the five sheets in `HARDCODE_ALLOWED`, and the thresholds
below are the reason it is on that list: a tolerance or a bound is a constant
by nature and has no formula source. Nothing else here is hardcoded — every
figure being tested is a reference.

--------------------------------------------------------------------------
The bounds, and why they are the numbers they are
--------------------------------------------------------------------------
* **The cash tie compares three constructions, not two.** The first version
  of this sheet tied ``CF!closing_cash`` to ``BS!cash`` and stopped there.
  Mutation testing on 13 Aug found that check could barely fail: ``BS!cash``
  is literally ``='CF'!closing_cash``, so the comparison was a cell against
  itself. Breaking the cash flow statement's own ``net_change_in_cash`` left
  it reading TRUE — only the balance-sheet check noticed, and then only
  incidentally. The debt schedule keeps an independent cash track
  (``Schedules!cash_closing``, built from cash available before debt service
  less repayment plus revolver draw), and tying the cash flow statement to
  THAT is a real cross-check between two separate constructions. Both
  comparisons are kept: the balance-sheet one still catches a corrupted link.
* **Tolerance 1e-6 (£m)** on the two tie-outs. The workbook is acyclic, so
  LibreOffice and Excel evaluate every cell in one pass and the only
  difference from exact arithmetic is floating-point association. The Python
  cross-check in `tests/test_workbook_sheets.py` holds 1e-9; this is looser
  because it is read by a human on a rounded display, not by a test.
* **Terminal share of EV below 0.97**, not the 0.90 the original plan named.
  `tests/test_valuation.py` documents the correction: 0.90 compared two
  different discount clocks, and on the construction the model uses the
  concentration is 93-95% in all three scenarios. That is high, and it is
  what a heavy-investment explicit period produces; 0.97 is the band that
  still catches a regression without failing on the model's own answer.
* **Revenue growth within +/-50%** a year. A shape check, not a forecast
  view: it catches a driver wired to the wrong row, which is the failure that
  produces a plausible-looking workbook.
* **Lease-inclusive net debt below 2.0x EBITDA, every year.** The model draws
  roughly £190-211m at its FY2028 peak against the £100m facility Greggs
  actually drew on at FY2025, so the workbook assumes that facility is
  upsized — see the Cover. What makes that an assumption about availability
  rather than about solvency is that leverage stays modest, and the honest
  way to say so is on a consistent basis: EBITDA here is post-IFRS 16 and
  excludes rent, so measuring gross borrowings against it leaves the lease
  obligations out of the numerator while their add-back inflates the
  denominator. That basis reads 0.40x-0.56x and is the most flattering of the
  defensible measures; lease-inclusive net debt over the same EBITDA reads
  1.30x (Bull), 1.51x (Base) and 1.78x (Bear). The check uses the latter and
  the Cover quotes it. The gross figure is still written to the sheet, as a
  labelled memo directly beneath, so the gap between the two is visible
  rather than quietly resolved in favour of the better-looking one.
"""

from __future__ import annotations

from bluebook.workbook.formulas import aref
from bluebook.workbook.layout import FCST_COLS, Layout
from bluebook.workbook.sheet import SheetWriter
from bluebook.workbook.styles import MONEY_FORMAT, MULTIPLE_FORMAT, TEXT_FORMAT

SHEET = "Checks"
ASSUMPTIONS = "Assumptions"
BS = "BS"
CF = "CF"
DCF = "DCF"
IS = "IS"
SCHEDULES = "Schedules"

SCALAR_COL = "C"
RESULT_COL = "D"
RESULT = (RESULT_COL,)

TIE_TOLERANCE = 1e-6
TERMINAL_SHARE_CEILING = 0.97
MAX_REVENUE_GROWTH = 0.5
MINIMUM_CASH = 50.0
# Lease-INCLUSIVE net debt / EBITDA. The basis matters more than the number:
# EBITDA here is post-IFRS 16 and so excludes rent, which means a numerator of
# gross borrowings alone is measured against a denominator inflated by the very
# obligations it leaves out. That mismatch reads 0.40x-0.56x, the most
# flattering of the defensible measures; on a consistent basis the same model
# is at 1.30x-1.78x. 2.0x leaves real headroom over the Bear case's 1.78x
# without being loose enough to pass on a materially more geared forecast.
PEAK_LEVERAGE_CEILING = 2.0


def write_checks(writer: SheetWriter, layout: Layout) -> None:
    """Write every integrity test, each a single TRUE/FALSE cell in column D."""

    def year(sheet: str, key: str, col: str) -> str:
        return layout.ref(sheet, key, col)

    def scalar(sheet: str, key: str) -> str:
        return aref(layout, sheet, key, SCALAR_COL)

    def across_years(build) -> str:
        """AND(...) of one expression per forecast year.

        Written as an explicit argument per year rather than as a range: the
        rows being tested live on five different sheets, and a range would
        assume a contiguity none of them promises.
        """
        return "AND(" + ",".join(build(col) for col in FCST_COLS) + ")"

    def net_debt_over_ebitda(col: str) -> str:
        """One year's lease-inclusive net debt over that year's EBITDA.

        Borrowings less cash PLUS lease liabilities, against a post-IFRS 16
        EBITDA. Both halves are then on the same side of the lease question,
        which the gross-borrowings measure this replaced was not.
        """
        return (
            f"({year(SCHEDULES, 'debt_closing', col)}"
            f"-{year(SCHEDULES, 'cash_closing', col)}"
            f"+{year(SCHEDULES, 'lease_liability_closing', col)})"
            f"/{year(IS, 'ebitda', col)}"
        )

    def check(key: str, label: str, expression: str) -> None:
        writer.formula_row(key, label, [f"={expression}"], TEXT_FORMAT, cols=RESULT)

    def value(key: str, label: str, formula: str, fmt: str = MONEY_FORMAT) -> None:
        writer.formula_row(key, label, [formula], fmt, cols=(SCALAR_COL,))

    def note(key: str, text: str) -> None:
        writer.formula_row(key, text, [])

    writer.title("Checks — integrity tests. Every result below must read TRUE.")
    writer.blank()

    check(
        "check_balance_sheet_balances",
        "Balance sheet balances in every forecast year",
        across_years(
            lambda col: f"ABS({year(BS, 'balance_check', col)})<{TIE_TOLERANCE}"
        ),
    )
    check(
        "check_cash_ties",
        "Closing cash agrees across all three constructions of it, every year",
        across_years(
            lambda col: f"AND(ABS({year(CF, 'closing_cash', col)}"
            f"-{year(BS, 'cash', col)})<{TIE_TOLERANCE},"
            f"ABS({year(CF, 'closing_cash', col)}"
            f"-{year(SCHEDULES, 'cash_closing', col)})<{TIE_TOLERANCE})"
        ),
    )
    check(
        "check_debt_never_negative",
        "Closing borrowings never negative (no accidental cash-as-debt)",
        across_years(lambda col: f"{year(SCHEDULES, 'debt_closing', col)}>=0"),
    )
    check(
        "check_cash_floor_held",
        f"Cash never falls below the £{MINIMUM_CASH:,.0f}m minimum the revolver defends",
        across_years(
            lambda col: f"{year(CF, 'closing_cash', col)}>={MINIMUM_CASH}-{TIE_TOLERANCE}"
        ),
    )
    check(
        "check_growth_below_wacc",
        "Perpetuity growth is below WACC (the Gordon formula is defined)",
        f"{scalar(DCF, 'perpetuity_growth')}<{scalar(DCF, 'wacc')}",
    )
    check(
        "check_terminal_share_banded",
        f"Terminal value is below {TERMINAL_SHARE_CEILING:.0%} of enterprise value",
        f"{scalar(DCF, 'terminal_share_of_ev')}<{TERMINAL_SHARE_CEILING}",
    )
    check(
        "check_revenue_growth_plausible",
        f"No forecast revenue growth outside +/-{MAX_REVENUE_GROWTH:.0%}",
        "AND("
        + ",".join(
            f"ABS({year(IS, 'revenue', col)}/{year(IS, 'revenue', FCST_COLS[index - 1])}-1)"
            f"<{MAX_REVENUE_GROWTH}"
            for index, col in enumerate(FCST_COLS)
            if index > 0
        )
        + ")",
    )
    check(
        "check_peak_leverage_modest",
        "Peak borrowings are an assumed facility upsize, not a solvency problem: "
        f"lease-inclusive net debt / EBITDA below {PEAK_LEVERAGE_CEILING:.1f}x "
        "every year",
        across_years(lambda col: f"{net_debt_over_ebitda(col)}<{PEAK_LEVERAGE_CEILING}"),
    )

    writer.blank()
    writer.title("The figures behind the financing disclosure")
    value(
        "peak_borrowings",
        "Peak forecast borrowings (£m) — against the £100m facility drawn at FY2025",
        "=MAX(" + ",".join(year(SCHEDULES, "debt_closing", col) for col in FCST_COLS) + ")",
    )
    value(
        "peak_leverage",
        "Peak lease-inclusive net debt / EBITDA (x) — the basis the check uses",
        "=MAX(" + ",".join(net_debt_over_ebitda(col) for col in FCST_COLS) + ")",
        MULTIPLE_FORMAT,
    )
    value(
        "peak_leverage_gross",
        "Memo: peak gross borrowings / EBITDA (x) — the flattering basis, shown "
        "so the difference is visible rather than hidden",
        "=MAX("
        + ",".join(
            f"{year(SCHEDULES, 'debt_closing', col)}/{year(IS, 'ebitda', col)}"
            for col in FCST_COLS
        )
        + ")",
        MULTIPLE_FORMAT,
    )

    writer.blank()
    note(
        "note_checks_are_live",
        "Every result above is a live formula reading the rows it tests, not a "
        "recorded outcome. Move the scenario switch on Assumptions and they "
        "re-evaluate. If any reads FALSE, the workbook is not internally "
        "consistent and nothing downstream of it should be quoted.",
    )
    note(
        "note_what_checks_cannot_do",
        "These test internal consistency, not whether the forecast is right. A "
        "model can tie out perfectly and still be built on the wrong drivers — "
        "the Cover's disclosures and the Historicals' source column are where "
        "that question is answered.",
    )
