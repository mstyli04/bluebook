"""The Sensitivity sheet: two 5x5 grids, both built as explicit formula grids.

--------------------------------------------------------------------------
Why these are formula grids and not Excel Data Tables
--------------------------------------------------------------------------
A Data Table is the native tool for this and it is not available: openpyxl
cannot write the `<dataTable>` cell records, and LibreOffice — which is what
recalculates this workbook in the test suite — does not reliably evaluate them
on load even where they are present. So each of the fifty cells here recomputes
its own answer from its own axis pair, and the whole sheet recalculates in the
same single pass as the rest of the workbook.

--------------------------------------------------------------------------
Each cell re-derives the TERMINAL YEAR, not just the Gordon denominator
--------------------------------------------------------------------------
This is the part a sensitivity grid usually gets wrong. Perpetuity growth does
not appear only in ``FCF x (1 + g)/(WACC - g)``: in this model ``g`` sets the
whole terminal year. The sustaining capex intensity is ``p(g + d)/(1 + g)``,
the steady-state depreciation charges are ``d x p/(1 + g)``, the working
capital movement is ``nwc x g/(1 + g)``, and even the PP&E anchor itself is
``(FY2030 PP&E/revenue)/(1 + g) ** (1/d)``. Holding the terminal year fixed and
moving only the denominator would price a cash flow the model does not produce.

So the block headed "Workings" re-runs `valuation.terminal_year` at each of the
five growth rates, one column per rate, and each grid cell reads the column
under its own growth rate. The centre column is the live case, and the tie row
at the bottom of that block is what proves it: the centre column's terminal FCF
less the DCF's own terminal FCF must be nil, and it is nil exactly, in every
scenario. If a re-derivation here ever drifts from `valuation.terminal_year`,
that row stops being nil.

Two quantities the axes do NOT change, and both are load-bearing:

* the **explicit five years** of unlevered free cash flow, which depend on
  neither axis, so they are re-DISCOUNTED at each cell's WACC but not rebuilt;
* the **terminal EBITDA**, which is the terminal margin applied to the FY2030
  revenue level. The re-basing touches the investment and depreciation
  intensities, not the P&L margin, which is why grid 2 has a single divisor.

The excess-PP&E tax shield is rebuilt inside each cell of grid 1 because it is
the one term that depends on BOTH axes: its decay factor on the WACC, and its
excess on the growth-dependent PP&E anchor.

The workings sit BELOW the grids rather than above them. That means the grid
rows reference rows below themselves, which no other sheet in this workbook
does — accepted here for two reasons: the plan fixes the first grid's body at
``D5:H9``, which leaves no room for the workings block above it; and a
sensitivity sheet is read for its grid, so the output belongs at the top.

--------------------------------------------------------------------------
Anchoring, and why the fifty cells are one formula
--------------------------------------------------------------------------
Every grid cell reads its WACC from column C of its own row (``$C7``) and its
growth rate from the axis row above the grid (``D$4``), which is exactly the
anchoring a formula copied across a block would carry. All twenty-five cells of
a grid are therefore the same formula bar entry, so a reader checks one cell and
then checks that the block is uniform. Those rows come from the writer's cursor
and from what `SheetWriter.formula_row` returns, never from arithmetic — see
`formulas.cell`.

--------------------------------------------------------------------------
The axis steps, and why the corner is safe
--------------------------------------------------------------------------
WACC moves +/-50bp and +/-100bp, growth +/-25bp and +/-50bp: the conventional
spreads, and the only literals on the sheet. They are presentation conventions
rather than model inputs, and each appears inside a formula that starts from the
live value, so the centre of both axes is the model's own case by construction.
The Gordon denominator is narrowest at the top-right corner — lowest WACC
against highest growth — where it is still 6.73% - 2.50% = 4.23%, so no cell
divides by anything near zero. Widening either axis until ``g`` approached
``WACC`` would print a meaningless number rather than an error, which is a
reason to keep the steps where they are.
"""

from __future__ import annotations

from typing import Callable

from bluebook.workbook.formulas import aref, cell
from bluebook.workbook.layout import FCST_COLS, HIST_COLS, Layout
from bluebook.workbook.sheet import SheetWriter
from bluebook.workbook.sheet_comps import MEDIAN_COL
from bluebook.workbook.styles import (
    MONEY_FORMAT,
    MULTIPLE_FORMAT,
    PENCE_FORMAT,
    PERCENT_FORMAT,
)

