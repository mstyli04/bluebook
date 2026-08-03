"""Greggs plc reported financials, transcribed from published annual reports.

Every figure carries the report and page it came from. Figures are £m on the
reported post-IFRS 16 basis. Do not edit a value without re-checking the filing.

Source documents (fetched 3 August 2026):
  FY2023 AR — "Greggs plc Annual Report and Accounts 2023"
      https://a.storyblok.com/f/162306/x/6191f7066b/greggs-annual-report-and-accounts-2023.pdf
  FY2024 AR — "Greggs plc Annual Report and Accounts 2024"
      https://a.storyblok.com/f/162306/x/043b5db0ef/greggs-annual-report-and-accounts-2024.pdf
  FY2025 AR — "Greggs plc Annual Report and Accounts 2025" (interactive)
      https://assets.greggs.com/f/162306/x/b1b0408bb2/greggs-ar25-interactive.pdf
Page references are the *printed* page numbers shown on the page, not PDF indices.

Conventions applied throughout:

* Sign: every figure is a positive magnitude. Costs, tax, capex, lease principal
  repayments and dividends are stored unsigned; the model applies the signs.
* Basis: "Total" column of the income statement, i.e. INCLUDING exceptional
  items, so the figures tie to reported operating profit and profit before tax.
* Group (consolidated) column of the balance sheet, never the Parent Company.
* `depreciation_ppe` and `depreciation_rou` each INCLUDE the year's net impairment
  charge on that asset class (PPE impairment in `depreciation_ppe`, right-of-use
  impairment in `depreciation_rou`). Impairment is a non-cash charge, and the
  model's free cash flow bridge adds back D&A while deducting capex in full;
  leaving impairment inside EBIT with no add-back would double-count it against
  capex. Amounts and pages are recorded beside each value.
* `operating_costs` is distribution and selling costs + administrative expenses,
  LESS other income, LESS everything carried in the `depreciation_*` and
  `amortisation` fields (i.e. D&A and impairment). Greggs does not disclose how D&A
  splits across cost of sales / distribution / admin (FY2025 AR p.138 states ROU
  depreciation sits in "cost of sales, selling and distribution costs or
  administrative expenses as appropriate"), so `operating_costs` is defined as the
  residual that makes
      revenue - cost_of_sales - operating_costs
          - depreciation_ppe - depreciation_rou - amortisation
          = reported operating profit
  hold exactly for each year. The full build-up of the residual is written out in
  the comment beside each year's value, so the figure is recoverable from this file
  without reopening the PDFs.
* `other_assets` / `other_liabilities` are the genuine sum of the balance sheet
  lines not itemised in the schema, taken line by line from the face of the
  balance sheet. They are not plugs.
* `capex` is total cash capital expenditure: acquisition of property, plant and
  equipment PLUS acquisition of intangible assets, because the schema models
  intangibles and amortisation but has no separate intangible-capex field. The
  split is recorded in the comment beside each value.
* `rou_additions` is additions to right-of-use assets from entering into new
  leases only; net increases from lease modifications / lease-term reassessment
  are excluded and noted in the comment beside each value.
"""

from __future__ import annotations

from bluebook.inputs.schema import HistoricalYear, Sourced

# Stated on the face of each primary statement; all three years are 52-week
# periods ending on a Saturday in late December. Greggs notes that 2020 was a
# 53-week year (FY2025 AR p.174, ten-year history) and that 2014 and 2020 were
# 53-week years (FY2024 AR p.172, ten-year history).
GREGGS_FYE_CONVENTION = (
    "52/53-week financial year ending on a Saturday in late December. "
    "FY2023 = 52 weeks ended 30 December 2023; "
    "FY2024 = 52 weeks ended 28 December 2024; "
    "FY2025 = 52 weeks ended 27 December 2025."
)

# Weighted average number of ordinary shares (diluted) for FY2025: 102,482,895.
GREGGS_SHARE_COUNT = Sourced(102.482895, "FY2025 AR p.152 (Note 9)")  # millions, weighted average diluted

