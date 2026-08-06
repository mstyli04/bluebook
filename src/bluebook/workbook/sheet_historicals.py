"""The Historicals sheet: three reported years, transcribed, with provenance.

This is the only sheet in the workbook that carries reported actuals, and
together with Assumptions it is one of the two sheets every other sheet's
opening balances and driver anchors are read from. Values come straight from
``inputs/greggs.py``, so a figure cannot differ between the Python model and
the workbook; each row's `Sourced.source` string is written beside it in
column L, so a reader can take any number on this sheet back to a page of a
filing without leaving the workbook.

Columns C/D/E hold FY2023/FY2024/FY2025 (the writer runs in `historical`
mode). The subtotal rows are formulas, not transcriptions, because they are
derived: writing a transcribed "gross profit" beside a transcribed revenue
and cost of sales would give the sheet two answers for the same quantity.
"""

from __future__ import annotations

from bluebook.inputs.greggs import GREGGS_SHARE_COUNT
from bluebook.inputs.schema import HistoricalYear
from bluebook.workbook.layout import HIST_COLS
from bluebook.workbook.sheet import SheetWriter
from bluebook.workbook.styles import MONEY_FORMAT, RATIO_FORMAT

SHEET = "Historicals"

# Provenance goes here rather than in a comment: an interviewer can click the
# cell. Far enough right (L) to clear the C:J number grid on every sheet.
SOURCE_COL = "L"

# (attribute on HistoricalYear, row label). Order is the order the rows
# appear on the sheet. Every numeric field of `HistoricalYear` appears exactly
# once, so nothing downstream has to reach past this sheet to the Python
# objects for a reported figure.
INCOME_STATEMENT_FIELDS = (
    ("revenue", "Revenue"),
    ("cost_of_sales", "Cost of sales"),
    ("operating_costs", "Operating costs (excl. D&A and impairment)"),
    ("depreciation_ppe", "Depreciation of PP&E (incl. net impairment)"),
    ("depreciation_rou", "Depreciation of ROU assets (incl. net impairment)"),
    ("amortisation", "Amortisation of intangibles"),
    ("finance_costs", "Finance costs (incl. lease interest)"),
    ("finance_income", "Finance income"),
    ("tax_expense", "Tax expense"),
)

ASSET_FIELDS = (
    ("ppe", "Property, plant and equipment"),
    ("rou_assets", "Right-of-use assets"),
    ("intangibles", "Intangible assets"),
    ("inventories", "Inventories"),
    ("trade_receivables", "Trade and other receivables"),
    ("cash", "Cash and cash equivalents"),
    ("other_assets", "Other assets"),
)

CLAIM_FIELDS = (
    ("trade_payables", "Trade and other payables"),
    ("lease_liabilities", "Lease liabilities"),
    ("borrowings", "Borrowings (RCF drawn)"),
    ("other_liabilities", "Other liabilities"),
    ("equity", "Total equity"),
)

CASH_FLOW_FIELDS = (
    ("capex", "Capital expenditure (total cash, PP&E + intangibles)"),
    ("lease_principal_paid", "Repayment of lease principal"),
    ("rou_additions", "New right-of-use asset additions"),
    ("dividends_paid", "Dividends paid"),
)


def _transcribed(
    writer: SheetWriter,
    historicals: list[HistoricalYear],
    fields: tuple[tuple[str, str], ...],
) -> None:
    """Write one block of reported lines, each with its filing citation."""
    for attr, label in fields:
        sourced = [getattr(year, attr) for year in historicals]
        row = writer.input_row(attr, label, [s.value for s in sourced], MONEY_FORMAT)
        # One source string per row, not per cell: all three years of a line
        # come from the same series of annual reports and the per-year
        # citations differ only in the year, which the column already says.
        writer.ws[f"{SOURCE_COL}{row}"] = " / ".join(s.source for s in sourced)


def _sum_row(writer, layout, key: str, label: str, add: list[str], less: list[str] = ()) -> None:
    """A subtotal across the three historical columns, as a formula per column."""
    formulas = []
    for col in HIST_COLS:
        terms = "+".join(layout.ref(SHEET, k, col) for k in add)
        for k in less:
            terms += f"-{layout.ref(SHEET, k, col)}"
        formulas.append(f"={terms}")
    writer.formula_row(key, label, formulas, MONEY_FORMAT)


def write_historicals(
    writer: SheetWriter,
    ref_layout,
    historicals: list[HistoricalYear],
) -> None:
    """Write the Historicals sheet. `writer` must be in `historical` mode."""
    writer.title("Historicals — Greggs plc, £m as reported (post-IFRS 16)")
    writer.year_header([year.label for year in historicals])

    _transcribed(writer, historicals, INCOME_STATEMENT_FIELDS)
    _sum_row(writer, ref_layout, "gross_profit", "Gross profit", ["revenue"], ["cost_of_sales"])
    _sum_row(writer, ref_layout, "ebitda", "EBITDA", ["gross_profit"], ["operating_costs"])
    _sum_row(
        writer, ref_layout, "da_total", "Total D&A (incl. impairment)",
        ["depreciation_ppe", "depreciation_rou", "amortisation"],
    )
    _sum_row(writer, ref_layout, "ebit", "EBIT (operating profit)", ["ebitda"], ["da_total"])
    _sum_row(
        writer, ref_layout, "profit_before_tax", "Profit before tax",
        ["ebit", "finance_income"], ["finance_costs"],
    )
    _sum_row(
        writer, ref_layout, "net_income", "Net income",
        ["profit_before_tax"], ["tax_expense"],
    )

    writer.blank()
    writer.title("Balance sheet")
    _transcribed(writer, historicals, ASSET_FIELDS)
    _sum_row(
        writer, ref_layout, "total_assets", "Total assets",
        [attr for attr, _ in ASSET_FIELDS],
    )
    writer.blank()
    _transcribed(writer, historicals, CLAIM_FIELDS)
    _sum_row(
        writer, ref_layout, "total_liabilities_and_equity", "Total liabilities and equity",
        [attr for attr, _ in CLAIM_FIELDS],
    )
    _sum_row(
        writer, ref_layout, "net_working_capital", "Net working capital",
        ["inventories", "trade_receivables"], ["trade_payables"],
    )

    writer.blank()
    writer.title("Cash flow")
    _transcribed(writer, historicals, CASH_FLOW_FIELDS)

    writer.blank()
    writer.title("Share count")
    # Not a `HistoricalYear` field — there is one share count in the schema, a
    # module-level constant, so it is written once in the last reported year's
    # column rather than across all three. This is the count every per-share
    # figure in the workbook is struck on: the DCF's implied price and the
    # comps-implied price both divide by it. `comps.GREGGS_SHARES_OUTSTANDING`
    # (101.96m) is a different number and is used only for the market
    # capitalisation on Comps, where the provider's price needs the provider's
    # count; the 0.51% gap between them is disclosed on that sheet.
    share_count_row = writer.input_row(
        "share_count",
        "Weighted average shares in issue, diluted (m)",
        [GREGGS_SHARE_COUNT.value],
        RATIO_FORMAT,
        cols=(HIST_COLS[-1],),
    )
    writer.ws[f"{SOURCE_COL}{share_count_row}"] = GREGGS_SHARE_COUNT.source