SHEET = "Sensitivity"
ASSUMPTIONS = "Assumptions"
COMPS = "Comps"
DCF = "DCF"
IS = "IS"
BS = "BS"

# The WACC axis runs down column C; the five value columns are D:H, which is
# where the plan's test requires the first grid's body to land.
AXIS_COL = HIST_COLS[0]
GRID_COLS = ("D", "E", "F", "G", "H")
ROW_COLS = (AXIS_COL,) + GRID_COLS

# The terminal anchors are struck on FY2030 and the excess PP&E on FY2029, as
# on the DCF sheet.
FINAL_COL = FCST_COLS[-1]
PENULTIMATE_COL = FCST_COLS[-2]

# Offsets off the live WACC and the live perpetuity growth rate, written as
# signed strings because they go straight into a formula that starts from the
# live cell. The empty string is the centre: no offset at all, not "+0".
WACC_OFFSETS = ("-0.01", "-0.005", "", "+0.005", "+0.01")
GROWTH_OFFSETS = ("-0.005", "-0.0025", "", "+0.0025", "+0.005")
WACC_LABELS = (
    "WACC less 100bp",
    "WACC less 50bp",
    "WACC (the model's own)",
    "WACC plus 50bp",
    "WACC plus 100bp",
)
# The centre column of the grids, derived from the offsets rather than written
# as 2, so widening an axis cannot leave the tie row reading an off-centre
# column and silently passing.
CENTRE_INDEX = WACC_OFFSETS.index("")
CENTRE_COL = GRID_COLS[CENTRE_INDEX]

# Grid 2 shares grid 1's WACC axis, so its row labels have to differ from grid
# 1's: `Layout` allows two rows to carry the same label, and anything that looks
# a row up by name then finds two. They are also deliberately not grid 1's label
# plus a suffix, because a label that is another label plus a suffix is just as
# ambiguous to a prefix search.
MULTIPLE_GRID_LABELS = tuple(f"Implied terminal multiple at {label}" for label in WACC_LABELS)

# The bridge is in £m and the price is quoted in pence.
PENCE_PER_POUND = "100"


