"""The three statements: income statement, balance sheet, cash flow.

All three carry the five forecast years in F:J and nothing else. The three
reported years live on the Historicals sheet in C:D:E, which is what keeps
the workbook's column grid consistent — a `SheetWriter` writes into one
column block or the other, not both, and reaching across to write C:E here
would mean bypassing the writer (and with it the hardcode guard) for every
row.

Every cell on these sheets is a formula. Where a line is computed elsewhere
the cell is a green link — the balance sheet in particular is almost entirely
links, because a balance sheet line that recomputed its own roll-forward
would be a second definition of a number the Schedules sheet already owns.

--------------------------------------------------------------------------
Why the balance sheet balances, with no plug
--------------------------------------------------------------------------
Neither total is derived from the other: `total_assets` foots its own seven
asset lines and `total_liabilities_and_equity` foots its own five claim
lines. They agree because every movement reaches both statements — the proof
is in `reference.py`'s module docstring. `balance_check` is written as the
difference of the two totals so that the claim is visible rather than
asserted; Task 14's Checks sheet surfaces it.
"""

from __future__ import annotations

from typing import Callable, Sequence

from bluebook.workbook.formulas import aref, roll_forward, total
from bluebook.workbook.layout import FCST_COLS, HIST_COLS, Layout
from bluebook.workbook.sheet import SheetWriter
from bluebook.workbook.styles import MONEY_FORMAT

IS = "IS"
BS = "BS"
CF = "CF"
ASSUMPTIONS = "Assumptions"
HISTORICALS = "Historicals"
SCHEDULES = "Schedules"

LAST_ACTUAL_COL = HIST_COLS[-1]
DRIVER_COL = HIST_COLS[0]

# The seven asset lines and five claim lines the balance sheet totals foot.
# Named here so the total and the rows above it cannot drift apart: adding a
# line to the sheet without adding it here would leave the total wrong, and
# the balance check is what would catch it.
ASSET_ROWS = (
    "ppe",
    "rou_assets",
    "intangibles",
    "inventories",
    "trade_receivables",
    "cash",
    "other_assets",
)
CLAIM_ROWS = (
    "trade_payables",
    "lease_liabilities",
    "borrowings",
    "other_liabilities",
    "equity",
)


def _row_writer(writer: SheetWriter):
    """Return a `row(key, label, build)` helper for one statement sheet.

    `build(col)` produces that column's formula, so a row is described once
    and the five columns follow from it — the shape that makes a row
    inspectable in the formula bar as "the same formula, one column across".
    """

    def row(
        key: str,
        label: str,
        build: Callable[[str], str],
        *,
        is_link: bool = False,
    ) -> None:
        writer.formula_row(
            key, label, [build(col) for col in FCST_COLS], MONEY_FORMAT, is_link=is_link
        )

    return row


def _linker(layout: Layout, source_sheet: str):
    """Return a `build` function that links a whole row to another sheet."""

    def build_for(source_key: str) -> Callable[[str], str]:
        return lambda col: f"={layout.ref(source_sheet, source_key, col)}"

    return build_for


