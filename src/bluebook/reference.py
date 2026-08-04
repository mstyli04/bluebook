"""Linked three-statement forecast model — the reference implementation.

Wires the four independent schedules (working capital, fixed assets, leases,
debt) into a forecast income statement, balance sheet and cash flow
statement that move together: change one driver and every statement
responds, and the balance sheet still balances.

--------------------------------------------------------------------------
Order of computation
--------------------------------------------------------------------------
revenue -> gross profit -> opex -> EBITDA -> schedules (fixed assets,
leases, working capital) -> D&A -> EBIT -> cash generated before financing
-> debt schedule -> interest -> profit before tax -> tax -> net income ->
dividends -> equity roll-forward -> balance sheet -> cash flow.

That order is run inside a fixed-point loop (see "The outer fixed point"
below); the order itself is never rearranged.

--------------------------------------------------------------------------
Opening balances
--------------------------------------------------------------------------
Every opening balance is the last historical year's *actual* figure, read
from ``historicals[-1]`` (FY2025):

    PP&E                832.1   ->  fixed_assets(opening_ppe=...)
    ROU assets          413.0   ->  leases(opening_rou=...)
    lease liabilities   449.8   ->  leases(opening_liability=...)
    intangibles          43.0   ->  intangibles roll-forward below
    cash                 70.8   ->  debt_schedule(opening_cash=...)
    borrowings           25.0   ->  debt_schedule(opening_debt=...)
    equity              625.2   ->  equity roll-forward below
    other assets          0.0   ->  held flat
    other liabilities   111.2   ->  held flat

and, critically, the opening *net working capital*:

    opening_nwc = inventories + trade receivables - trade payables
                = 55.7 + 69.4 - 272.8 = -147.7

``working_capital()``'s ``opening_nwc`` parameter defaults to 0.0 and that
default is wrong for a real forecast — it would make the FY2026 movement the
whole FY2026 NWC balance (~-156) instead of the movement off FY2025 (~-9),
overstating the year-1 working-capital cash swing by an order of magnitude.
The actual opening balance is passed here, and
test_year_one_working_capital_movement_uses_the_actual_opening_balances in
tests/test_reference.py pins it.

It matters that ``opening_nwc`` is built from exactly the same three
historical lines that the balance sheet's year-1 movements are measured
against; if the two disagreed the balance sheet would not balance (see the
proof below).

--------------------------------------------------------------------------
Amortisation and the intangibles balance
--------------------------------------------------------------------------
``Drivers`` has no amortisation rate field, deliberately: the project owner
ruled that amortisation is forecast as a constant share of revenue derived
from the last actual rather than by widening the frozen ``Drivers``
interface. That share is computed here from ``historicals[-1]``:

    AMORTISATION_PCT_REVENUE = 4.7 / 2151.2 = 0.2185% of revenue

The intangibles balance rolls forward as opening intangibles less that
amortisation, with no additions. This is a stated simplification, not an
oversight: ``capex`` in ``inputs/greggs.py`` is *total* cash capital
expenditure — PP&E plus intangible additions bundled together, because the
schema has no separate intangible-capex field — and ``capex_pct_revenue`` is
calibrated on that total. The whole capex figure therefore flows through the
fixed-asset schedule into PP&E, so charging a second lot of additions to
intangibles would double-count it. The consequence is that intangibles
amortise down (43.0 to ~15 by FY2030) while the intangible capex sits inside
PP&E. Total assets, total capex and total D&A are all correct; only the
split between two non-current asset lines is affected. Flagged for the owner
rather than fixed here, since fixing it means deriving a PP&E/intangible
capex split that no task asked for.

--------------------------------------------------------------------------
Lease interest
--------------------------------------------------------------------------
Lease interest does not capitalise into the lease liability (accrued and
paid interest cancel — see the note in ``schedules/leases.py``), but it IS a
real P&L finance cost. It appears in ``profit_before_tax`` as
``lease_interest`` and as a cash outflow ``lease_interest_paid``. The
liability roll-forward is additions less principal only.

--------------------------------------------------------------------------
The outer fixed point
--------------------------------------------------------------------------
Tax and dividends are cash costs, so they belong in the cash generated that
drives the debt schedule; but both depend on profit before tax, which
depends on debt interest, which depends on how much cash the year generated.
The debt schedule already solves the interest/closing-debt circularity
*within* a year; this module solves the outer tax/dividend circularity by
running the whole sequence above to a fixed point in debt interest, seeded
at zero. It converges in a handful of passes (a £1 change in interest moves
cash generated by only ~£0.375 after the tax and dividend offsets), and
mirrors how Excel's iterative calculation resolves the same loop. Failure to
converge raises rather than returning a half-solved model, for the same
reason ``DebtScheduleConvergenceError`` exists.

--------------------------------------------------------------------------
Sign conventions
--------------------------------------------------------------------------
Same convention as ``inputs/greggs.py``: every named line is a positive
magnitude of the flow its name describes — ``capex``, ``tax_paid``,
``dividends_paid`` and ``debt_repayment`` are cash out, ``revolver_draw`` is
cash in, and ``change_in_working_capital`` is the increase in NWC (a cash
outflow when positive). Only the subtotals — ``cash_from_operations``,
``net_change_in_cash`` — are signed net figures.

--------------------------------------------------------------------------
Why it balances, with no plug
--------------------------------------------------------------------------
Neither balance sheet total is derived from the other, and no line absorbs a
residual: ``total_assets`` foots its own seven asset lines and
``total_liabilities_and_equity`` foots its own five claim lines
(test_balance_sheet_totals_are_the_sum_of_their_own_components). They are
equal because every movement reaches both statements. Writing the movement
in each line over one year:

    d(assets)  = (capex - dep_ppe) + (rou_additions - dep_rou) + (-amort)
                 + d(inv) + d(rec) + d(cash)
    d(claims)  = d(pay) + (rou_additions - principal)
                 + (draw - repayment) + (net_income - dividends)

with d(cash) = cash_generated - debt_interest - repayment + draw and

    cash_generated = EBITDA - d(NWC) - capex - principal - lease_interest
                     - tax - dividends,   d(NWC) = d(inv) + d(rec) - d(pay)

Substituting, rou_additions, draw and repayment cancel, d(inv)/d(rec) cancel
against d(NWC), capex cancels, and what is left is

    EBITDA - dep_ppe - dep_rou - amort - lease_interest - debt_interest
        - tax - dividends + d(pay) - principal
    = EBIT - lease_interest - debt_interest - tax - dividends
        + d(pay) - principal
    = net_income - dividends + d(pay) - principal
    = d(claims)

so d(assets) = d(claims) identically. The opening balance sheet balances
(FY2025 actual: 1,484.0 both sides), so every forecast year does too. If
this ever breaks, the cause is a movement that reaches one statement and not
the other — not a missing balancing item.
"""