FY2023 = HistoricalYear(
    label="FY2023",
    # --- Income statement (FY2023 AR p.119, "2023 Total" column) ---
    revenue=Sourced(1809.6, "FY2023 AR p.119"),
    cost_of_sales=Sourced(710.5, "FY2023 AR p.119"),
    # Residual build-up (all FY2023 AR p.119 unless stated):
    #   844.2 distribution and selling costs
    # +  82.9 administrative expenses
    # -  20.3 other income
    # -  66.6 depreciation of PPE            (p.124)
    # -   1.4 net impairment of PPE          (p.124)
    # -  54.5 depreciation of ROU assets     (p.124)
    # -   2.5 impairment of ROU assets       (p.124)
    # -   3.9 amortisation                   (p.124)
    # = 777.9
    operating_costs=Sourced(777.9, "FY2023 AR p.119, p.124 (D&A and impairment)"),
    depreciation_ppe=Sourced(68.0, "FY2023 AR p.124"),  # 66.6 depreciation + 1.4 net impairment of PPE
    depreciation_rou=Sourced(57.0, "FY2023 AR p.124"),  # 54.5 depreciation + 2.5 impairment of ROU assets
    amortisation=Sourced(3.9, "FY2023 AR p.124"),
    # The FY2023 AR presents finance expense net (p.119, £4.0m net; Note 6 p.140).
    # The gross split is taken from the FY2024 AR's comparative column, which is
    # the same figures presented gross: income 6.1, expense 10.1 (net 4.0).
    finance_costs=Sourced(10.1, "FY2024 AR p.128 (2023 comparative)"),
    finance_income=Sourced(6.1, "FY2024 AR p.128 (2023 comparative)"),
    tax_expense=Sourced(45.8, "FY2023 AR p.119"),
    # --- Balance sheet at 30 December 2023 (FY2023 AR p.120, Group column) ---
    ppe=Sourced(510.3, "FY2023 AR p.120"),
    rou_assets=Sourced(296.6, "FY2023 AR p.120"),
    intangibles=Sourced(18.3, "FY2023 AR p.120"),
    inventories=Sourced(48.8, "FY2023 AR p.120"),
    trade_receivables=Sourced(53.8, "FY2023 AR p.120"),  # trade and other receivables
    cash=Sourced(195.3, "FY2023 AR p.120"),
    trade_payables=Sourced(211.1, "FY2023 AR p.120"),  # trade and other payables, current
    lease_liabilities=Sourced(319.6, "FY2023 AR p.120"),  # 52.5 current + 267.1 non-current
    borrowings=Sourced(0.0, "FY2023 AR p.120"),  # no borrowings line on the balance sheet
    other_assets=Sourced(6.6, "FY2023 AR p.120"),  # defined benefit pension asset 6.6
    # 4.9 current tax + 4.0 provisions + 2.3 other payables + 54.7 deferred tax + 2.2 LT provisions
    other_liabilities=Sourced(68.1, "FY2023 AR p.120"),
    equity=Sourced(530.9, "FY2023 AR p.120"),
    # --- Cash flow (FY2023 AR p.123) ---
    capex=Sourced(198.1, "FY2023 AR p.123"),  # 189.5 PPE + 8.6 intangibles
    lease_principal_paid=Sourced(53.7, "FY2023 AR p.123"),
    rou_additions=Sourced(70.3, "FY2023 AR p.144 (Note 11)"),  # new leases; excludes +1.7 modifications
    dividends_paid=Sourced(60.8, "FY2023 AR p.123"),
)

FY2024 = HistoricalYear(
    label="FY2024",
    # --- Income statement (FY2024 AR p.128, "2024 Total" column) ---
    revenue=Sourced(2014.4, "FY2024 AR p.128"),
    cost_of_sales=Sourced(770.8, "FY2024 AR p.128"),
    # Residual build-up (all FY2024 AR p.128 unless stated):
    #   950.1 distribution and selling costs
    # +  97.9 administrative expenses
    # -  13.8 other income
    # -  76.6 depreciation of owned PPE          (p.147, Note 3)
    # -   2.9 net impairment of owned PPE        (p.147, Note 3)
    # -  59.2 depreciation of ROU assets         (p.147, Note 3)
    # -   2.1 net impairment of ROU assets       (p.147, Note 3)
    # -   4.2 amortisation                       (p.147, Note 3)
    # = 889.2
    operating_costs=Sourced(889.2, "FY2024 AR p.128, p.147 (D&A and impairment)"),
    depreciation_ppe=Sourced(79.5, "FY2024 AR p.147 (Note 3)"),  # 76.6 depreciation + 2.9 net impairment of owned PPE
    depreciation_rou=Sourced(61.3, "FY2024 AR p.147 (Note 3)"),  # 59.2 depreciation + 2.1 net impairment of ROU assets
    amortisation=Sourced(4.2, "FY2024 AR p.147 (Note 3)"),
    finance_costs=Sourced(13.6, "FY2024 AR p.128"),
    finance_income=Sourced(8.1, "FY2024 AR p.128"),
    tax_expense=Sourced(50.5, "FY2024 AR p.128"),
    # --- Balance sheet at 28 December 2024 (FY2024 AR p.129, Group column) ---
    ppe=Sourced(664.7, "FY2024 AR p.129"),
    rou_assets=Sourced(387.2, "FY2024 AR p.129"),
    intangibles=Sourced(24.9, "FY2024 AR p.129"),
    inventories=Sourced(55.2, "FY2024 AR p.129"),
    trade_receivables=Sourced(62.4, "FY2024 AR p.129"),  # trade and other receivables
    cash=Sourced(125.3, "FY2024 AR p.129"),
    trade_payables=Sourced(243.9, "FY2024 AR p.129"),  # trade and other payables, current
    lease_liabilities=Sourced(415.1, "FY2024 AR p.129"),  # 53.8 current + 361.3 non-current
    borrowings=Sourced(0.0, "FY2024 AR p.129"),  # RCF undrawn at 28 December 2024
    other_assets=Sourced(0.0, "FY2024 AR p.129"),  # no unitemised assets; total assets 1,319.7 ties
    # 9.1 current tax + 3.4 provisions + 1.8 other payables + 72.6 deferred tax
    # + 2.9 LT provisions + 0.4 defined benefit pension liability
    other_liabilities=Sourced(90.2, "FY2024 AR p.129"),
    equity=Sourced(570.5, "FY2024 AR p.129"),
    # --- Cash flow (FY2024 AR p.132, as published; the FY2025 AR restates only
    # the operating/investing split of interest received, not these lines) ---
    capex=Sourced(240.9, "FY2024 AR p.132"),  # 230.0 PPE + 10.9 intangibles
    lease_principal_paid=Sourced(56.7, "FY2024 AR p.132"),
    rou_additions=Sourced(143.8, "FY2024 AR p.153 (Note 11)"),  # new leases; excludes +8.4 modifications
    dividends_paid=Sourced(106.8, "FY2024 AR p.132"),
)

