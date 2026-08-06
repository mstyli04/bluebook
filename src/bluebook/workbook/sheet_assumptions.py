"""The Assumptions sheet: the scenario switch, the drivers, the derived rates.

Every forecast number in the workbook is ultimately a function of this sheet
and of Historicals. It has six blocks:

1. **The scenario switch**, cell ``C3`` — a validated dropdown over
   Bear / Base / Bull.
2. **The scenario paths**, blue inputs: for each of the five drivers that
   differ by scenario, the Bear, Base and Bull path is written out in full,
   plus the three exit multiples. Nothing is hidden inside a formula.
3. **The live drivers**, one row per driver, each
   ``=CHOOSE(MATCH($C$3,{"Bear";"Base";"Bull"},0), <bear>, <base>, <bull>)``.
   These are the rows the statements and schedules read, so toggling ``C3``
   re-drives the entire model.
4. **The scenario-invariant drivers** — day counts, depreciation rates, the
   tax rate, the payout ratio, the cash floor, the cost-of-capital build.
   ``assumptions._scenario`` shifts only revenue growth, gross margin, the
   opex ratio, capex, ROU additions and the exit multiple off Base, so
   everything else is one value, written once, in column C.
5. **Rates derived from the filings** — the amortisation rate, the
   PP&E/intangible capex split, the lease discount rate and implied lease
   term, the blended cost of debt. In `assumptions.py` and `lease_rate.py`
   these are computed from ``GREGGS_HISTORICALS`` rather than hardcoded,
   precisely so they cannot go stale against the data; they are written here
   as **formulas off the Historicals sheet** for the same reason, so the
   workbook shows the derivation instead of asserting the answer.
6. **The LBO sponsor conventions** — entry leverage and the IRR hurdle. Added
   in Task 13 because the LBO sheet may hold no constants of its own, and an
   input resting on convention rather than on a filing still belongs on the
   input sheet.

--------------------------------------------------------------------------
Where the switch sits, and the row-3 convention
--------------------------------------------------------------------------
The layout convention is row 1 title, row 2 year header, first data row 3;
the plan puts the switch at ``C3``. Those are not in conflict — they are the
same statement. Row 3 IS the switch's row: it is the sheet's first data row,
written through `SheetWriter.input_row` like any other, with its label in
``B3``. Column C is `HIST_COLS[0]`, the first of the three columns a
`historical`-mode writer writes into, so the switch (and every other
single-value input on this sheet) is written by flipping the writer into that
mode for one row — see `_scalar_column`. That keeps the cursor and the row
registration in `SheetWriter`'s hands: this module never computes a row
number, so the switch's address is a consequence of it being written first,
not a hardcoded position.

Column C is also the right place for a scalar on presentation grounds. A
single tax rate parked in column F would sit under the "FY2026" header and
read as a FY2026-only value.
"""

from __future__ import annotations

from typing import Callable, Sequence

from openpyxl.worksheet.datavalidation import DataValidation

from bluebook.assumptions import RCF_COST_OF_DEBT, SCENARIOS
from bluebook.lbo import SPONSOR_ENTRY_LEVERAGE, SPONSOR_IRR_HURDLE
from bluebook.lease_rate import GREGGS_FY2025_LEASE_INTEREST
from bluebook.schedules.leases import (
    GREGGS_LEASE_MATURITY_LESS_THAN_1YR,
    GREGGS_LEASE_MATURITY_TOTAL_UNDISCOUNTED,
    LEASE_ADDITIONS_PRINCIPAL_RATE,
)
from bluebook.schedules.working_capital import DAYS_IN_YEAR
from bluebook.workbook.formulas import aref, choose_scenario
from bluebook.workbook.layout import FCST_COLS, HIST_COLS, Layout
from bluebook.workbook.sheet import SheetWriter
from bluebook.workbook.styles import (
    MONEY_FORMAT,
    MULTIPLE_FORMAT,
    PERCENT_FORMAT,
    RATIO_FORMAT,
    TEXT_FORMAT,
)