def write_income_statement(
    writer: SheetWriter, ref_layout: Layout, year_labels: Sequence[str]
) -> None:
    """Write the IS sheet. `writer` must be in forecast mode."""
    layout = ref_layout
    row = _row_writer(writer)
    from_schedules = _linker(layout, SCHEDULES)

    def me(key: str, col: str) -> str:
        return layout.ref(IS, key, col)

    def path(key: str, col: str) -> str:
        return layout.ref(ASSUMPTIONS, key, col)

    def driver(key: str) -> str:
        return aref(layout, ASSUMPTIONS, key, DRIVER_COL)

    writer.title("Income statement — forecast, £m")
    writer.year_header(year_labels)

    # Year one grows off the FY2025 actual; later years off the prior column.
    writer.formula_row(
        "revenue",
        "Revenue",
        [
            f"={layout.ref(HISTORICALS, 'revenue', LAST_ACTUAL_COL)}"
            f"*(1+{path('revenue_growth', FCST_COLS[0])})"
        ]
        + [
            f"={me('revenue', FCST_COLS[index - 1])}*(1+{path('revenue_growth', col)})"
            for index, col in enumerate(FCST_COLS)
            if index > 0
        ],
        MONEY_FORMAT,
    )
    # Gross margin is the driver, so gross profit is computed and cost of
    # sales is the balance. Presented in that order rather than the reported
    # one so that no row on this sheet reads a row below it.
    row("gross_profit", "Gross profit", lambda c: f"={me('revenue', c)}*{path('gross_margin', c)}")
    row(
        "cost_of_sales",
        "Cost of sales (memo: revenue less gross profit)",
        lambda c: f"={me('revenue', c)}-{me('gross_profit', c)}",
    )
    row(
        "operating_costs",
        "Operating costs (excl. D&A)",
        lambda c: f"={me('revenue', c)}*{path('opex_pct_revenue', c)}",
    )
    row(
        "ebitda",
        "EBITDA",
        lambda c: f"={me('gross_profit', c)}-{me('operating_costs', c)}",
    )
    row(
        "depreciation_ppe",
        "Depreciation of PP&E",
        from_schedules("ppe_depreciation"),
        is_link=True,
    )
    row(
        "depreciation_rou",
        "Depreciation of ROU assets",
        from_schedules("rou_depreciation"),
        is_link=True,
    )
    row("amortisation", "Amortisation", from_schedules("amortisation"), is_link=True)
    row(
        "da_total",
        "Total depreciation and amortisation",
        lambda c: f"={me('depreciation_ppe', c)}+{me('depreciation_rou', c)}"
                  f"+{me('amortisation', c)}",
    )
    row("ebit", "EBIT", lambda c: f"={me('ebitda', c)}-{me('da_total', c)}")
    row("lease_interest", "Lease interest", from_schedules("lease_interest"), is_link=True)
    row("debt_interest", "Interest on borrowings", from_schedules("debt_interest"), is_link=True)
    row(
        "profit_before_tax",
        "Profit before tax",
        lambda c: f"={me('ebit', c)}-{me('lease_interest', c)}-{me('debt_interest', c)}",
    )
    # A loss attracts no charge rather than a refund: this model has no loss
    # carryforward, and a negative tax line would show cash arriving from HMRC.
    row(
        "tax",
        "Tax charge (nil in a loss year)",
        lambda c: f"=MAX({me('profit_before_tax', c)},0)*{driver('tax_rate')}",
    )
    row(
        "net_income",
        "Net income",
        lambda c: f"={me('profit_before_tax', c)}-{me('tax', c)}",
    )


def write_balance_sheet(
    writer: SheetWriter, ref_layout: Layout, year_labels: Sequence[str]
) -> None:
    """Write the BS sheet. `writer` must be in forecast mode."""
    layout = ref_layout
    row = _row_writer(writer)
    from_schedules = _linker(layout, SCHEDULES)
    from_cash_flow = _linker(layout, CF)

    def me(key: str, col: str) -> str:
        return layout.ref(BS, key, col)

    def held_flat(key: str) -> Callable[[str], str]:
        """Lines with no driver are held at the last reported balance."""
        return lambda col: f"={layout.ref(HISTORICALS, key, LAST_ACTUAL_COL)}"

    writer.title("Balance sheet — forecast, £m")
    writer.year_header(year_labels)

    row("ppe", "Property, plant and equipment", from_schedules("ppe_closing"), is_link=True)
    row("rou_assets", "Right-of-use assets", from_schedules("rou_closing"), is_link=True)
    row("intangibles", "Intangible assets", from_schedules("intangibles_closing"), is_link=True)
    row("inventories", "Inventories", from_schedules("inventories"), is_link=True)
    row(
        "trade_receivables",
        "Trade and other receivables",
        from_schedules("receivables"),
        is_link=True,
    )
    # From the cash flow statement's own closing balance, not the debt
    # schedule's parallel track. The two are built independently and agree;
    # Task 14's Checks sheet is where that agreement gets asserted.
    row("cash", "Cash and cash equivalents", from_cash_flow("closing_cash"), is_link=True)
    row("other_assets", "Other assets (held flat)", held_flat("other_assets"), is_link=True)
    writer.formula_row(
        "total_assets",
        "Total assets",
        [total([me(key, col) for key in ASSET_ROWS]) for col in FCST_COLS],
        MONEY_FORMAT,
    )

    writer.blank()
    writer.title("Liabilities and equity")
    row("trade_payables", "Trade and other payables", from_schedules("payables"), is_link=True)
    row(
        "lease_liabilities",
        "Lease liabilities",
        from_schedules("lease_liability_closing"),
        is_link=True,
    )
    row("borrowings", "Borrowings", from_schedules("debt_closing"), is_link=True)
    row(
        "other_liabilities",
        "Other liabilities (held flat)",
        held_flat("other_liabilities"),
        is_link=True,
    )
    row("equity", "Total equity", from_schedules("equity_closing"), is_link=True)
    writer.formula_row(
        "total_liabilities_and_equity",
        "Total liabilities and equity",
        [total([me(key, col) for key in CLAIM_ROWS]) for col in FCST_COLS],
        MONEY_FORMAT,
    )
    row(
        "balance_check",
        "Balance check (total assets less total claims — must be nil)",
        lambda c: f"={me('total_assets', c)}-{me('total_liabilities_and_equity', c)}",
    )


