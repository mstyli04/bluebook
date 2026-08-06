"""Assemble the workbook: `build_workbook(historicals, scenario_name, path)`.

--------------------------------------------------------------------------
Why the build runs twice
--------------------------------------------------------------------------
Formulas address rows through `Layout`, which only knows a row once a writer
has written it. That is fine for a chain of sheets, but this model is not a
chain: ``IS!tax`` reads ``Schedules!debt_interest`` and
``Schedules!cash_generated`` reads ``IS!tax`` back. Whichever of the two
sheets is written first, some of its formulas point at rows that do not exist
yet — the cycle is in the model, not in the code, and no ordering removes it.

So the build runs the identical sheet-writing code twice:

* **Pass 1** writes into a throwaway workbook with a `_ProbeLayout`, which
  answers `row_of` for keys not yet registered by returning a sentinel row.
  The formulas this pass produces are wrong and are discarded; the row
  registrations it accumulates are what the pass is for.
* **Pass 2** writes into the real workbook against a fresh `Layout`, but
  resolves every reference through pass 1's now fully-populated layout. No
  lookup can hit the sentinel, because every key exists by then.

Both passes execute the same code in the same order, so they register the
same rows — and rather than trust that, `build_workbook` compares the two
layouts before saving and refuses to write a workbook whose formulas could
be pointing one row off.

--------------------------------------------------------------------------
Iterative calculation
--------------------------------------------------------------------------
The finished workbook contains no circular reference: `INTEREST_BASIS` is
``"opening"``, so interest depends only on the prior year's closing balance and
every cell resolves in a single pass. Iterative calculation is switched on
anyway, with the count and delta Task 2's spike verified LibreOffice honours.

Retaining it on an acyclic workbook is deliberate, not leftover. It costs
nothing — a workbook with no cycle iterates once whatever the setting — and it
means an editor who later reintroduces a circularity (charging interest on
average debt is the obvious candidate, and it was the basis until Task 12 fix
round 1) gets a converged answer rather than `Err:522` across the financing
block. What it does NOT do is make such an edit safe: LibreOffice resolves only
the first circular group in a chain of them, which is why the basis was changed
in the first place. That measurement, its twelve-cell reproduction and the
reasoning are in `sheet_schedules.py`'s docstring, `schedules/debt.py`,
`docs/superpowers/spike-circularity.md` and
`tests/test_libreoffice_iteration_limits.py`.
"""

from __future__ import annotations

from pathlib import Path

import openpyxl
from openpyxl.workbook.workbook import Workbook

from bluebook.assumptions import FORECAST_YEARS, SCENARIOS
from bluebook.inputs.schema import HistoricalYear
from bluebook.workbook.formulas import year_header_links
from bluebook.workbook.layout import FCST_COLS, HIST_COLS, Layout
from bluebook.workbook.sheet import SheetWriter
from bluebook.workbook.sheet_assumptions import write_assumptions
from bluebook.workbook.sheet_comps import EXTRA_COLS as COMPS_EXTRA_COLS
from bluebook.workbook.sheet_comps import write_comps
from bluebook.workbook.sheet_dcf import write_dcf
from bluebook.workbook.sheet_historicals import write_historicals
from bluebook.workbook.sheet_lbo import write_lbo
from bluebook.workbook.sheet_schedules import write_schedules
from bluebook.workbook.sheet_sensitivity import write_sensitivity
from bluebook.workbook.sheet_statements import (
    write_balance_sheet,
    write_cash_flow,
    write_income_statement,
)

# Tab order. The three placeholder-free sheets an interviewer opens first
# (Cover, Checks) lead; the statements sit in the middle; the valuation
# output sheets Tasks 13 and 14 fill come last.
SHEET_ORDER = (
    "Cover",
    "Checks",
    "Assumptions",
    "Historicals",
    "IS",
    "BS",
    "CF",
    "Schedules",
    "DCF",
    "Sensitivity",
    "Comps",
    "LBO",
    "Football Field",
)

# Sheets Task 14 fills in. Written here with a title and nothing else, so the
# tab order is fixed now and that task only adds rows. Task 13 filled DCF,
# Sensitivity, Comps and LBO, which is why they are no longer in this list —
# `Layout.register` would refuse a second title row on a sheet a writer owns.
PLACEHOLDER_TITLES = {
    "Checks": "Checks — integrity tests (Task 14)",
    "Football Field": "Football field — valuation ranges (Task 14)",
}