SHEET = "Assumptions"
HISTORICALS = "Historicals"

# The column single-value inputs are written into, and therefore the column
# the scenario switch lands in. Not a free choice: it is the first column a
# `historical`-mode SheetWriter writes to.
SCALAR_COL = HIST_COLS[0]

# The scenario labels, in the order the CHOOSE arms are written. One ordered
# constant drives the dropdown, the MATCH array and the arm order, so the
# three cannot disagree — a mismatch would silently select the wrong case.
SCENARIO_LABELS = ("Bear", "Base", "Bull")

# The last historical year is the final column of the Historicals sheet.
LAST_ACTUAL_COL = HIST_COLS[-1]
# FY2024, the opening year of the last actual — the denominator of both the
# amortisation rate and the lease discount rate.
PRIOR_ACTUAL_COL = HIST_COLS[-2]

# Drivers that differ by scenario and have one value per forecast year.
# `assumptions._scenario` shifts exactly these five plus the exit multiple.
PER_YEAR_SCENARIO_DRIVERS = (
    ("revenue_growth", "Revenue growth", PERCENT_FORMAT),
    ("gross_margin", "Gross margin", PERCENT_FORMAT),
    ("opex_pct_revenue", "Operating costs (% of revenue)", PERCENT_FORMAT),
    ("capex_pct_revenue", "Total capex (% of revenue)", PERCENT_FORMAT),
    ("rou_additions_pct_revenue", "ROU additions (% of revenue)", PERCENT_FORMAT),
)

# Single-value drivers that are the same in all three scenarios, read
# straight off `SCENARIOS["Base"]`.
INVARIANT_DRIVERS = (
    ("inventory_days", "Inventory days (on cost of sales)", RATIO_FORMAT),
    ("receivable_days", "Receivable days (on revenue)", RATIO_FORMAT),
    ("payable_days", "Payable days (on cost of sales)", RATIO_FORMAT),
    ("ppe_depreciation_rate", "PP&E depreciation rate (of opening PP&E)", PERCENT_FORMAT),
    ("rou_depreciation_rate", "ROU depreciation rate (of opening ROU)", PERCENT_FORMAT),
    ("tax_rate", "Corporation tax rate", PERCENT_FORMAT),
    ("dividend_payout_ratio", "Dividend payout ratio (of net income)", PERCENT_FORMAT),
    ("minimum_cash", "Minimum cash balance (£m)", MONEY_FORMAT),
)

COST_OF_CAPITAL_DRIVERS = (
    ("risk_free_rate", "Risk-free rate (UK 10-year gilt, estimate)", PERCENT_FORMAT),
    ("equity_risk_premium", "Equity risk premium (UK, estimate)", PERCENT_FORMAT),
    ("beta", "Levered equity beta (estimate)", RATIO_FORMAT),
    ("target_debt_weight", "Debt weight in WACC (incl. leases)", PERCENT_FORMAT),
    ("perpetuity_growth", "Perpetuity growth rate", PERCENT_FORMAT),
)


def _scalar_column(writer: SheetWriter, write: Callable[[], int]) -> int:
    """Run `write` with the writer temporarily in single-value column mode.

    A `SheetWriter` writes a row's values into `FCST_COLS` or `HIST_COLS`
    depending on its mode, and this sheet needs both: driver paths across
    F:J, single values in C. Flipping the mode for one row keeps the cursor
    and the Layout registration inside `SheetWriter` — the alternative,
    poking `writer.row`, would move row bookkeeping into this module, which
    is the thing `layout.py` exists to prevent.
    """
    writer.historical = True
    try:
        return write()
    finally:
        writer.historical = False


def _scalar_input(writer: SheetWriter, key: str, label: str, value, fmt: str) -> int:
    return _scalar_column(writer, lambda: writer.input_row(key, label, [value], fmt))


def _scalar_formula(writer: SheetWriter, key: str, label: str, formula: str, fmt: str) -> int:
    return _scalar_column(writer, lambda: writer.formula_row(key, label, [formula], fmt))


