"""The LBO sheet: a sponsor-return exercise on the model's own operating case.

One question: if a financial sponsor bought Greggs at the price the market puts
on it today, financed it as far as this balance sheet allows, ran the model's own
operating case for five years and sold at the multiple it paid, what would the
equity return be?

--------------------------------------------------------------------------
What this sheet is NOT
--------------------------------------------------------------------------
It is **not a test of whether the DCF's cash flows are real**, because it
consumes the same cash flows: the free cash flow row below is a link to the DCF
sheet, which is a link to the same schedules. If that path is wrong, this sheet
is wrong in exactly the same way and by exactly the same amount. It cannot
corroborate the DCF and it cannot falsify it.

What it adds is a RE-EXPRESSION: the same cash flows, levered and inside a
five-year window, which surfaces two things a single share price hides — the
timing of the flows (the front-loaded capex burn) and the amount of value
sitting outside the window (the terminal value). An LBO cannot borrow against a
terminal value, so "93-95% of enterprise value is terminal" reappears here as a
low IRR. Two views of one cash-flow path, not two pieces of evidence.

It is also **not a claim that Greggs is a buyout candidate**. The business holds
net CASH excluding leases, so there is no existing structure to lever against;
and the lease liability is 1.28x EBITDA and contractual, so a lender
underwriting 4.0x lease-adjusted is underwriting 2.72x of new money because the
first 1.28x is already spoken for. A lease-heavy retailer with a running capital
programme is close to the worst case for an LBO, and saying so with numbers is
more useful than not running one.

--------------------------------------------------------------------------
What is sourced and what is convention
--------------------------------------------------------------------------
Sourced: the entry enterprise value is Greggs' own traded EV from the Comps
sheet; entry EBITDA and the opening lease liability come from Historicals; the
whole operating case comes from the schedules. Convention, and both live on
Assumptions because this sheet may hold no constants: entry leverage of 4.0x
(lease-INCLUSIVE) and the 20% IRR hurdle. The new debt is priced at the
revolver's own rate, which a real buyout facility would price wider, so the
return here is if anything FLATTERED.

Two omissions that also flatter it, neither built in: **no control premium** and
**no transaction fees**. `lbo.py` quantifies both (a 30% premium takes the Base
case to 1.66x / 10.65%, and 2% fees on top to 1.60x / 9.84%) and notes that the
premium largely self-cancels only because the exit is struck at the multiple
PAID, which is an artefact of the no-expansion convention rather than any real
insulation from overpaying.

--------------------------------------------------------------------------
The cash sweep, and the one subtlety in it
--------------------------------------------------------------------------
    cash available = unlevered FCF
                   + new ROU additions
                   - lease principal repaid
                   - lease interest x (1 - tax rate)
                   - financial interest x (1 - tax rate)

The ROU add-back is the subtlety and it is not a fudge. The DCF DEDUCTS new ROU
additions as an investing outflow, on the ruling that funding a leased shop is
economically the same act as funding an owned one. Under that ruling a new lease
is also a financing INFLOW of the same amount — the liability that funds the
asset — so it is added back here and the lease is then serviced through the
principal and interest lines like any other debt. Deducting the additions and
the principal without the add-back would charge the same leases twice.

Both interest lines carry a tax shield because unlevered FCF taxes EBIT and so
carries none. Interest is charged on the OPENING balance, so the sweep at the
year end cannot reduce the interest the year itself bore — the same basis, and
for the same acyclicity reason, as the revolver on the Schedules sheet.

Lease liabilities are not re-forecast here: the closing balances are links to the
lease schedule, so the sponsor case inherits exactly the lease book the DCF
values, including the fact that it GROWS. In Base it grows £106.2m over the hold,
which is why total debt including leases ends higher than it started even though
the financial debt sweep turns positive in the last two years.
"""

from __future__ import annotations

from typing import Callable, Sequence