def write_sensitivity(writer: SheetWriter, ref_layout: Layout) -> None:
    """Write the Sensitivity sheet. `writer` names its own columns."""
    layout = ref_layout

    def dcf(key: str) -> str:
        """A single-value row on the DCF sheet, absolute."""
        return aref(layout, DCF, key, HIST_COLS[0])

    def dcf_year(key: str, col: str) -> str:
        """A per-year row on the DCF sheet, absolute so it is copy-safe."""
        return aref(layout, DCF, key, col)

    def driver(key: str) -> str:
        """A single-value driver on Assumptions."""
        return aref(layout, ASSUMPTIONS, key, HIST_COLS[0])

    def workings(key: str, col: str) -> str:
        """A cell of the workings block, in one growth-rate column."""
        return layout.ref(SHEET, key, col)

    writer.title("Sensitivity — every cell recomputed from its own axis pair")
    # Row 2 is blank: this sheet has no year axis to label there, and each grid
    # carries its own axis labels on the two rows immediately above it.
    writer.blank()

    # --- Grid 1: implied share price ---------------------------------------
    writer.title(
        "Implied share price (p) — perpetuity growth across, WACC down. "
        "The centre cell is the DCF's own answer."
    )
    growth_row = writer.formula_row(
        "growth_axis",
        "Perpetuity growth (across)",
        [f"={dcf('perpetuity_growth')}{offset}" for offset in GROWTH_OFFSETS],
        PERCENT_FORMAT,
        cols=GRID_COLS,
    )

    def growth(col: str) -> str:
        """This column's growth rate, anchored to the axis row (``D$4``)."""
        return cell(col, growth_row, lock_row=True)

    def grid_row(
        index: int,
        key: str,
        build: Callable[[str, str], str],
        fmt: str,
        labels: tuple[str, ...] = WACC_LABELS,
    ) -> int:
        """One grid line: its WACC in column C, then its five cells in D:H.

        `build(wacc_ref, col)` returns one cell's formula. The row is read off
        the writer's cursor BEFORE the row is written, because the WACC every
        cell in it reads is a cell on the very row about to be written; no row
        number is computed here.

        `labels` is which of the two label sets to take this row's label from.
        The axis is the same axis in both grids, so without two sets the labels
        would be identical, and a duplicated label in column B is a row that
        cannot be addressed by name — which is how a test ends up checking the
        wrong grid.
        """
        row = writer.row
        wacc_ref = cell(AXIS_COL, row, lock_col=True)
        values = [f"={dcf('wacc')}{WACC_OFFSETS[index]}"]
        values += [build(wacc_ref, col) for col in GRID_COLS]
        written = writer.formula_row(key, labels[index], values, fmt, cols=ROW_COLS)
        # The axis cell is a rate while the five beside it are not, and
        # `formula_row` applies one number format to a row. Restyling the axis
        # cell afterwards changes no value and skips no guard — the formula in
        # it was written through `formula_row` like every other cell here.
        writer.ws[f"{AXIS_COL}{written}"].number_format = PERCENT_FORMAT
        return written

    def price(wacc_ref: str, col: str) -> str:
        """Implied share price in pence at one (WACC, growth) pair."""
        g = growth(col)
        pv_explicit = "+".join(
            f"{dcf_year('unlevered_fcf', year_col)}"
            f"/(1+{wacc_ref})^{dcf_year('discount_period', year_col)}"
            for year_col in FCST_COLS
        )
        gordon = f"{workings('terminal_fcf', col)}*(1+{g})/({wacc_ref}-{g})"
        decay = f"(1-{driver('ppe_depreciation_rate')})/(1+{wacc_ref})"
        shield = (
            f"{driver('tax_rate')}*{driver('ppe_depreciation_rate')}"
            f"*{workings('excess_ppe', col)}*{decay}/(1-{decay})"
        )
        terminal_factor = f"(1+{wacc_ref})^{dcf_year('discount_period', FINAL_COL)}"
        return (
            f"=({pv_explicit}+({gordon}+{shield})/{terminal_factor}"
            f"-{dcf('net_debt')}-{dcf('lease_liabilities')})/{dcf('share_count')}"
            f"*{PENCE_PER_POUND}"
        )

    for index in range(len(WACC_LABELS)):
        grid_row(index, f"price_{index}", price, PENCE_FORMAT)

    # --- Grid 2: the terminal multiple each pair implies --------------------
    writer.blank()
    writer.title(
        "Implied terminal EV/EBITDA — the same pairs, read as the multiple the "
        "Gordon value puts on terminal EBITDA"
    )

    def implied_multiple(wacc_ref: str, col: str) -> str:
        """Gordon terminal value over terminal EBITDA at one axis pair.

        Terminal EBITDA depends on neither axis, so this grid differs from grid
        1 only in what it divides by. It is here because it is the number the
        peer evidence can be held against, and the two rows beneath it are that
        evidence.
        """
        g = growth(col)
        return (
            f"={workings('terminal_fcf', col)}*(1+{g})/({wacc_ref}-{g})"
            f"/{dcf('terminal_ebitda')}"
        )

    for index in range(len(WACC_LABELS)):
        grid_row(
            index, f"multiple_{index}", implied_multiple, MULTIPLE_FORMAT,
            MULTIPLE_GRID_LABELS,
        )

    writer.formula_row(
        "peer_median_ev_ebitda",
        "For comparison: peer median EV/EBITDA (a TRAILING multiple, from Comps)",
        [f"={aref(layout, COMPS, 'ev_ebitda', MEDIAN_COL)}"],
        MULTIPLE_FORMAT,
        cols=(AXIS_COL,),
        is_link=True,
    )
    writer.formula_row(
        "derived_exit_multiple",
        "For comparison: exit EV/EBITDA derived from the peer median EV/EBIT",
        [f"={aref(layout, COMPS, 'derived_exit_multiple', HIST_COLS[0])}"],
        MULTIPLE_FORMAT,
        cols=(AXIS_COL,),
        is_link=True,
    )

    # --- The workings both grids read --------------------------------------
    writer.blank()
    writer.title(
        "Workings — the terminal year rebuilt at each growth rate above, one "
        "column per rate, aligned with the grids"
    )

    def workings_row(key: str, label: str, build: Callable[[str], str], fmt: str) -> int:
        """One workings line: five columns, one per growth rate."""
        return writer.formula_row(
            key, label, [build(col) for col in GRID_COLS], fmt, cols=GRID_COLS
        )

    workings_row(
        "terminal_ppe_intensity",
        "Terminal PP&E / revenue (post-programme anchor at this growth rate)",
        lambda col: f"=({layout.ref(BS, 'ppe', FINAL_COL)}"
                    f"/{layout.ref(IS, 'revenue', FINAL_COL)})"
                    f"/(1+{growth(col)})^(1/{driver('ppe_depreciation_rate')})",
        PERCENT_FORMAT,
    )
    workings_row(
        "terminal_capex_pct_revenue",
        "Terminal total capex (% of revenue, sustaining at this growth rate)",
        lambda col: f"={workings('terminal_ppe_intensity', col)}"
                    f"*({growth(col)}+{driver('ppe_depreciation_rate')})"
                    f"/(1+{growth(col)})/{driver('ppe_capex_share')}",
        PERCENT_FORMAT,
    )
    # PP&E depreciation + ROU depreciation + amortisation, each at its own
    # steady state, in that order — the order `valuation.terminal_year` sums
    # them in, so the two agree to the last bit and not merely to the eye.
    workings_row(
        "terminal_da_pct_revenue",
        "Terminal D&A (% of revenue: PP&E + ROU depreciation + amortisation)",
        lambda col: f"={driver('ppe_depreciation_rate')}"
                    f"*{workings('terminal_ppe_intensity', col)}/(1+{growth(col)})"
                    f"+{driver('rou_depreciation_rate')}*{dcf('terminal_rou_intensity')}"
                    f"/(1+{growth(col)})"
                    f"+{workings('terminal_capex_pct_revenue', col)}"
                    f"*{driver('intangible_capex_share')}*{driver('amortisation_rate')}"
                    f"/({growth(col)}+{driver('amortisation_rate')})",
        PERCENT_FORMAT,
    )
    workings_row(
        "terminal_da",
        "Terminal depreciation and amortisation",
        lambda col: f"={workings('terminal_da_pct_revenue', col)}*{dcf('terminal_revenue')}",
        MONEY_FORMAT,
    )
    workings_row(
        "terminal_ebit",
        "Terminal EBIT (terminal EBITDA less the D&A above)",
        lambda col: f"={dcf('terminal_ebitda')}-{workings('terminal_da', col)}",
        MONEY_FORMAT,
    )
    # ROU additions and the working capital movement are inlined rather than
    # given rows of their own: both are one product off an intensity that is
    # already on the DCF sheet, and two more five-column rows would have made
    # the block longer without making it more checkable.
    workings_row(
        "terminal_fcf",
        "Terminal unlevered free cash flow",
        lambda col: f"={workings('terminal_ebit', col)}*(1-{driver('tax_rate')})"
                    f"+{workings('terminal_da', col)}"
                    f"-{workings('terminal_capex_pct_revenue', col)}"
                    f"*{dcf('terminal_revenue')}"
                    f"-{dcf('terminal_rou_intensity')}"
                    f"*({growth(col)}+{driver('rou_depreciation_rate')})/(1+{growth(col)})"
                    f"*{dcf('terminal_revenue')}"
                    f"-{dcf('terminal_nwc_pct_revenue')}*{growth(col)}/(1+{growth(col)})"
                    f"*{dcf('terminal_revenue')}",
        MONEY_FORMAT,
    )
    workings_row(
        "excess_ppe",
        "Excess PP&E over this growth rate's re-based base, at FY2029",
        lambda col: f"={layout.ref(BS, 'ppe', PENULTIMATE_COL)}"
                    f"-{workings('terminal_ppe_intensity', col)}"
                    f"*{layout.ref(IS, 'revenue', PENULTIMATE_COL)}",
        MONEY_FORMAT,
    )
    writer.formula_row(
        "centre_column_tie",
        "Check: centre column's terminal FCF less the DCF's own (must be nil)",
        [f"={workings('terminal_fcf', CENTRE_COL)}-{dcf('terminal_fcf')}"],
        MONEY_FORMAT,
        cols=(AXIS_COL,),
    )
