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

That order is run literally, inside a fixed-point loop (see "The outer
fixed point" below) whose seed is the pair of quantities the order needs
before it has computed them: tax and dividends, seeded at zero.

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
Intangibles and amortisation
--------------------------------------------------------------------------
``Drivers`` has no amortisation rate field and is frozen, so both sides of
the intangibles roll-forward are derived here from ``historicals`` instead.
Both are derived, never hardcoded, so they cannot drift from the filings.

``capex`` in ``inputs/greggs.py`` is *total* cash capital expenditure —
PP&E plus intangible additions bundled together, because the schema has no
separate intangible-capex field — and ``capex_pct_revenue`` is calibrated on
that total. It is therefore split before use:

    intangible capex share = implied intangible additions / total capex,
                             aggregated over every year with a prior-year
                             balance to roll off (FY2024 + FY2025)
                           = (10.8 + 22.8) / (240.9 + 285.4) = 6.38%

This is a two-year aggregate rather than the three-year one, because
FY2023's intangible capex is not recoverable from the schema: implied
additions need a prior-year balance to roll off and FY2022 is not in
``GREGGS_HISTORICALS``. The disclosed three-year split (41.6 / 724.4 =
5.74%) exists only in prose comments in ``inputs/greggs.py`` — ``capex`` is
a single field — so it cannot be derived, and hardcoding it would put a
figure in this module that no test could tie back to the filings. Owner
ruling: derivation wins, two-year aggregate accepted. Closing the 64bp gap
properly needs a ``capex_intangible`` field in ``inputs/schema.py``.

where implied additions = closing intangibles - opening intangibles +
amortisation. The PP&E share (93.62%) is what the fixed-asset schedule sees;
the remainder is added to intangibles. The cash flow reports the total, so
capex is never double-counted or lost.

    amortisation rate = FY2025 amortisation / FY2024 closing intangibles
                      = 4.7 / 24.9 = 18.88% of opening intangibles

charged on the opening balance, exactly as ``ppe_depreciation_rate`` and
``rou_depreciation_rate`` are (and anchored on the last actual year, as they
are). This **supersedes an earlier ruling** that amortisation be a constant
share of revenue. That version was mismatched: additions accrued on one
basis while the charge against them accrued on another, so the intangibles
balance drifted with no economic meaning — it amortised away to £15m by
FY2030 while the company was still capitalising software every year, and
FY2030 total assets moved £28.7m purely on the choice of basis. Running both
sides off the asset balance removes that. The result is self-consistent: the
implied steady state, c(1 + g)/(g + d) = 0.0638 x 0.07 x 1.045 / 0.2338,
is 2.0% of revenue, and the FY2025 actual is 43.0 / 2151.2 = 2.0%. The two
derived rates reproduce the observed balance without being fitted to it.

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
running the sequence above to a fixed point, **seeded with tax and dividends
at zero** so that each pass executes the briefed order literally: cash
generated, then the debt schedule, then interest, then profit before tax,
then tax, then net income, then dividends. It converges in 11 passes (a £1
change in interest moves cash generated by only ~£0.375 after the tax and
dividend offsets), and mirrors how Excel's iterative calculation resolves
the same loop. Failure to converge raises rather than returning a
half-solved model, for the same reason ``DebtScheduleConvergenceError``
exists.

After the loop, one settling pass rebuilds cash generated from the converged
tax and dividends and reruns the debt schedule, so that the reported cash
flow, debt balances and P&L interest are all the *same* numbers rather than
merely equal to within the tolerance. Everything the balance sheet depends
on is then exact; the only slack left anywhere is that the reported tax was
computed from an interest figure differing from the reported one by ~1e-12.

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

    d(assets)  = (ppe_capex - dep_ppe) + (rou_additions - dep_rou)
                 + (intangible_capex - amort)
                 + d(inv) + d(rec) + d(cash)
    d(claims)  = d(pay) + (rou_additions - principal)
                 + (draw - repayment) + (net_income - dividends)

with d(cash) = cash_generated - debt_interest - repayment + draw and

    cash_generated = EBITDA - d(NWC) - capex - principal - lease_interest
                     - tax - dividends,   d(NWC) = d(inv) + d(rec) - d(pay)

and capex = ppe_capex + intangible_capex, which is why the cash flow must
report the *total* while the fixed-asset schedule sees only the PP&E share:
a split that failed to add back to the total would unbalance the balance
sheet by the difference.

Substituting, rou_additions, draw and repayment cancel, d(inv)/d(rec) cancel
against d(NWC), both halves of capex cancel, and what is left is

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

from dataclasses import dataclass, replace

from bluebook.assumptions import (
    FORECAST_YEARS,
    Drivers,
    amortisation_rate,
    intangible_capex_share,
)
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

    # Intangibles have no drivers (Drivers is frozen); both sides of the
    # roll-forward are derived from the filings — see module docstring.
    intangible_share = intangible_capex_share(historicals)
    amortisation_pct = amortisation_rate(historicals)

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
    # drivers.capex_pct_revenue is calibrated on TOTAL cash capex, so only
    # the PP&E share is routed through the fixed-asset schedule. The
    # intangible share is added to intangibles below and the two are summed
    # back to the total for the cash flow — see module docstring.
    ppe_drivers = replace(
        drivers,
        capex_pct_revenue=tuple(
            c * (1.0 - intangible_share) for c in drivers.capex_pct_revenue
        ),
    )
    assets = fixed_assets(opening_ppe, revenue, ppe_drivers)
    lease = leases(opening_rou, opening_lease_liability, revenue, drivers)
    nwc = working_capital(revenue, cost_of_sales, drivers, opening_nwc=opening_nwc)

    intangible_capex = [
        r * capex_pct * intangible_share
        for r, capex_pct in zip(revenue, drivers.capex_pct_revenue)
    ]
    total_capex = [p + i for p, i in zip(assets.capex, intangible_capex)]

    # --- D&A -> EBIT ------------------------------------------------------
    # Intangibles roll forward on the same basis the charge is computed on:
    # amortisation is a rate on the OPENING balance, like PP&E and ROU
    # depreciation, not a share of revenue.
    amortisation: list[float] = []
    intangibles: list[float] = []
    intangible_balance = opening_intangibles
    for additions in intangible_capex:
        year_amortisation = intangible_balance * amortisation_pct
        intangible_balance += additions - year_amortisation
        amortisation.append(year_amortisation)
        intangibles.append(intangible_balance)

    da_total = [
        d_ppe + d_rou + amort
        for d_ppe, d_rou, amort in zip(assets.depreciation, lease.depreciation, amortisation)
    ]
    ebit = [e - d for e, d in zip(ebitda, da_total)]

    # --- Cash generated before financing -> debt schedule -> interest -----
    # -> PBT -> tax -> net income -> dividends. Each pass runs that order
    # literally; the loop exists because the first step needs the last two,
    # so they are seeded at zero and the sequence is repeated to a fixed
    # point (see module docstring).
    def _cash_generated(tax: list[float], dividends: list[float]) -> list[float]:
        return [
            e - change - capex - principal - lease_int - t - div
            for e, change, capex, principal, lease_int, t, div in zip(
                ebitda,
                nwc.change_in_nwc,
                total_capex,
                lease.principal_paid,
                lease.interest,
                tax,
                dividends,
            )
        ]

    tax = [0.0] * len(revenue)
    dividends = [0.0] * len(revenue)
    profit_before_tax = list(ebit)
    net_income = list(ebit)
    # Bound before the loop so the `else:` branch below can report it even
    # if the loop body never runs (an empty forecast).
    moved = float("inf")
    for _ in range(MAX_PASSES):
        cash_generated = _cash_generated(tax, dividends)
        debt = debt_schedule(
            opening_debt, opening_cash, cash_generated, drivers, INTEREST_BASIS
        )
        profit_before_tax = [
            e - lease_int - debt_int
            for e, lease_int, debt_int in zip(ebit, lease.interest, debt.interest)
        ]
        # A loss attracts no charge rather than a refund: this model has no
        # NOL carryforward, and a negative tax line would show cash arriving
        # from HMRC in a loss year. Same for dividends — a loss-making year
        # pays nothing; it does not collect from shareholders.
        new_tax = [max(p, 0.0) * drivers.tax_rate for p in profit_before_tax]
        net_income = [p - t for p, t in zip(profit_before_tax, new_tax)]
        new_dividends = [max(n, 0.0) * drivers.dividend_payout_ratio for n in net_income]

        moved = max(
            (
                max(abs(t - t_old), abs(d - d_old))
                for t, t_old, d, d_old in zip(new_tax, tax, new_dividends, dividends)
            ),
            default=0.0,
        )
        tax, dividends = new_tax, new_dividends
        if moved < CONVERGENCE_TOLERANCE:
            break
    else:
        raise ModelConvergenceError(
            f"three-statement model failed to converge after {MAX_PASSES} passes "
            f"(last tax/dividend movement={moved}, tolerance={CONVERGENCE_TOLERANCE})"
        )

    # Settling pass: rebuild cash generated from the converged tax and
    # dividends and rerun the schedule, so the reported cash flow, debt
    # balances and P&L interest are the same numbers rather than merely
    # equal to within the tolerance.
    cash_generated = _cash_generated(tax, dividends)
    debt = debt_schedule(opening_debt, opening_cash, cash_generated, drivers, INTEREST_BASIS)
    debt_interest = list(debt.interest)

    # --- Equity roll-forward ---------------------------------------------
    equity: list[float] = []
    balance = opening_equity
    for income, dividend in zip(net_income, dividends):
        balance += income - dividend
        equity.append(balance)

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
            total_capex,
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
        # Total cash capex, on the same definition as inputs/greggs.py.
        # The two components are shown beside it because the split drives
        # two different balance sheet lines.
        "capex": total_capex,
        "capex_ppe": assets.capex,
        "capex_intangible": intangible_capex,
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