def _switch_ref(layout: Layout) -> str:
    """Absolute reference to the scenario switch cell, e.g. ``'Assumptions'!$C$3``."""
    return aref(layout, SHEET, "scenario", SCALAR_COL)


def _scenario_key(field: str, label: str) -> str:
    return f"{field}_{label.lower()}"


def _choose_row(
    layout: Layout,
    field: str,
    cols: Sequence[str],
) -> list[str]:
    """A CHOOSE formula per column, selecting that column's three scenario rows."""
    switch = _switch_ref(layout)
    return [
        choose_scenario(
            switch,
            SCENARIO_LABELS,
            [
                layout.ref(SHEET, _scenario_key(field, label), col)
                for label in SCENARIO_LABELS
            ],
        )
        for col in cols
    ]


def _hist(layout: Layout, key: str, col: str) -> str:
    return layout.ref(HISTORICALS, key, col)


def write_assumptions(
    writer: SheetWriter,
    ref_layout: Layout,
    scenario_name: str,
    year_labels: Sequence[str],
) -> int:
    """Write the Assumptions sheet and return the row its year header landed on.

    `writer` must be in forecast mode. The returned row is what the statement
    sheets link their own year headers to, so the forecast years are written
    down once, here, and nowhere else — see `formulas.year_header_links`.
    """
    if scenario_name not in SCENARIO_LABELS:
        raise ValueError(
            f"scenario_name must be one of {list(SCENARIO_LABELS)}, got {scenario_name!r}"
        )

    writer.title("Assumptions — drivers and the scenario switch")
    # `writer.row` is the cursor the header is about to be written at; read it
    # before the call rather than assuming the convention's row 2.
    year_header_row = writer.row
    writer.year_header(year_labels)

    # --- 1. The switch. First data row, hence row 3, hence cell C3. --------
    switch_row = _scalar_input(
        writer, "scenario", "SCENARIO (Bear / Base / Bull)", scenario_name, TEXT_FORMAT
    )
    validation = DataValidation(
        type="list",
        formula1='"' + ",".join(SCENARIO_LABELS) + '"',
        allow_blank=False,
        showDropDown=False,
    )
    validation.error = "Choose Bear, Base or Bull."
    validation.prompt = "Toggling this cell re-drives every forecast in the workbook."
    writer.ws.add_data_validation(validation)
    validation.add(writer.ws[f"{SCALAR_COL}{switch_row}"])

    # --- 2. The three scenario paths, written out in full ------------------
    writer.blank()
    writer.title("Scenario paths (inputs)")
    for field, label, fmt in PER_YEAR_SCENARIO_DRIVERS:
        for scenario_label in SCENARIO_LABELS:
            writer.input_row(
                _scenario_key(field, scenario_label),
                f"{label} — {scenario_label}",
                list(getattr(SCENARIOS[scenario_label], field)),
                fmt,
            )
    for scenario_label in SCENARIO_LABELS:
        _scalar_input(
            writer,
            _scenario_key("exit_ev_ebitda", scenario_label),
            f"Exit EV/EBITDA multiple — {scenario_label}",
            SCENARIOS[scenario_label].exit_ev_ebitda,
            MULTIPLE_FORMAT,
        )

    # --- 3. The live drivers the rest of the workbook reads ----------------
    writer.blank()
    writer.title("Live drivers (selected by the scenario switch in C3)")
    for field, label, fmt in PER_YEAR_SCENARIO_DRIVERS:
        writer.formula_row(field, label, _choose_row(ref_layout, field, FCST_COLS), fmt)
    _scalar_formula(
        writer,
        "exit_ev_ebitda",
        "Exit EV/EBITDA multiple",
        _choose_row(ref_layout, "exit_ev_ebitda", [SCALAR_COL])[0],
        MULTIPLE_FORMAT,
    )

    # --- 4. Drivers that do not vary by scenario --------------------------
    writer.blank()
    writer.title("Operating and financing drivers (same in every scenario)")
    base = SCENARIOS["Base"]
    for field, label, fmt in INVARIANT_DRIVERS:
        _scalar_input(writer, field, label, getattr(base, field), fmt)
    _scalar_input(
        writer, "days_in_year", "Days in year (working capital basis)", DAYS_IN_YEAR, RATIO_FORMAT
    )
    _scalar_input(
        writer,
        "rcf_cost_of_debt",
        "RCF interest rate (risk-free + ~150bp, estimate)",
        RCF_COST_OF_DEBT,
        PERCENT_FORMAT,
    )
    # The revolver genuinely borrows at the RCF rate; the blended
    # cost_of_debt below is a cost-of-capital construct no instrument pays.
    _scalar_formula(
        writer,
        "interest_rate_debt",
        "Revolver interest rate (charged in the debt schedule)",
        f"={aref(ref_layout, SHEET, 'rcf_cost_of_debt', SCALAR_COL)}",
        PERCENT_FORMAT,
    )
    for field, label, fmt in COST_OF_CAPITAL_DRIVERS:
        _scalar_input(writer, field, label, getattr(base, field), fmt)

    # --- 5. Rates derived from the filings, shown as their derivations -----
    writer.blank()
    writer.title("Rates derived from the filings (formulas off Historicals)")

    # SCHEMA GAP, carried over from lease_rate.py: `finance_costs` bundles
    # lease interest with RCF interest and a 0.7 exceptional, so FY2025 lease
    # interest of 16.7 cannot be divided out of the Historicals sheet. It is
    # the one transcribed figure on this sheet that Historicals does not
    # carry, and it needs a `lease_interest` field on `HistoricalYear` to be
    # derived rather than hand-checked against the filing.
    _scalar_input(
        writer,
        "lease_interest_fy2025",
        "FY2025 interest on lease liabilities (FY2025 AR p.128)",
        GREGGS_FY2025_LEASE_INTEREST,
        MONEY_FORMAT,
    )
    _scalar_formula(
        writer,
        "lease_discount_rate",
        "IFRS 16 lease discount rate (= FY2025 lease interest / FY2024 liability)",
        f"={aref(ref_layout, SHEET, 'lease_interest_fy2025', SCALAR_COL)}"
        f"/{_hist(ref_layout, 'lease_liabilities', PRIOR_ACTUAL_COL)}",
        PERCENT_FORMAT,
    )
    _scalar_input(
        writer,
        "lease_maturity_total",
        "Undiscounted lease cash flows, total (FY2025 AR p.154)",
        GREGGS_LEASE_MATURITY_TOTAL_UNDISCOUNTED,
        MONEY_FORMAT,
    )
    _scalar_input(
        writer,
        "lease_maturity_under_1yr",
        "Undiscounted lease cash flows, < 1 year (FY2025 AR p.154)",
        GREGGS_LEASE_MATURITY_LESS_THAN_1YR,
        MONEY_FORMAT,
    )
    _scalar_formula(
        writer,
        "implied_lease_term_years",
        "Implied average lease term, years (= total / < 1 year)",
        f"={aref(ref_layout, SHEET, 'lease_maturity_total', SCALAR_COL)}"
        f"/{aref(ref_layout, SHEET, 'lease_maturity_under_1yr', SCALAR_COL)}",
        RATIO_FORMAT,
    )
    # Empirical fit, not a disclosed figure: the partial-year principal
    # amortisation on leases signed during the year. Solved jointly with the
    # implied term against FY2024 and FY2025 actual principal paid — see
    # schedules/leases.py.
    _scalar_input(
        writer,
        "lease_additions_principal_rate",
        "Principal repaid on in-year lease additions (empirical fit)",
        LEASE_ADDITIONS_PRINCIPAL_RATE,
        PERCENT_FORMAT,
    )

    # Implied intangible additions = closing - opening + amortisation,
    # aggregated over the two years that have a prior-year balance to roll
    # off (FY2024 and FY2025), over the same two years' total capex.
    intangible_additions = (
        f"({_hist(ref_layout, 'intangibles', PRIOR_ACTUAL_COL)}"
        f"-{_hist(ref_layout, 'intangibles', HIST_COLS[0])}"
        f"+{_hist(ref_layout, 'amortisation', PRIOR_ACTUAL_COL)})"
        f"+({_hist(ref_layout, 'intangibles', LAST_ACTUAL_COL)}"
        f"-{_hist(ref_layout, 'intangibles', PRIOR_ACTUAL_COL)}"
        f"+{_hist(ref_layout, 'amortisation', LAST_ACTUAL_COL)})"
    )
    two_year_capex = (
        f"({_hist(ref_layout, 'capex', PRIOR_ACTUAL_COL)}"
        f"+{_hist(ref_layout, 'capex', LAST_ACTUAL_COL)})"
    )
    _scalar_formula(
        writer,
        "intangible_capex_share",
        "Intangible share of total capex (FY2024-25 implied additions / capex)",
        f"=({intangible_additions})/{two_year_capex}",
        PERCENT_FORMAT,
    )
    _scalar_formula(
        writer,
        "ppe_capex_share",
        "PP&E share of total capex (= 1 - intangible share)",
        f"=1-{aref(ref_layout, SHEET, 'intangible_capex_share', SCALAR_COL)}",
        PERCENT_FORMAT,
    )
    _scalar_formula(
        writer,
        "amortisation_rate",
        "Amortisation rate (= FY2025 amortisation / FY2024 intangibles)",
        f"={_hist(ref_layout, 'amortisation', LAST_ACTUAL_COL)}"
        f"/{_hist(ref_layout, 'intangibles', PRIOR_ACTUAL_COL)}",
        PERCENT_FORMAT,
    )
    # Gross-debt-weighted blend of the RCF rate and the lease rate on the
    # FY2025 actual balances. Gross, not net: netting cash against the RCF
    # would put a negative weight on the RCF leg. Used only by the WACC.
    borrowings = _hist(ref_layout, "borrowings", LAST_ACTUAL_COL)
    lease_liabilities = _hist(ref_layout, "lease_liabilities", LAST_ACTUAL_COL)
    _scalar_formula(
        writer,
        "cost_of_debt",
        "Cost of debt for the WACC (RCF/lease blend, gross-weighted)",
        f"=({borrowings}*{aref(ref_layout, SHEET, 'rcf_cost_of_debt', SCALAR_COL)}"
        f"+{lease_liabilities}*{aref(ref_layout, SHEET, 'lease_discount_rate', SCALAR_COL)})"
        f"/({borrowings}+{lease_liabilities})",
        PERCENT_FORMAT,
    )

    # --- 6. LBO sponsor assumptions ---------------------------------------
    # Two judgement conventions, and neither is sourced from anything — they
    # are here rather than on the LBO sheet because that sheet may hold no
    # constants (`HARDCODE_ALLOWED`), and an input with no formula behind it
    # belongs on the input sheet whatever it drives. `lbo.py` states the case
    # for each; the short version is that 4.0x is where a UK leveraged
    # retail/hospitality structure is typically underwritten and 20% is the
    # conventional equity hurdle. The leverage is deliberately LEASE-INCLUSIVE,
    # which is the only definition consistent with the rest of this model:
    # read lease-exclusive it would imply 5.28x total.
    writer.blank()
    writer.title("LBO sponsor assumptions (conventions, not sourced figures)")
    _scalar_input(
        writer,
        "sponsor_entry_leverage",
        "Sponsor entry leverage (x EBITDA, total net debt INCLUDING leases)",
        SPONSOR_ENTRY_LEVERAGE,
        MULTIPLE_FORMAT,
    )
    _scalar_input(
        writer,
        "sponsor_irr_hurdle",
        "Sponsor IRR hurdle (conventional underwriting hurdle)",
        SPONSOR_IRR_HURDLE,
        PERCENT_FORMAT,
    )

    return year_header_row
