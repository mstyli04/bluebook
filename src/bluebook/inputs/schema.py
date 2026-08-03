from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Sourced:
    """A figure transcribed from a filing, with its provenance."""

    value: float
    source: str

    def __post_init__(self) -> None:
        if not self.source.strip():
            raise ValueError("every historical figure requires a source reference")


@dataclass(frozen=True)
class HistoricalYear:
    """One reported financial year, £m, post-IFRS 16 as reported."""

    label: str                      # e.g. "FY2025"

    # Income statement
    revenue: Sourced
    cost_of_sales: Sourced
    operating_costs: Sourced        # distribution + admin, less other income, less D&A and impairment
    depreciation_ppe: Sourced       # includes net impairment of PPE
    depreciation_rou: Sourced       # right-of-use asset depreciation, including net ROU impairment
    amortisation: Sourced
    finance_costs: Sourced          # includes lease interest
    finance_income: Sourced
    tax_expense: Sourced

    # Balance sheet
    ppe: Sourced
    rou_assets: Sourced
    intangibles: Sourced
    inventories: Sourced
    trade_receivables: Sourced
    cash: Sourced
    trade_payables: Sourced
    lease_liabilities: Sourced
    borrowings: Sourced
    other_assets: Sourced           # everything not itemised above
    other_liabilities: Sourced
    equity: Sourced

    # Cash flow
    capex: Sourced
    lease_principal_paid: Sourced
    rou_additions: Sourced
    dividends_paid: Sourced