def write_cash_flow(
    writer: SheetWriter, ref_layout: Layout, year_labels: Sequence[str]
) -> None:
    """Write the CF sheet. `writer` must be in forecast mode."""
    layout = ref_layout
    row = _row_writer(writer)
    from_schedules = _linker(layout, SCHEDULES)
    from_income = _linker(layout, IS)

    def me(key: str, col: str) -> str:
        return layout.ref(CF, key, col)

    writer.title("Cash flow statement — forecast, £m")
    writer.year_header(year_labels)

    # Sign convention, as in inputs/greggs.py: every named line is a positive
    # magnitude of the flow its name describes. Only the subtotals are signed.
    row("ebitda", "EBITDA", from_income("ebitda"), is_link=True)
    row(
        "change_in_working_capital",
        "Increase in working capital (outflow when positive)",
        from_schedules("change_in_nwc"),
        is_link=True,
    )
    row("tax_paid", "Tax paid", from_income("tax"), is_link=True)
    row(
        "cash_from_operations",
        "Cash from operations",
        lambda c: f"={me('ebitda', c)}-{me('change_in_working_capital', c)}"
                  f"-{me('tax_paid', c)}",
    )

    writer.blank()
    writer.title("Investing and financing")
    # The total is what the statement spends; the two components beside it are
    # memo lines, because the split drives two different balance sheet lines.
    # Only `capex` enters the subtotal below — including a component too would
    # double-count it and unbalance the balance sheet.
    row("capex", "Capital expenditure (total)", from_schedules("total_capex"), is_link=True)
    row("capex_ppe", "  of which PP&E (memo)", from_schedules("ppe_capex"), is_link=True)
    row(
        "capex_intangible",
        "  of which intangible (memo)",
        from_schedules("intangible_capex"),
        is_link=True,
    )
    row(
        "lease_interest_paid",
        "Lease interest paid",
        from_schedules("lease_interest"),
        is_link=True,
    )
    row(
        "lease_principal_paid",
        "Lease principal repaid",
        from_schedules("lease_principal_paid"),
        is_link=True,
    )
    row(
        "debt_interest_paid",
        "Interest paid on borrowings",
        from_schedules("debt_interest"),
        is_link=True,
    )
    row("debt_repayment", "Repayment of borrowings", from_schedules("debt_repayment"), is_link=True)
    row("revolver_draw", "Revolver draw (inflow)", from_schedules("revolver_draw"), is_link=True)
    row("dividends_paid", "Dividends paid", from_schedules("dividends"), is_link=True)
    row(
        "net_change_in_cash",
        "Net change in cash",
        lambda c: f"={me('cash_from_operations', c)}-{me('capex', c)}"
                  f"-{me('lease_interest_paid', c)}-{me('lease_principal_paid', c)}"
                  f"-{me('debt_interest_paid', c)}-{me('debt_repayment', c)}"
                  f"+{me('revolver_draw', c)}-{me('dividends_paid', c)}",
    )
    writer.formula_row(
        "opening_cash",
        "Opening cash",
        roll_forward(
            layout,
            f"={layout.ref(HISTORICALS, 'cash', LAST_ACTUAL_COL)}",
            "closing_cash",
            sheet=CF,
        ),
        MONEY_FORMAT,
    )
    row(
        "closing_cash",
        "Closing cash",
        lambda c: f"={me('opening_cash', c)}+{me('net_change_in_cash', c)}",
    )