from __future__ import annotations

from dataclasses import dataclass

from bluebook.assumptions import Drivers, FORECAST_YEARS
from bluebook.inputs.schema import HistoricalYear
from bluebook.schedules.debt import INTEREST_BASIS, DebtSchedule, debt_schedule
from bluebook.schedules.fixed_assets import FixedAssets, fixed_assets
from bluebook.schedules.leases import Leases, leases
from bluebook.schedules.working_capital import WorkingCapital, working_capital

MAX_PASSES = 50
CONVERGENCE_TOLERANCE = 1e-10


class ModelConvergenceError(RuntimeError):
    """Raised when the outer tax/dividend/interest loop fails to converge.

    Deliberately not swallowed: a half-solved model would report a tax
    charge computed off one interest figure and a cash balance computed off
    another, and the balance sheet would then fail to balance for a reason
    that looks like a linkage bug but isn't.
    """


@dataclass(frozen=True)
class Model:
    """A complete linked forecast for one scenario.

    The three statements are ``dict[str, list[float]]`` keyed by line-item
    name, one entry per forecast year. The schedules are exposed too so
    downstream tasks (valuation, workbook writing) can reach the underlying
    roll-forwards without recomputing them.
    """

    years: list[str]
    income_statement: dict[str, list[float]]
    balance_sheet: dict[str, list[float]]
    cash_flow: dict[str, list[float]]
    ebitda: list[float]
    ebit: list[float]
    net_income: list[float]
    da_total: list[float]
    fixed_assets: FixedAssets
    leases: Leases
    working_capital: WorkingCapital
    debt: DebtSchedule