COVER_TITLE = "Greggs plc — three-statement operating model and valuation"

# Notes written to the Cover sheet as row labels, no values. The financing
# assumption is here because the Task 8 review ruled it must be disclosed.
# Checked against `reference.py` at this commit, ON THE OPENING INTEREST BASIS
# (the figures moved when the basis changed, so they were recomputed rather
# than carried over): forecast borrowings peak in FY2028 in all three
# scenarios, at £190.2m (Bear) / £207.1m (Base) / £210.9m (Bull) against the
# £100m facility drawn on at FY2025 — 1.9x to 2.1x it — while peak-year
# leverage is 0.56x / 0.48x / 0.40x that year's EBITDA.
COVER_NOTES = (
    ("cover_units", "All figures £m unless stated. Reported figures are post-IFRS 16."),
    (
        "cover_scenario",
        "Scenario switch: Assumptions!C3 (Bear / Base / Bull). Changing it re-drives "
        "every forecast, schedule and valuation in this workbook.",
    ),
    (
        "cover_iteration",
        "There are no circular references: interest on borrowings is charged on "
        "the opening balance, so the workbook recalculates in a single pass. "
        "Iterative calculation is enabled anyway (100 iterations, 0.0001 delta) "
        "so that a later edit introducing a circularity converges rather than "
        "erroring.",
    ),
    (
        "cover_financing",
        "FINANCING ASSUMPTION: the revolving credit facility is assumed to be "
        "upsized. Forecast borrowings peak in FY2028 in every scenario, at "
        "roughly twice the £100m facility drawn against at FY2025. Peak-year "
        "leverage stays modest at 0.4x-0.6x EBITDA, so the upsize is an "
        "assumption about facility availability, not about solvency.",
    ),
    (
        "cover_estimates",
        "The risk-free rate, equity risk premium, beta and RCF credit spread are "
        "reasoned judgement estimates, not sourced figures. Every other input is "
        "either transcribed from a filing (see Historicals, column L) or derived "
        "from those transcriptions.",
    ),
)

LABEL_COL_WIDTH = 56.0
COVER_LABEL_COL_WIDTH = 110.0
DATA_COL_WIDTH = 13.0
SOURCE_COL_WIDTH = 44.0

ITERATE_COUNT = 100
ITERATE_DELTA = 0.0001

# Row a `_ProbeLayout` reports for a key that pass 1 has not registered yet.
# Any row would do — pass 1's formulas are thrown away — but a row well past
# the end of every sheet makes a leaked probe reference obvious rather than
# plausible if one ever survived into a saved file.
_PROBE_ROW = 9999


class _ProbeLayout(Layout):
    """A `Layout` that answers `row_of` for keys it has not registered yet.

    Pass 1 of the build exists only to learn row positions, and it has to run
    the real sheet code to do that. That code builds formulas through `ref()`,
    and on the first pass some of those references point at rows that do not
    exist yet — see this module's docstring on the IS/Schedules cycle.
    Returning a sentinel lets the pass finish; the formulas it produces are
    discarded with the throwaway workbook it writes them into.
    """

    def row_of(self, sheet: str, key: str) -> int:
        try:
            return super().row_of(sheet, key)
        except KeyError:
            return _PROBE_ROW


