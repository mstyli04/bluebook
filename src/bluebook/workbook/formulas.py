"""Formula-string builders shared by the sheet writers.

Everything here resolves row positions through :class:`Layout`, never through
a literal row number, for the reason `layout.py` exists: a row that moves
must not silently break a reference. `Layout.ref` covers the common relative
case (``'IS'!F5``); this module adds the three shapes the statement sheets
need on top of it.
"""

from __future__ import annotations

from typing import Sequence

from bluebook.workbook.layout import FCST_COLS, Layout


def aref(layout: Layout, sheet: str, key: str, col: str) -> str:
    """Absolute form of `Layout.ref` — ``'Assumptions'!$C$12``.

    Used for the scalar cells on Assumptions (a single tax rate, a single day
    count) which every forecast column of every statement points at. The
    ``$`` matters: it is what makes a driver row's five columns literally the
    same formula bar entry apart from the column they read, which is how a
    reader checks a row is consistent across the forecast.
    """
    return f"'{sheet}'!${col}${layout.row_of(sheet, key)}"


def total(refs: Sequence[str]) -> str:
    """Sum of the given references, written out as an addition chain.

    Deliberately not ``SUM(F5:F11)``: the balance sheet's asset and claim
    blocks are not contiguous ranges (each is interrupted by section headers
    and blank rows), and a range that silently grows to include a row
    inserted at its edge is exactly the class of error the row registry is
    meant to remove.
    """
    return "=" + "+".join(refs)


def roll_forward(
    layout: Layout,
    opening_formula: str,
    closing_key: str,
    *,
    sheet: str,
) -> list[str]:
    """Formulas for an opening-balance row across the five forecast years.

    Year one opens on `opening_formula` — in every case in this model, a link
    to the last historical year's actual balance, mirroring `reference.py`'s
    rule that no opening balance is ever a fresh start. Years two to five
    open on the prior column of `sheet`'s `closing_key` row.
    """
    formulas = [opening_formula]
    for index in range(1, len(FCST_COLS)):
        prior_col = FCST_COLS[index - 1]
        formulas.append(f"={layout.ref(sheet, closing_key, prior_col)}")
    return formulas


def year_header_links(sheet: str, header_row: int, cols: Sequence[str]) -> list[str]:
    """Formulas pulling one sheet's year labels from another sheet's header row.

    A year header is a label rather than a number, but the smoke test is right
    to insist nothing in F:J on a statement sheet is a constant: six sheets
    each holding their own copy of "FY2027" is six places to change a year.
    Every forecast sheet's header therefore links to the Assumptions header,
    which is the one place the forecast years are written down.

    `header_row` is read off the writing cursor of the sheet being linked to,
    never hardcoded, so the row-2 convention is observed rather than assumed.
    """
    return [f"='{sheet}'!{col}${header_row}" for col in cols]


def choose_scenario(switch_ref: str, labels: Sequence[str], options: Sequence[str]) -> str:
    """``=CHOOSE(MATCH(<switch>,{"Bear";"Base";"Bull"},0), <bear>, <base>, <bull>)``.

    `labels` and `options` must be in the same order; the caller supplies
    both from one ordered constant so they cannot fall out of step.
    """
    if len(labels) != len(options):
        raise ValueError(
            f"choose_scenario needs one option per label, got "
            f"{len(labels)} labels and {len(options)} options"
        )
    cases = ";".join(f'"{label}"' for label in labels)
    return f"=CHOOSE(MATCH({switch_ref},{{{cases}}},0),{','.join(options)})"
