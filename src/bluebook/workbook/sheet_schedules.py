"""The Schedules sheet: the four roll-forwards, plus equity and the debt sweep.

One sheet, six blocks, in `reference.py`'s computation order: working
capital, fixed assets, intangibles, leases, equity and distributions, then
debt and cash. Every opening balance links to the last historical year's
actual — `reference.py`'s rule that no forecast starts from a fresh sheet is
visible here as a green link into Historicals in the FY2026 column of every
opening row.

--------------------------------------------------------------------------
The debt schedule, and the circularity that is deliberately not here
--------------------------------------------------------------------------
`schedules/debt.py` charges interest on the OPENING debt balance, so this
block is acyclic and every cell in it recalculates in one pass:

    debt_interest            = debt_opening * rate
    cash_before_debt_service = cash_opening + cash_generated - debt_interest
    debt_repayment           = MAX(0, MIN(debt_opening, cbds - min_cash))
    revolver_draw            = MAX(0, min_cash - cbds)
    debt_closing             = debt_opening - debt_repayment + revolver_draw

`debt_interest` reads the opening balance above it, never the closing balance
below, and nothing on any sheet reads back into a cell that feeds it — there is
no `AVERAGE(` on this sheet at all. The
outer tax and dividend loop that `reference.py` solves by iteration is
likewise not a loop here: `cash_generated` reads ``IS!tax``, `dividends` reads
``IS!net_income``, and both are downstream of an interest figure that was
already fixed by the opening balance.

**This is a reversal, and the reason belongs on the sheet.** The basis was
``"average"`` until Task 12 fix round 1, on the strength of Task 2's spike
verifying that headless LibreOffice honours ``wb.calculation.iterate``. That is
true, and it does not generalise: the spike's circularity was a single
two-cell loop, and LibreOffice 24.2.7 resolves exactly that. Measured on the
average-basis version of this very block, it resolved FY2026 exactly (balance
check -9.6e-07) and left FY2027-30 each reading the prior year's closing debt
frozen at its seed value, so borrowings read 25.0 for the rest of the
forecast. ``iterateCount`` at 10,000, ``iterateDelta`` at 1e-12 and seven
sequential recalculations all returned bit-identical answers — a stable wrong
result, not an unfinished one — and reshaping the block so each year's loop
was a single simple chain bought FY2026 alone. A five-year average-balance
schedule is inherently a chain of five circular groups, and LibreOffice
resolves only the first link of a chain (it also freezes the second branch of
any branched loop). Both behaviours are pinned in
`tests/test_libreoffice_iteration_limits.py`, twelve cells apiece, and the
reasoning is recorded in `schedules/debt.py` and
`docs/superpowers/spike-circularity.md`.

The cost of the opening basis is real: it understates interest in a year of
rising debt, by roughly half a year's interest on the increase. What it buys
is that Task 15 can cross-check every cell of this block against the Python
model, instead of having to exclude the one block whose construction was the
reason for choosing "average".

Iterative calculation is still switched on in `build.py`. See the note there
for why a now-acyclic workbook keeps it.
"""

from __future__ import annotations

from bluebook.workbook.formulas import aref, roll_forward
from bluebook.workbook.layout import FCST_COLS, HIST_COLS, Layout
from bluebook.workbook.sheet import SheetWriter
from bluebook.workbook.styles import MONEY_FORMAT

SHEET = "Schedules"
ASSUMPTIONS = "Assumptions"
HISTORICALS = "Historicals"
IS = "IS"

# Opening balances come from the last historical year.
LAST_ACTUAL_COL = HIST_COLS[-1]

# Single-value driver cells on Assumptions all sit in this column.
DRIVER_COL = HIST_COLS[0]