def _write_sheets(
    historicals: list[HistoricalYear],
    scenario_name: str,
    layout: Layout,
    ref_layout: Layout,
) -> Workbook:
    """Create every sheet, in tab order, and write the ones this task owns.

    `layout` registers the rows written; `ref_layout` resolves the references
    those rows contain. Pass 1 supplies the same `_ProbeLayout` for both; pass
    2 supplies a fresh `Layout` and pass 1's result.
    """
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    sheets = {name: wb.create_sheet(name) for name in SHEET_ORDER}

    cover = SheetWriter(sheets["Cover"], layout, historical=True)
    cover.title(COVER_TITLE)
    cover.blank()
    for key, note in COVER_NOTES:
        # Label only, no values: the note IS the row.
        cover.input_row(key, note, [])

    for name, title in PLACEHOLDER_TITLES.items():
        SheetWriter(sheets[name], layout).title(title)

    # Assumptions is written first because it is the one sheet that holds the
    # forecast year labels as text; every other forecast sheet links to them.
    year_header_row = write_assumptions(
        SheetWriter(sheets["Assumptions"], layout),
        ref_layout,
        scenario_name,
        FORECAST_YEARS,
    )
    year_links = year_header_links("Assumptions", year_header_row, FCST_COLS)

    write_historicals(
        SheetWriter(sheets["Historicals"], layout, historical=True),
        ref_layout,
        historicals,
    )
    write_income_statement(SheetWriter(sheets["IS"], layout), ref_layout, year_links)
    write_balance_sheet(SheetWriter(sheets["BS"], layout), ref_layout, year_links)
    write_cash_flow(SheetWriter(sheets["CF"], layout), ref_layout, year_links)
    write_schedules(SheetWriter(sheets["Schedules"], layout), ref_layout, year_links)

    # Comps before DCF because the DCF's exit-multiple memo reads the peer
    # median EV/EBIT, and Sensitivity and LBO after both because they read the
    # DCF's rows. The order is presentational only — Comps also reads the DCF's
    # terminal capital intensity back, and it is the two-pass build rather than
    # any ordering that lets a pair of sheets reference each other.
    write_comps(SheetWriter(sheets["Comps"], layout), ref_layout)
    write_dcf(SheetWriter(sheets["DCF"], layout), ref_layout, year_links)
    write_sensitivity(SheetWriter(sheets["Sensitivity"], layout), ref_layout)
    write_lbo(SheetWriter(sheets["LBO"], layout), ref_layout, year_links)

    _apply_presentation(wb)
    return wb


def _apply_presentation(wb: Workbook) -> None:
    """Column widths and frozen panes — labels and year headers stay visible."""
    for ws in wb.worksheets:
        ws.column_dimensions["A"].width = 4.0
        ws.column_dimensions["B"].width = (
            COVER_LABEL_COL_WIDTH if ws.title == "Cover" else LABEL_COL_WIDTH
        )
        # The year grid, plus the columns the Comps sheet uses beyond it for its
        # peer statistics — taken from that module so the two cannot fall out of
        # step if the peer table widens.
        for col in HIST_COLS + FCST_COLS + COMPS_EXTRA_COLS:
            ws.column_dimensions[col].width = DATA_COL_WIDTH
        ws.column_dimensions["L"].width = SOURCE_COL_WIDTH
        # Freezing at C3 holds the label column and the year header in view.
        ws.freeze_panes = "C3"


def build_workbook(
    historicals: list[HistoricalYear],
    scenario_name: str,
    path: Path | str,
) -> Path:
    """Write the Greggs model to `path` as live Excel formulas and return it.

    `scenario_name` sets the starting position of the switch in
    ``Assumptions!C3``; all three scenarios' driver paths are written to the
    sheet regardless, so the switch is a real toggle and not a rebuild.
    """
    if scenario_name not in SCENARIOS:
        raise ValueError(
            f"scenario_name must be one of {sorted(SCENARIOS)}, got {scenario_name!r}"
        )
    if not historicals:
        raise ValueError("historicals must hold at least one reported year")

    # Pass 1: learn the row positions (see the module docstring).
    probe = _ProbeLayout()
    _write_sheets(historicals, scenario_name, probe, probe)

    # Pass 2: the same rows, with every reference resolved against pass 1.
    layout = Layout()
    wb = _write_sheets(historicals, scenario_name, layout, probe)

    if layout.items() != probe.items():
        differences = {
            key: (probe.items().get(key), layout.items().get(key))
            for key in set(probe.items()) | set(layout.items())
            if probe.items().get(key) != layout.items().get(key)
        }
        raise RuntimeError(
            "the two build passes registered different rows, so formulas written "
            f"in pass 2 may address the wrong cells: {differences}"
        )

    # Kept on although the workbook is acyclic: free here, and it turns a
    # future reintroduced circularity into a converged answer rather than
    # `Err:522`. See the module docstring for what it does not protect against.
    wb.calculation.iterate = True
    wb.calculation.iterateCount = ITERATE_COUNT
    wb.calculation.iterateDelta = ITERATE_DELTA

    path = Path(path)
    wb.save(path)
    return path