def build_model(historicals: list[HistoricalYear], drivers: Drivers) -> Model:
    """Build the linked three-statement forecast off the last historical year."""
    last = historicals[-1]

    # --- Opening balance sheet: last actual, never a fresh start ----------
    opening_ppe = last.ppe.value
    opening_rou = last.rou_assets.value
    opening_lease_liability = last.lease_liabilities.value
    opening_intangibles = last.intangibles.value
    opening_cash = last.cash.value
    opening_debt = last.borrowings.value
    opening_equity = last.equity.value
    other_assets = last.other_assets.value
    other_liabilities = last.other_liabilities.value
    # Must be built from the same three lines the year-1 balance sheet
    # movements are measured against — see the module docstring.
    opening_nwc = (
        last.inventories.value + last.trade_receivables.value - last.trade_payables.value
    )

    # Amortisation has no driver by deliberate ruling; derive the rate from
    # the last actual (see module docstring).
    amortisation_pct_revenue = last.amortisation.value / last.revenue.value

    # --- Revenue -> gross profit -> opex -> EBITDA ------------------------
    revenue: list[float] = []
    prior_revenue = last.revenue.value
    for growth in drivers.revenue_growth:
        prior_revenue *= 1.0 + growth
        revenue.append(prior_revenue)

    gross_profit = [r * m for r, m in zip(revenue, drivers.gross_margin)]
    cost_of_sales = [r - g for r, g in zip(revenue, gross_profit)]
    operating_costs = [r * o for r, o in zip(revenue, drivers.opex_pct_revenue)]
    ebitda = [g - o for g, o in zip(gross_profit, operating_costs)]

    # --- Schedules --------------------------------------------------------
    assets = fixed_assets(opening_ppe, revenue, drivers)
    lease = leases(opening_rou, opening_lease_liability, revenue, drivers)
    nwc = working_capital(revenue, cost_of_sales, drivers, opening_nwc=opening_nwc)

    # --- D&A -> EBIT ------------------------------------------------------
    amortisation = [r * amortisation_pct_revenue for r in revenue]
    da_total = [
        d_ppe + d_rou + amort
        for d_ppe, d_rou, amort in zip(assets.depreciation, lease.depreciation, amortisation)
    ]
    ebit = [e - d for e, d in zip(ebitda, da_total)]

    # --- Cash generated before financing -> debt schedule -> interest -----
    # -> PBT -> tax -> net income -> dividends, iterated to a fixed point
    # because tax and dividends are cash costs that depend on debt interest,
    # which depends on the cash they consume (see module docstring).
    debt_interest = [0.0] * len(revenue)
    for _ in range(MAX_PASSES):
        profit_before_tax = [
            e - lease_int - debt_int
            for e, lease_int, debt_int in zip(ebit, lease.interest, debt_interest)
        ]
        tax = [p * drivers.tax_rate for p in profit_before_tax]
        net_income = [p - t for p, t in zip(profit_before_tax, tax)]
        dividends = [n * drivers.dividend_payout_ratio for n in net_income]
        cash_generated = [
            e - change - capex - principal - lease_int - t - div
            for e, change, capex, principal, lease_int, t, div in zip(
                ebitda,
                nwc.change_in_nwc,
                assets.capex,
                lease.principal_paid,
                lease.interest,
                tax,
                dividends,
            )
        ]
        debt = debt_schedule(
            opening_debt, opening_cash, cash_generated, drivers, INTEREST_BASIS
        )
        moved = max(abs(new - old) for new, old in zip(debt.interest, debt_interest))
        if moved < CONVERGENCE_TOLERANCE:
            break
        debt_interest = list(debt.interest)
    else:
        raise ModelConvergenceError(
            f"three-statement model failed to converge after {MAX_PASSES} passes "
            f"(last interest movement={moved}, tolerance={CONVERGENCE_TOLERANCE})"
        )

    # --- Equity roll-forward ---------------------------------------------
    equity: list[float] = []
    balance = opening_equity
    for income, dividend in zip(net_income, dividends):
        balance += income - dividend
        equity.append(balance)

    # --- Intangibles roll-forward (amortisation only, see docstring) ------
    intangibles: list[float] = []
    balance = opening_intangibles
    for amort in amortisation:
        balance -= amort
        intangibles.append(balance)

    # --- Cash flow statement ---------------------------------------------
    # Built from its own components so it foots exactly; the debt schedule
    # tracks cash independently and the two are cross-checked by
    # test_cash_flow_agrees_with_the_debt_schedules_own_cash_balance.
    cash_from_operations = [
        e - change - t for e, change, t in zip(ebitda, nwc.change_in_nwc, tax)
    ]
    net_change_in_cash = [
        cfo - capex - lease_int - principal - debt_int - repayment + draw - dividend
        for cfo, capex, lease_int, principal, debt_int, repayment, draw, dividend in zip(
            cash_from_operations,
            assets.capex,
            lease.interest,
            lease.principal_paid,
            debt_interest,
            debt.repayment,
            debt.revolver_draw,
            dividends,
        )
    ]
    opening_cash_balances: list[float] = []
    closing_cash_balances: list[float] = []
    balance = opening_cash
    for movement in net_change_in_cash:
        opening_cash_balances.append(balance)
        balance += movement
        closing_cash_balances.append(balance)

    income_statement = {
        "revenue": revenue,
        "cost_of_sales": cost_of_sales,
        "gross_profit": gross_profit,
        "operating_costs": operating_costs,
        "ebitda": ebitda,
        "depreciation_ppe": assets.depreciation,
        "depreciation_rou": lease.depreciation,
        "amortisation": amortisation,
        "ebit": ebit,
        "lease_interest": lease.interest,
        "debt_interest": debt_interest,
        "profit_before_tax": profit_before_tax,
        "tax": tax,
        "net_income": net_income,
    }

    balance_sheet = {
        "ppe": assets.closing_ppe,
        "rou_assets": lease.closing_rou,
        "intangibles": intangibles,
        "inventories": nwc.inventories,
        "trade_receivables": nwc.receivables,
        "cash": closing_cash_balances,
        "other_assets": [other_assets] * len(revenue),
        "trade_payables": nwc.payables,
        "lease_liabilities": lease.closing_liability,
        "borrowings": debt.closing,
        "other_liabilities": [other_liabilities] * len(revenue),
        "equity": equity,
    }
    balance_sheet["total_assets"] = [
        ppe + rou + intangible + inventory + receivable + cash + other
        for ppe, rou, intangible, inventory, receivable, cash, other in zip(
            balance_sheet["ppe"],
            balance_sheet["rou_assets"],
            balance_sheet["intangibles"],
            balance_sheet["inventories"],
            balance_sheet["trade_receivables"],
            balance_sheet["cash"],
            balance_sheet["other_assets"],
        )
    ]
    balance_sheet["total_liabilities_and_equity"] = [
        payable + lease_liability + borrowing + other + shareholders
        for payable, lease_liability, borrowing, other, shareholders in zip(
            balance_sheet["trade_payables"],
            balance_sheet["lease_liabilities"],
            balance_sheet["borrowings"],
            balance_sheet["other_liabilities"],
            balance_sheet["equity"],
        )
    ]

    cash_flow = {
        "ebitda": ebitda,
        "change_in_working_capital": nwc.change_in_nwc,
        "tax_paid": tax,
        "cash_from_operations": cash_from_operations,
        "capex": assets.capex,
        "lease_interest_paid": lease.interest,
        "lease_principal_paid": lease.principal_paid,
        "debt_interest_paid": debt_interest,
        "debt_repayment": debt.repayment,
        "revolver_draw": debt.revolver_draw,
        "dividends_paid": dividends,
        "net_change_in_cash": net_change_in_cash,
        "opening_cash": opening_cash_balances,
        "closing_cash": closing_cash_balances,
    }

    return Model(
        years=list(FORECAST_YEARS),
        income_statement=income_statement,
        balance_sheet=balance_sheet,
        cash_flow=cash_flow,
        ebitda=ebitda,
        ebit=ebit,
        net_income=net_income,
        da_total=da_total,
        fixed_assets=assets,
        leases=lease,
        working_capital=nwc,
        debt=debt,
    )