FY2025 = HistoricalYear(
    label="FY2025",
    # --- Income statement (FY2025 AR p.128, "2025 Total" column) ---
    revenue=Sourced(2151.2, "FY2025 AR p.128"),
    cost_of_sales=Sourced(829.1, "FY2025 AR p.128"),
    # Residual build-up (all FY2025 AR p.128 unless stated):
    #   1,036.3 distribution and selling costs
    # +   102.1 administrative expenses
    # -     0.0 other income (nil in 2025)
    # -    90.7 depreciation of owned PPE        (p.148, Note 3)
    # -     3.9 net impairment of owned PPE      (p.148, Note 3; 5.5 charge less 1.6 release, p.156 Note 12)
    # -    65.2 depreciation of ROU assets       (p.148, Note 3)
    # -     3.0 net impairment of ROU assets     (p.148, Note 3; 4.9 charge less 1.9 release, p.155 Note 11)
    # -     4.7 amortisation                     (p.148, Note 3)
    # =   970.9
    operating_costs=Sourced(970.9, "FY2025 AR p.128, p.148 (D&A and impairment)"),
    depreciation_ppe=Sourced(94.6, "FY2025 AR p.148 (Note 3)"),  # 90.7 depreciation + 3.9 net impairment of owned PPE
    depreciation_rou=Sourced(68.2, "FY2025 AR p.148 (Note 3)"),  # 65.2 depreciation + 3.0 net impairment of ROU assets
    amortisation=Sourced(4.7, "FY2025 AR p.148 (Note 3)"),
    finance_costs=Sourced(18.1, "FY2025 AR p.128"),  # incl. 16.7 lease interest and 0.7 exceptional
    finance_income=Sourced(1.8, "FY2025 AR p.128"),
    tax_expense=Sourced(45.2, "FY2025 AR p.128"),
    # --- Balance sheet at 27 December 2025 (FY2025 AR p.129, Group column) ---
    ppe=Sourced(832.1, "FY2025 AR p.129"),
    rou_assets=Sourced(413.0, "FY2025 AR p.129"),
    intangibles=Sourced(43.0, "FY2025 AR p.129"),
    inventories=Sourced(55.7, "FY2025 AR p.129"),
    trade_receivables=Sourced(69.4, "FY2025 AR p.129"),  # trade and other receivables
    cash=Sourced(70.8, "FY2025 AR p.129"),
    trade_payables=Sourced(272.8, "FY2025 AR p.129"),  # trade and other payables, current
    lease_liabilities=Sourced(449.8, "FY2025 AR p.129"),  # 62.5 current + 387.3 non-current
    borrowings=Sourced(25.0, "FY2025 AR p.129"),  # drawn on the £100m RCF
    other_assets=Sourced(0.0, "FY2025 AR p.129"),  # no unitemised assets; total assets 1,484.0 ties
    # 2.1 current tax + 10.3 short-term provisions + 1.4 other payables
    # + 93.7 deferred tax + 3.4 LT provisions + 0.3 defined benefit pension liability
    other_liabilities=Sourced(111.2, "FY2025 AR p.129"),
    equity=Sourced(625.2, "FY2025 AR p.129"),
    # --- Cash flow (FY2025 AR p.132) ---
    capex=Sourced(285.4, "FY2025 AR p.132"),  # 263.3 PPE + 22.1 intangibles
    lease_principal_paid=Sourced(63.3, "FY2025 AR p.132"),
    rou_additions=Sourced(74.8, "FY2025 AR p.154 (Note 11)"),  # new leases; excludes +20.3 modifications, +0.7 restoration
    dividends_paid=Sourced(70.3, "FY2025 AR p.132"),
)

GREGGS_HISTORICALS = [FY2023, FY2024, FY2025]