def write_schedules(writer: SheetWriter, ref_layout: Layout, year_labels) -> None:
    """Write the Schedules sheet. `writer` must be in forecast mode."""
    layout = ref_layout

    def me(key: str, col: str) -> str:
        """A reference to another row of this sheet, same column."""
        return layout.ref(SHEET, key, col)

    def driver(key: str) -> str:
        """A single-value driver on Assumptions, absolute so it is column-safe."""
        return aref(layout, ASSUMPTIONS, key, DRIVER_COL)

    def path(key: str, col: str) -> str:
        """A per-year driver on Assumptions, same column."""
        return layout.ref(ASSUMPTIONS, key, col)

    def actual(key: str) -> str:
        """The last reported year's figure for a line on Historicals."""
        return layout.ref(HISTORICALS, key, LAST_ACTUAL_COL)

    def statement(key: str, col: str) -> str:
        return layout.ref(IS, key, col)

    def row(key: str, label: str, build, fmt: str = MONEY_FORMAT, *, is_link: bool = False) -> None:
        writer.formula_row(key, label, [build(col) for col in FCST_COLS], fmt, is_link=is_link)

    # The first block gets no section header of its own: the layout
    # convention puts the first data row at row 3, so a header there would
    # push it to row 4. The sheet title names the first block instead; every
    # later block is introduced by a header after a blank row.
    writer.title("Schedules — working capital, then fixed assets, leases, equity, debt")
    writer.year_header(year_labels)

    # --- Working capital --------------------------------------------------
    row(
        "inventories",
        "Inventories (cost of sales x inventory days / 365)",
        lambda c: f"={statement('cost_of_sales', c)}*{driver('inventory_days')}"
                  f"/{driver('days_in_year')}",
    )
    row(
        "receivables",
        "Trade receivables (revenue x receivable days / 365)",
        lambda c: f"={statement('revenue', c)}*{driver('receivable_days')}"
                  f"/{driver('days_in_year')}",
    )
    row(
        "payables",
        "Trade payables (cost of sales x payable days / 365)",
        lambda c: f"={statement('cost_of_sales', c)}*{driver('payable_days')}"
                  f"/{driver('days_in_year')}",
    )
    row(
        "net_working_capital",
        "Net working capital",
        lambda c: f"={me('inventories', c)}+{me('receivables', c)}-{me('payables', c)}",
    )
    # Year one opens on the FY2025 actual NWC, built from the same three
    # balance sheet lines the forecast movements are measured against. Getting
    # this wrong (opening at zero) would make the FY2026 movement the whole
    # FY2026 NWC balance instead of the movement off FY2025.
    writer.formula_row(
        "nwc_opening",
        "Opening net working capital",
        roll_forward(
            layout,
            f"={actual('net_working_capital')}",
            "net_working_capital",
            sheet=SHEET,
        ),
        MONEY_FORMAT,
    )
    row(
        "change_in_nwc",
        "Increase in net working capital (cash outflow when positive)",
        lambda c: f"={me('net_working_capital', c)}-{me('nwc_opening', c)}",
    )

    # --- Fixed assets -----------------------------------------------------
    writer.blank()
    writer.title("Fixed assets (PP&E)")
    writer.formula_row(
        "ppe_opening",
        "Opening PP&E",
        roll_forward(layout, f"={actual('ppe')}", "ppe_closing", sheet=SHEET),
        MONEY_FORMAT,
    )
    # capex_pct_revenue is a TOTAL capex ratio; only the PP&E share reaches
    # this schedule. The intangible share is spent in the block below and the
    # two are summed back to the total, so nothing is lost or double-counted.
    row(
        "ppe_capex",
        "PP&E capex (revenue x total capex % x PP&E share)",
        lambda c: f"={statement('revenue', c)}*{path('capex_pct_revenue', c)}"
                  f"*{driver('ppe_capex_share')}",
    )
    row(
        "ppe_depreciation",
        "Depreciation of PP&E (rate on opening balance)",
        lambda c: f"={me('ppe_opening', c)}*{driver('ppe_depreciation_rate')}",
    )
    row(
        "ppe_closing",
        "Closing PP&E",
        lambda c: f"={me('ppe_opening', c)}+{me('ppe_capex', c)}-{me('ppe_depreciation', c)}",
    )

    # --- Intangibles ------------------------------------------------------
    writer.blank()
    writer.title("Intangible assets")
    writer.formula_row(
        "intangibles_opening",
        "Opening intangibles",
        roll_forward(layout, f"={actual('intangibles')}", "intangibles_closing", sheet=SHEET),
        MONEY_FORMAT,
    )
    row(
        "intangible_capex",
        "Intangible additions (revenue x total capex % x intangible share)",
        lambda c: f"={statement('revenue', c)}*{path('capex_pct_revenue', c)}"
                  f"*{driver('intangible_capex_share')}",
    )
    # Charged on the opening balance, exactly as PP&E and ROU depreciation
    # are, so both sides of the roll-forward accrue on the same basis.
    row(
        "amortisation",
        "Amortisation (rate on opening balance)",
        lambda c: f"={me('intangibles_opening', c)}*{driver('amortisation_rate')}",
    )
    row(
        "intangibles_closing",
        "Closing intangibles",
        lambda c: f"={me('intangibles_opening', c)}+{me('intangible_capex', c)}"
                  f"-{me('amortisation', c)}",
    )
    row(
        "total_capex",
        "Total cash capex (PP&E + intangible)",
        lambda c: f"={me('ppe_capex', c)}+{me('intangible_capex', c)}",
    )

    # --- Leases -----------------------------------------------------------
    writer.blank()
    writer.title("Leases (IFRS 16)")
    writer.formula_row(
        "rou_opening",
        "Opening right-of-use assets",
        roll_forward(layout, f"={actual('rou_assets')}", "rou_closing", sheet=SHEET),
        MONEY_FORMAT,
    )
    row(
        "rou_additions",
        "New ROU asset additions (revenue x ROU additions %)",
        lambda c: f"={statement('revenue', c)}*{path('rou_additions_pct_revenue', c)}",
    )
    row(
        "rou_depreciation",
        "Depreciation of ROU assets (rate on opening balance)",
        lambda c: f"={me('rou_opening', c)}*{driver('rou_depreciation_rate')}",
    )
    row(
        "rou_closing",
        "Closing right-of-use assets",
        lambda c: f"={me('rou_opening', c)}+{me('rou_additions', c)}-{me('rou_depreciation', c)}",
    )
    writer.formula_row(
        "lease_liability_opening",
        "Opening lease liabilities",
        roll_forward(
            layout, f"={actual('lease_liabilities')}", "lease_liability_closing", sheet=SHEET
        ),
        MONEY_FORMAT,
    )
    # A real P&L finance cost, but it does NOT capitalise into the liability:
    # under IFRS 16 the interest accrued and the interest paid are the same
    # figure in the same period, so they cancel in the roll-forward below.
    row(
        "lease_interest",
        "Lease interest (discount rate on opening liability)",
        lambda c: f"={me('lease_liability_opening', c)}*{driver('lease_discount_rate')}",
    )
    row(
        "lease_principal_paid",
        "Lease principal repaid (opening / implied term + additions x fit rate)",
        lambda c: f"={me('lease_liability_opening', c)}/{driver('implied_lease_term_years')}"
                  f"+{me('rou_additions', c)}*{driver('lease_additions_principal_rate')}",
    )
    row(
        "lease_liability_closing",
        "Closing lease liabilities",
        lambda c: f"={me('lease_liability_opening', c)}+{me('rou_additions', c)}"
                  f"-{me('lease_principal_paid', c)}",
    )

    # --- Equity and distributions -----------------------------------------
    writer.blank()
    writer.title("Equity and distributions")
    # A loss-making year pays nothing; it does not collect from shareholders.
    row(
        "dividends",
        "Dividends declared (payout ratio on net income, floored at nil)",
        lambda c: f"=MAX({statement('net_income', c)},0)*{driver('dividend_payout_ratio')}",
    )
    writer.formula_row(
        "equity_opening",
        "Opening shareholders' equity",
        roll_forward(layout, f"={actual('equity')}", "equity_closing", sheet=SHEET),
        MONEY_FORMAT,
    )
    row(
        "equity_closing",
        "Closing shareholders' equity",
        lambda c: f"={me('equity_opening', c)}+{statement('net_income', c)}"
                  f"-{me('dividends', c)}",
    )

    # --- Debt and cash (acyclic — see the module docstring) ---------------
    writer.blank()
    writer.title("Debt and cash")
    row(
        "cash_generated",
        "Cash generated before financing",
        lambda c: f"={statement('ebitda', c)}-{me('change_in_nwc', c)}-{me('total_capex', c)}"
                  f"-{me('lease_principal_paid', c)}-{me('lease_interest', c)}"
                  f"-{statement('tax', c)}-{me('dividends', c)}",
    )
    writer.formula_row(
        "debt_opening",
        "Opening borrowings",
        roll_forward(layout, f"={actual('borrowings')}", "debt_closing", sheet=SHEET),
        MONEY_FORMAT,
    )
    writer.formula_row(
        "cash_opening",
        "Opening cash",
        roll_forward(layout, f"={actual('cash')}", "cash_closing", sheet=SHEET),
        MONEY_FORMAT,
    )
    row(
        "cash_before_interest",
        "Cash available before interest",
        lambda c: f"={me('cash_opening', c)}+{me('cash_generated', c)}",
    )
    # On the OPENING balance, so this cell does not read the closing balance
    # further down the block and the whole block stays acyclic. That is
    # the owner ruling behind `INTEREST_BASIS = "opening"` — see the module
    # docstring, `schedules/debt.py`, and the LibreOffice measurements in
    # `tests/test_libreoffice_iteration_limits.py`.
    row(
        "debt_interest",
        "Interest on borrowings (rate on opening debt)",
        lambda c: f"={me('debt_opening', c)}*{driver('interest_rate_debt')}",
    )
    row(
        "cash_before_debt_service",
        "Cash available before debt service",
        lambda c: f"={me('cash_before_interest', c)}-{me('debt_interest', c)}",
    )
    # Surplus above the cash floor repays debt, but never more than is
    # outstanding; a shortfall draws exactly enough to hold cash at the floor.
    #
    # MAX/MIN rather than the pair of IFs on a shared condition that
    # `schedules/debt.py` uses. Algebraically identical — above the floor the
    # draw's MAX is nil, below it the repayment's MAX is — but the two rows are
    # then mutually exclusive by construction rather than by agreeing about a
    # condition, so they cannot disagree if one is edited.
    row(
        "debt_repayment",
        "Repayment of borrowings",
        lambda c: f"=MAX(0,MIN({me('debt_opening', c)},"
                  f"{me('cash_before_debt_service', c)}-{driver('minimum_cash')}))",
    )
    row(
        "revolver_draw",
        "Revolver draw",
        lambda c: f"=MAX(0,{driver('minimum_cash')}-{me('cash_before_debt_service', c)})",
    )
    row(
        "debt_closing",
        "Closing borrowings",
        lambda c: f"={me('debt_opening', c)}-{me('debt_repayment', c)}"
                  f"+{me('revolver_draw', c)}",
    )
    row(
        "cash_closing",
        "Closing cash (debt schedule's own track)",
        lambda c: f"={me('cash_before_debt_service', c)}-{me('debt_repayment', c)}"
                  f"+{me('revolver_draw', c)}",
    )
