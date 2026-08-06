"""The Schedules sheet: the four roll-forwards, plus equity and the debt solve.

One sheet, six blocks, in `reference.py`'s computation order: working
capital, fixed assets, intangibles, leases, equity and distributions, then
debt and cash. Every opening balance links to the last historical year's
actual — `reference.py`'s rule that no forecast starts from a fresh sheet is
visible here as a green link into Historicals in the FY2026 column of every
opening row.

--------------------------------------------------------------------------
The circular debt schedule, as Excel expresses it
--------------------------------------------------------------------------
`schedules/debt.py` charges interest on the *average* of the opening and
closing debt balance, which makes the year genuinely circular: interest needs
the closing balance, the closing balance needs the repayment or draw, the
repayment needs the cash left after interest. Python resolves it by
fixed-point iteration. The workbook does not resolve it at all — it simply
writes the circularity down and lets Excel's iterative calculation find the
same fixed point:

**KNOWN OPEN ISSUE — headless LibreOffice does not resolve this block.**
Task 2's spike verified LibreOffice honours ``wb.calculation.iterate`` on a
*single* circular cell pair, and that is all it verified. Measured during
Task 12, LibreOffice 24.2.7 resolves only the FIRST circular group in a chain
of them: FY2026 comes out exact against `reference.py` (balance check
-9.6e-07), and FY2027-30 are each solved with the prior year's closing debt
frozen at its seed value, so borrowings read 25.0 for the rest of the
forecast. Raising ``iterateCount`` to 10,000, tightening ``iterateDelta`` to
1e-12 and recalculating the file up to seven times all leave the answer
bit-identical, so it is a stable wrong result rather than an unfinished one.
A branched circular group fails the same way, freezing the second branch.
`tests/test_libreoffice_iteration_limits.py` pins both behaviours in twelve
cells apiece. A five-year average-balance debt schedule is inherently a chain
of five circular groups, so NO arrangement of these rows fixes it — the
`INTEREST_BASIS` decision needs an owner ruling, and Task 12's report raises
it as a question rather than changing a constant an earlier task fixed. The
rows below are the faithful expression of the model as specified.

    debt_interest            = AVERAGE(debt_opening, debt_closing) * rate
    cash_before_debt_service = cash_opening + cash_generated - debt_interest
    debt_repayment           = IF(cbds >= min_cash, MIN(debt_opening, cbds - min_cash), 0)
    revolver_draw            = IF(cbds >= min_cash, 0, min_cash - cbds)
    debt_closing             = debt_opening - debt_repayment + revolver_draw

`debt_interest` reads `debt_closing`, four rows below, which reads back up to
`debt_interest`. That is the loop, and it is deliberate:
``build.build_workbook`` sets ``wb.calculation.iterate`` with the count and
delta Task 2's spike verified LibreOffice honours. Without those three
settings this block evaluates to zeros or an error, which is why
`INTEREST_BASIS = "average"` was only licensed once the spike had passed.

`reference.py` has a second, outer loop on top of that one: `cash_generated`
is net of tax and dividends, tax depends on profit before tax, which depends
on this block's interest. In the workbook that is not a separate mechanism —
`cash_generated` reads ``IS!tax`` and this sheet's `dividends` reads
``IS!net_income``, so the outer loop is part of the same circular group and
the same iteration settles both.
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

    # --- Debt and cash (circular — see the module docstring) --------------
    writer.blank()
    writer.title("Debt and cash (circular: needs iterative calculation)")
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
    row(
        "debt_interest",
        "Interest on borrowings (average of opening and closing debt)",
        lambda c: f"=AVERAGE({me('debt_opening', c)},{me('debt_closing', c)})"
                  f"*{driver('interest_rate_debt')}",
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
