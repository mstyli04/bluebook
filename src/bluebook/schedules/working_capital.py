"""Working capital schedule: inventories, receivables, payables and NWC.

Pure function of revenue, cost of sales and the day-count drivers. Does not
import the other schedule modules (fixed_assets, leases) — each schedule is
independent and gets wired together downstream in the three-statement model.
"""

from __future__ import annotations

from dataclasses import dataclass

from bluebook.assumptions import Drivers

DAYS_IN_YEAR = 365.0


@dataclass(frozen=True)
class WorkingCapital:
    inventories: list[float]
    receivables: list[float]
    payables: list[float]
    net_working_capital: list[float]
    change_in_nwc: list[float]


def working_capital(
    revenue: list[float],
    cost_of_sales: list[float],
    drivers: Drivers,
    # Default of 0.0 is only correct if opening NWC really is zero, which is
    # never true for a real forecast. It exists purely so this function's
    # own unit tests don't have to supply one. Task 8 (the linked
    # three-statement model) MUST pass the actual net working capital of the
    # last historical year (FY2025) here — otherwise change_in_nwc[0] jumps
    # from an implied opening balance of zero to the first forecast year's
    # full NWC balance, wildly overstating the year-1 working-capital cash
    # outflow (or inflow).
    opening_nwc: float = 0.0,
) -> WorkingCapital:
    inventories = [c * drivers.inventory_days / DAYS_IN_YEAR for c in cost_of_sales]
    receivables = [r * drivers.receivable_days / DAYS_IN_YEAR for r in revenue]
    payables = [c * drivers.payable_days / DAYS_IN_YEAR for c in cost_of_sales]
    nwc = [i + r - p for i, r, p in zip(inventories, receivables, payables)]
    prior = [opening_nwc, *nwc[:-1]]
    change = [n - p for n, p in zip(nwc, prior)]
    return WorkingCapital(inventories, receivables, payables, nwc, change)
