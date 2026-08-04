"""Fixed asset schedule: PP&E roll-forward (capex less depreciation).

Pure function of opening PP&E, revenue and the capex/depreciation drivers.
Does not import the other schedule modules (working_capital, leases) — each
schedule is independent and gets wired together downstream in the linked
three-statement model.

Note: ``drivers.ppe_depreciation_rate`` is calibrated against
``depreciation_ppe`` in the historicals, which includes that year's net PPE
impairment charge (see ``inputs/greggs.py`` module docstring). The
depreciation this schedule produces therefore also represents
depreciation-plus-impairment, not textbook straight-line depreciation alone.
This is a deliberate upstream ruling, not something to correct here.
"""

from __future__ import annotations

from dataclasses import dataclass

from bluebook.assumptions import Drivers


@dataclass(frozen=True)
class FixedAssets:
    capex: list[float]
    depreciation: list[float]
    closing_ppe: list[float]


def fixed_assets(
    opening_ppe: float,
    revenue: list[float],
    drivers: Drivers,
) -> FixedAssets:
    capex: list[float] = []
    depreciation: list[float] = []
    closing_ppe: list[float] = []

    ppe = opening_ppe
    for year_revenue, capex_pct in zip(revenue, drivers.capex_pct_revenue):
        year_capex = year_revenue * capex_pct
        year_depreciation = ppe * drivers.ppe_depreciation_rate
        ppe = ppe + year_capex - year_depreciation

        capex.append(year_capex)
        depreciation.append(year_depreciation)
        closing_ppe.append(ppe)

    return FixedAssets(capex, depreciation, closing_ppe)