from bluebook.workbook.formulas import aref, cell_range, roll_forward
from bluebook.workbook.layout import FCST_COLS, HIST_COLS, Layout
from bluebook.workbook.sheet import SheetWriter
from bluebook.workbook.styles import (
    MONEY_FORMAT,
    MULTIPLE_FORMAT,
    PERCENT_FORMAT,
    RATIO_FORMAT,
)

SHEET = "LBO"
ASSUMPTIONS = "Assumptions"
COMPS = "Comps"
DCF = "DCF"
HISTORICALS = "Historicals"
IS = "IS"
SCHEDULES = "Schedules"

SCALAR_COL = HIST_COLS[0]
SCALAR = (SCALAR_COL,)
DRIVER_COL = HIST_COLS[0]
LAST_ACTUAL_COL = HIST_COLS[-1]
FINAL_COL = FCST_COLS[-1]


def write_lbo(writer: SheetWriter, ref_layout: Layout, year_labels: Sequence[str]) -> None:
    """Write the LBO sheet. `writer` must be in forecast mode."""
    layout = ref_layout

    def me(key: str, col: str) -> str:
        return layout.ref(SHEET, key, col)

    def scalar(key: str) -> str:
        return aref(layout, SHEET, key, SCALAR_COL)

    def driver(key: str) -> str:
        return aref(layout, ASSUMPTIONS, key, DRIVER_COL)

    def actual(key: str) -> str:
        return layout.ref(HISTORICALS, key, LAST_ACTUAL_COL)

    def row(
        key: str,
        label: str,
        build: Callable[[str], str],
        fmt: str = MONEY_FORMAT,
        *,
        is_link: bool = False,
    ) -> None:
        writer.formula_row(
            key, label, [build(col) for col in FCST_COLS], fmt, is_link=is_link
        )

    def scalar_row(
        key: str, label: str, formula: str, fmt: str = MONEY_FORMAT, *, is_link: bool = False
    ) -> int:
        return writer.formula_row(key, label, [formula], fmt, cols=SCALAR, is_link=is_link)

    def note(key: str, text: str) -> None:
        writer.formula_row(key, text, [])

    writer.title("Leveraged buyout — sponsor returns on the model's own operating case, £m")
    writer.year_header(year_labels)

    # --- Entry -------------------------------------------------------------
    # The entry price is the OBSERVED traded EV, not a valuation: whatever the
    # DCF says, a sponsor pays the market. Everything downstream is therefore a
    # return on a price rather than on an opinion.
    scalar_row(
        "entry_ev",
        "Entry enterprise value (Greggs' traded EV from Comps)",
        f"={aref(layout, COMPS, 'greggs_ev', SCALAR_COL)}",
        is_link=True,
    )
    scalar_row(
        "entry_ebitda",
        "Entry EBITDA (FY2025, the basis the model forecasts)",
        f"={actual('ebitda')}",
        is_link=True,
    )
    scalar_row(
        "entry_multiple",
        "Entry EV/EBITDA",
        f"={scalar('entry_ev')}/{scalar('entry_ebitda')}",
        MULTIPLE_FORMAT,
    )
    scalar_row(
        "entry_leverage",
        "Entry leverage (x EBITDA, total net debt INCLUDING leases)",
        f"={driver('sponsor_entry_leverage')}",
        MULTIPLE_FORMAT,
        is_link=True,
    )
    scalar_row(
        "entry_debt",
        "Entry total net debt including leases",
        f"={scalar('entry_leverage')}*{scalar('entry_ebitda')}",
    )
    scalar_row(
        "entry_leases",
        "  of which the existing lease liability (already spoken for)",
        f"={actual('lease_liabilities')}",
        is_link=True,
    )
    # The lease liability is senior in economic substance to anything a sponsor
    # would raise, so the new money is what is left of the leverage after it.
    scalar_row(
        "entry_financial_debt",
        "  new financial debt raised (the leverage less the leases)",
        f"={scalar('entry_debt')}-{scalar('entry_leases')}",
    )
    scalar_row(
        "entry_equity",
        "Sponsor equity cheque (entry EV less total entry debt)",
        f"={scalar('entry_ev')}-{scalar('entry_debt')}",
    )

    # --- The hold ----------------------------------------------------------
    writer.blank()
    writer.title("The hold — cash sweep against the new financial debt")
    row(
        "unlevered_fcf",
        "Unlevered free cash flow (the DCF's own, unchanged)",
        lambda c: f"={layout.ref(DCF, 'unlevered_fcf', c)}",
        is_link=True,
    )
    # Added back because the DCF deducts it as an investing outflow while the
    # lease liability funds the asset — see the module docstring. Servicing then
    # happens on the two lease lines below.
    row(
        "rou_additions",
        "New ROU additions added back (a new lease funds its own asset)",
        lambda c: f"={layout.ref(SCHEDULES, 'rou_additions', c)}",
        is_link=True,
    )
    row(
        "lease_principal_paid",
        "Lease principal repaid",
        lambda c: f"={layout.ref(SCHEDULES, 'lease_principal_paid', c)}",
        is_link=True,
    )
    row(
        "lease_interest",
        "Lease interest",
        lambda c: f"={layout.ref(SCHEDULES, 'lease_interest', c)}",
        is_link=True,
    )
    writer.formula_row(
        "financial_debt_opening",
        "Opening financial debt",
        roll_forward(
            layout,
            f"={scalar('entry_financial_debt')}",
            "financial_debt_closing",
            sheet=SHEET,
        ),
        MONEY_FORMAT,
    )
    # On the OPENING balance: the sweep happens at the year end, so it cannot
    # reduce the interest the year itself carried. Priced at the revolver's rate,
    # which flatters the return — see the module docstring.
    row(
        "financial_interest",
        "Interest on financial debt (rate on the opening balance)",
        lambda c: f"={me('financial_debt_opening', c)}*{driver('interest_rate_debt')}",
    )
    row(
        "cash_swept",
        "Cash available to repay debt (negative draws more)",
        lambda c: f"={me('unlevered_fcf', c)}+{me('rou_additions', c)}"
                  f"-{me('lease_principal_paid', c)}"
                  f"-{me('lease_interest', c)}*(1-{driver('tax_rate')})"
                  f"-{me('financial_interest', c)}*(1-{driver('tax_rate')})",
    )
    row(
        "financial_debt_closing",
        "Closing financial debt",
        lambda c: f"={me('financial_debt_opening', c)}-{me('cash_swept', c)}",
    )
    row(
        "lease_liability_closing",
        "Closing lease liabilities (the DCF's own lease book — it GROWS)",
        lambda c: f"={layout.ref(SCHEDULES, 'lease_liability_closing', c)}",
        is_link=True,
    )
    row(
        "total_debt_closing",
        "Closing total debt including leases",
        lambda c: f"={me('financial_debt_closing', c)}+{me('lease_liability_closing', c)}",
    )
    row(
        "leverage_closing",
        "Closing total debt / that year's EBITDA",
        lambda c: f"={me('total_debt_closing', c)}/{layout.ref(IS, 'ebitda', c)}",
        MULTIPLE_FORMAT,
    )

    # --- Exit --------------------------------------------------------------
    writer.blank()
    writer.title("Exit — at the multiple paid, with no expansion assumed")
    scalar_row(
        "exit_ebitda",
        "Exit EBITDA (FY2030)",
        f"={layout.ref(IS, 'ebitda', FINAL_COL)}",
        is_link=True,
    )
    # No multiple expansion. The entry multiple is an observed market price; any
    # other exit multiple would be an opinion dressed as an input.
    scalar_row(
        "exit_multiple",
        "Exit EV/EBITDA (the entry multiple, unchanged)",
        f"={scalar('entry_multiple')}",
        MULTIPLE_FORMAT,
    )
    scalar_row(
        "exit_ev",
        "Exit enterprise value",
        f"={scalar('exit_multiple')}*{scalar('exit_ebitda')}",
    )
    scalar_row(
        "exit_debt",
        "Exit total net debt including leases",
        f"={me('total_debt_closing', FINAL_COL)}",
        is_link=True,
    )
    scalar_row(
        "exit_equity",
        "Exit equity value",
        f"={scalar('exit_ev')}-{scalar('exit_debt')}",
    )
    # COLUMNS of the forecast block rather than a written-out 5: the hold period
    # IS the length of the forecast, and writing it twice is how the two come to
    # disagree.
    fcf_row = layout.row_of(SHEET, "unlevered_fcf")
    scalar_row(
        "hold_period_years",
        "Hold period (years, = the length of the forecast)",
        f"=COLUMNS({cell_range(FCST_COLS[0], FCST_COLS[-1], fcf_row)})",
        RATIO_FORMAT,
    )
    scalar_row(
        "money_multiple",
        "Money multiple (exit equity / entry equity)",
        f"={scalar('exit_equity')}/{scalar('entry_equity')}",
        MULTIPLE_FORMAT,
    )
    # One cheque in and one out, so the IRR is the geometric growth rate of the
    # equity and nothing more; there are no interim distributions to solve around.
    scalar_row(
        "irr",
        "IRR (geometric: one cheque in, one out)",
        f"={scalar('money_multiple')}^(1/{scalar('hold_period_years')})-1",
        PERCENT_FORMAT,
    )
    scalar_row(
        "irr_less_hurdle",
        "IRR less the sponsor hurdle (negative = below it)",
        f"={scalar('irr')}-{driver('sponsor_irr_hurdle')}",
        PERCENT_FORMAT,
    )
    # The exit multiple that would clear the hurdle, solved from
    # exit equity = entry equity x (1 + hurdle) ^ years:
    #     exit EV = entry equity x (1 + h) ^ n + exit debt
    #     multiple = exit EV / exit EBITDA
    scalar_row(
        "hurdle_exit_multiple",
        "Exit EV/EBITDA that would clear the hurdle (against the entry multiple above)",
        f"=({scalar('entry_equity')}*(1+{driver('sponsor_irr_hurdle')})"
        f"^{scalar('hold_period_years')}+{scalar('exit_debt')})/{scalar('exit_ebitda')}",
        MULTIPLE_FORMAT,
    )
    # Signed so that positive means the debt GREW, which is what happens here:
    # calling the row "deleveraging" and letting it print +118 would read as the
    # opposite of what it says.
    scalar_row(
        "change_in_total_debt",
        "Change in total debt over the hold (exit less entry, £m; positive = debt GREW)",
        f"={scalar('exit_debt')}-{scalar('entry_debt')}",
    )
    scalar_row(
        "ebitda_growth",
        "EBITDA growth over the hold",
        f"={scalar('exit_ebitda')}/{scalar('entry_ebitda')}-1",
        PERCENT_FORMAT,
    )
    note(
        "note_where_the_return_comes_from",
        "Read the two rows above together. De-gearing contributes nothing to the "
        "return in any scenario and works against it in two: total debt "
        "including leases ends £208.7m HIGHER in Bear and £118.2m higher in "
        "Base, and only £6.8m lower in Bull, against an equity cheque of "
        "£1,001.7m. The money multiple is therefore essentially an "
        "EBITDA-growth story applied to a static multiple. Unlevered free cash "
        "flow is negative in FY2026 in every scenario (and in FY2027 too in "
        "Bear and Base) while the distribution-centre programme runs, so the "
        "sponsor FUNDS capex rather than sweeping cash against the debt; and "
        "the lease book grows in all three, because the model opens more shops "
        "than it closes.",
    )
    note(
        "note_not_a_test_of_the_dcf",
        "This sheet CANNOT corroborate the DCF: the free cash flow row above is "
        "the DCF's own row, so both are wrong together or right together. It is "
        "the same cash flows re-expressed levered and inside a five-year window, "
        "which is why the terminal-value concentration on the DCF sheet shows up "
        "here as a low IRR. It also carries no control premium and no fees, both "
        "of which flatter it — lbo.py quantifies each.",
    )
