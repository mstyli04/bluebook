"""The DCF sheet: WACC, unlevered FCF, a re-based terminal year, the bridge.

Five blocks, in the order `valuation.py` computes them: the cost of capital,
the explicit five-year free cash flow and its present value, the terminal year
rebuilt at the perpetuity growth rate, the terminal value, and the enterprise-
to-equity bridge. Nothing on this sheet is a constant — the single-value rows
sit in column C, the five forecast years in F:J, and every cell is a formula.

--------------------------------------------------------------------------
The terminal year is RE-BASED, and this sheet shows the re-basing
--------------------------------------------------------------------------
The terminal value is NOT struck on the raw FY2030 forecast year, and the
reason is visible in the block that builds it: FY2030's capex and ROU
additions were derived to sustain the asset base at that scenario's terminal
REVENUE growth (4.5% in Base), while the perpetuity grows at
``perpetuity_growth`` (2.0%). A business growing more slowly needs less
sustaining investment. FY2030 is also still carrying the tail of the
distribution-centre build programme, so its PP&E/revenue is above the level
the perpetuity assumes and its free cash flow is flattered by the tax shield
on the excess depreciation.

So every investment and depreciation intensity in the terminal block is
re-derived at g*. For an asset held at intensity ``p`` that depreciates at
``d``, the steady state under growth ``g`` satisfies ``p = c(1 + g)/(g + d)``,
so the sustaining capex intensity is ``c = p(g + d)/(1 + g)`` and the
steady-state depreciation charge is ``d x p/(1 + g)`` of revenue. The rows
below are that arithmetic, cell by cell, at the anchors
`valuation.terminal_year` uses: a POST-PROGRAMME PP&E intensity (the FY2030
intensity discounted by one average asset life of perpetuity-rate growth,
because FY2025's 38.68% is the top of a rising series and FY2030's is a
transitional peak) and the FY2025 ACTUAL ROU intensity (which stepped up once
and has been flat, so there is no build-ahead to absorb).

The excess PP&E that re-basing strips out of the perpetuity is a real asset,
and its depreciation is a real tax shield, so it is added back explicitly as
its own decaying series rather than smuggled back into the perpetuity:
``shield = tax x d x E x x/(1 - x)`` with ``x = (1 - d)/(1 + WACC)`` and ``E``
the FY2029 closing excess. The formula decays ``E`` once before the first
shield year, which is why FY2029 and not FY2030 is the basis — FY2030's own
shield is a legitimate explicit-period cash flow and is already inside FY2030
free cash flow.

Discounting is mid-year throughout, terminal value included: year ``t``
discounts at ``(1 + WACC) ** (t - 0.5)`` and the terminal value at
``(1 + WACC) ** (n - 0.5)``, the same 4.5-year point the last explicit year
discounts to. The discount period row is built from ``COLUMN()`` rather than
from five written-out numbers, so the mid-year convention is one expression
and not five constants.

--------------------------------------------------------------------------
The exit-multiple terminal value is NOT a second method
--------------------------------------------------------------------------
It is reported and it is labelled, and the label says what it contains,
because a reader who takes it for corroboration of the Gordon result is being
misled. ``EV/EBITDA == EV/EBIT x (1 - D&A/EBITDA)`` is an identity, and
``drivers.exit_ev_ebitda`` IS the peer median EV/EBIT read at the terminal
year's own D&A/EBITDA (`comps.exit_multiple_from_peers`), so

    terminal value (exit multiple)  ==  peer median EV/EBIT  x  terminal EBIT

exactly, in all three scenarios — the EBITDA in the calculation cancels. The
memo row on this sheet divides the exit-multiple terminal value by the terminal
EBIT and lands on 13.4333x (Bear), 13.4202x (Base) and 13.4367x (Bull) against
the peer median of 13.4277x. The residual is the two-decimal rounding of the
shipped multiple and its sign tracks the rounding direction exactly: 5.0679 ->
5.07 and 7.2351 -> 7.24 round UP and land above the median, 6.3135 -> 6.31
rounds DOWN and lands below it. So the bar contains one peer statistic
(J D Wetherspoon's EV/EBIT, the median of five) applied to the model's own
terminal EBIT, and nothing else. It builds no part of the enterprise value
below, and the notes beside it say so on the sheet rather than only here.
"""

from __future__ import annotations

from typing import Callable, Sequence

from bluebook.workbook.formulas import aref, total
from bluebook.workbook.layout import FCST_COLS, HIST_COLS, Layout
from bluebook.workbook.sheet import SheetWriter
from bluebook.workbook.sheet_comps import MEDIAN_COL
from bluebook.workbook.styles import (
    MONEY_FORMAT,
    MULTIPLE_FORMAT,
    PENCE_FORMAT,
    PERCENT_FORMAT,
    RATIO_FORMAT,
)

SHEET = "DCF"
ASSUMPTIONS = "Assumptions"
HISTORICALS = "Historicals"
COMPS = "Comps"
IS = "IS"
BS = "BS"
SCHEDULES = "Schedules"

# Single-value rows sit in column C, as on every other sheet.
SCALAR_COL = HIST_COLS[0]
SCALAR = (SCALAR_COL,)
DRIVER_COL = HIST_COLS[0]

# The last two reported/forecast columns this sheet reaches back into: the
# terminal anchors are struck on FY2030 (J) and the excess PP&E on FY2029 (I).
FINAL_COL = FCST_COLS[-1]
PENULTIMATE_COL = FCST_COLS[-2]
LAST_ACTUAL_COL = HIST_COLS[-1]

# Pence per pound: the bridge is in £m and the price is quoted in pence.
PENCE_PER_POUND = "100"


def write_dcf(writer: SheetWriter, ref_layout: Layout, year_labels: Sequence[str]) -> None:
    """Write the DCF sheet. `writer` must be in forecast mode."""
    layout = ref_layout

    def me(key: str, col: str) -> str:
        """A per-year row of this sheet, same column."""
        return layout.ref(SHEET, key, col)

    def scalar(key: str) -> str:
        """A single-value row of this sheet, absolute so it is column-safe."""
        return aref(layout, SHEET, key, SCALAR_COL)

    def driver(key: str) -> str:
        """A single-value driver on Assumptions."""
        return aref(layout, ASSUMPTIONS, key, DRIVER_COL)

    def path(key: str, col: str) -> str:
        """A per-year driver on Assumptions."""
        return layout.ref(ASSUMPTIONS, key, col)

    def actual(key: str) -> str:
        """The last reported year's figure on Historicals."""
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
        """A label-only row: the note IS the row, as on the Cover sheet."""
        writer.formula_row(key, text, [])

    writer.title("Discounted cash flow — Gordon growth on a re-based terminal year, £m")
    writer.year_header(year_labels)

    # --- 1. Cost of capital -----------------------------------------------
    # None of the four market inputs varies by scenario, so the WACC is
    # 7.7311% in Bear, Base and Bull alike and the whole scenario spread is an
    # operating spread. The debt base INCLUDES lease liabilities, matching the
    # equity bridge below, and `cost_of_debt` is correspondingly a blend of the
    # RCF rate and the lease discount rate rather than the RCF rate alone.
    scalar_row(
        "cost_of_equity",
        "Cost of equity (CAPM: risk-free rate + beta x equity risk premium)",
        f"={driver('risk_free_rate')}+{driver('beta')}*{driver('equity_risk_premium')}",
        PERCENT_FORMAT,
    )
    scalar_row(
        "after_tax_cost_of_debt",
        "After-tax cost of debt (blended rate x (1 - tax rate))",
        f"={driver('cost_of_debt')}*(1-{driver('tax_rate')})",
        PERCENT_FORMAT,
    )
    scalar_row(
        "wacc",
        "WACC",
        f"=(1-{driver('target_debt_weight')})*{scalar('cost_of_equity')}"
        f"+{driver('target_debt_weight')}*{scalar('after_tax_cost_of_debt')}",
        PERCENT_FORMAT,
    )

    # --- 2. The explicit period -------------------------------------------
    writer.blank()
    writer.title("Unlevered free cash flow — the explicit five years")
    row("ebit", "EBIT (from the income statement)", lambda c: f"={layout.ref(IS, 'ebit', c)}",
        is_link=True)
    row(
        "ebit_after_tax",
        "EBIT after tax (unlevered: nothing below EBIT enters this sheet)",
        lambda c: f"={me('ebit', c)}*(1-{driver('tax_rate')})",
    )
    row(
        "da_total",
        "Depreciation and amortisation (added back)",
        lambda c: f"={layout.ref(IS, 'da_total', c)}",
        is_link=True,
    )
    row(
        "capex",
        "Total cash capex (PP&E + intangible)",
        lambda c: f"={layout.ref(SCHEDULES, 'total_capex', c)}",
        is_link=True,
    )
    # An investing outflow because the lease liability is deducted as debt in
    # the bridge below: funding a leased shop is then the same act as funding
    # an owned one. Omitting it while still deducting lease liabilities would
    # count the same leases twice.
    row(
        "rou_additions",
        "New ROU asset additions (an investing outflow — leases are debt here)",
        lambda c: f"={layout.ref(SCHEDULES, 'rou_additions', c)}",
        is_link=True,
    )
    row(
        "change_in_nwc",
        "Increase in net working capital",
        lambda c: f"={layout.ref(SCHEDULES, 'change_in_nwc', c)}",
        is_link=True,
    )
    row(
        "unlevered_fcf",
        "Unlevered free cash flow",
        lambda c: f"={me('ebit_after_tax', c)}+{me('da_total', c)}-{me('capex', c)}"
                  f"-{me('rou_additions', c)}-{me('change_in_nwc', c)}",
    )
    # Mid-year convention, expressed once rather than as five written-out
    # numbers: COLUMN() less the column the forecast starts in, plus a half
    # year. F reads 0.5 and J reads 4.5. Literally the same formula in all five
    # columns — hence the ignored argument — because COLUMN() supplies the only
    # thing that differs between them.
    row(
        "discount_period",
        "Discount period (years, mid-year convention)",
        lambda _col: f"=COLUMN()"
                     f"-COLUMN({aref(layout, SHEET, 'unlevered_fcf', FCST_COLS[0])})+0.5",
        RATIO_FORMAT,
    )
    row(
        "discount_factor",
        "Discount factor",
        lambda c: f"=(1+{scalar('wacc')})^{me('discount_period', c)}",
        RATIO_FORMAT,
    )
    row(
        "pv_fcf",
        "PV of unlevered free cash flow",
        lambda c: f"={me('unlevered_fcf', c)}/{me('discount_factor', c)}",
    )

    # --- 3. The terminal year, re-based on g* ------------------------------
    writer.blank()
    writer.title("Terminal year — the final year rebuilt at the perpetuity growth rate")
    note(
        "note_rebasing",
        "This block is NOT FY2030. Every investment and depreciation intensity "
        "below is re-derived at the perpetuity growth rate g*, because FY2030's "
        "were derived to sustain the estate at that scenario's own terminal "
        "revenue growth and still carry the tail of the distribution-centre "
        "programme. The revenue LEVEL is FY2030's; the (1 + g*) step to the "
        "first perpetuity year is applied by the Gordon formula below.",
    )
    scalar_row(
        "perpetuity_growth",
        "Perpetuity growth rate (g*)",
        f"={driver('perpetuity_growth')}",
        PERCENT_FORMAT,
        is_link=True,
    )
    # anchor = (FY2030 PP&E / FY2030 revenue) / (1 + g*) ^ (1 / d). One over the
    # depreciation rate is the average remaining asset life the rate itself
    # implies (7.03 years at 14.23%), and it is the right horizon because
    # capacity built ahead of demand is absorbed over the life of the asset.
    # NOT the FY2025 actual (38.68%, the top of a rising series and the last
    # observed year of the programme) and NOT the model's own FY2030 (46.67% in
    # Base, a transitional peak that is already falling).
    scalar_row(
        "terminal_ppe_intensity",
        "Terminal PP&E / revenue (post-programme anchor)",
        f"=({layout.ref(BS, 'ppe', FINAL_COL)}/{layout.ref(IS, 'revenue', FINAL_COL)})"
        f"/(1+{scalar('perpetuity_growth')})^(1/{driver('ppe_depreciation_rate')})",
        PERCENT_FORMAT,
    )
    # The leased estate keeps its FY2025 actual intensity: ROU/revenue stepped
    # up once (16.4% / 19.2% / 19.2%) and the forecast never builds a hump over
    # it, so there is no build-ahead to absorb and FY2025 is already the plateau.
    scalar_row(
        "terminal_rou_intensity",
        "Terminal ROU assets / revenue (FY2025 actual)",
        f"={actual('rou_assets')}/{actual('revenue')}",
        PERCENT_FORMAT,
    )
    # c = p (g + d) / (1 + g), grossed up by 1 / (PP&E share of capex) because
    # the driver is a TOTAL capex ratio and only 93.62% of it reaches PP&E.
    scalar_row(
        "terminal_capex_pct_revenue",
        "Terminal total capex (% of revenue, sustaining, grossed up for intangibles)",
        f"={scalar('terminal_ppe_intensity')}"
        f"*({scalar('perpetuity_growth')}+{driver('ppe_depreciation_rate')})"
        f"/(1+{scalar('perpetuity_growth')})/{driver('ppe_capex_share')}",
        PERCENT_FORMAT,
    )
    scalar_row(
        "terminal_rou_additions_pct_revenue",
        "Terminal ROU additions (% of revenue, sustaining)",
        f"={scalar('terminal_rou_intensity')}"
        f"*({scalar('perpetuity_growth')}+{driver('rou_depreciation_rate')})"
        f"/(1+{scalar('perpetuity_growth')})",
        PERCENT_FORMAT,
    )
    # Depreciation in a steady-state year is d on the OPENING balance, and the
    # opening balance is p x the prior year's revenue, hence the /(1 + g*).
    scalar_row(
        "terminal_depreciation_ppe_pct",
        "Terminal PP&E depreciation (% of revenue)",
        f"={driver('ppe_depreciation_rate')}*{scalar('terminal_ppe_intensity')}"
        f"/(1+{scalar('perpetuity_growth')})",
        PERCENT_FORMAT,
    )
    scalar_row(
        "terminal_depreciation_rou_pct",
        "Terminal ROU depreciation (% of revenue)",
        f"={driver('rou_depreciation_rate')}*{scalar('terminal_rou_intensity')}"
        f"/(1+{scalar('perpetuity_growth')})",
        PERCENT_FORMAT,
    )
    scalar_row(
        "terminal_intangible_capex_pct",
        "Terminal intangible additions (% of revenue)",
        f"={scalar('terminal_capex_pct_revenue')}*{driver('intangible_capex_share')}",
        PERCENT_FORMAT,
    )
    # Intangibles reach their own steady state off that slice: balance =
    # c_int (1 + g) / (g + a) and charge = a x opening, which collapses to
    # c_int x a / (g + a) of revenue.
    scalar_row(
        "terminal_amortisation_pct",
        "Terminal amortisation (% of revenue)",
        f"={scalar('terminal_intangible_capex_pct')}*{driver('amortisation_rate')}"
        f"/({scalar('perpetuity_growth')}+{driver('amortisation_rate')})",
        PERCENT_FORMAT,
    )
    scalar_row(
        "terminal_da_pct_revenue",
        "Terminal D&A (% of revenue)",
        f"={scalar('terminal_depreciation_ppe_pct')}+{scalar('terminal_depreciation_rou_pct')}"
        f"+{scalar('terminal_amortisation_pct')}",
        PERCENT_FORMAT,
    )
    scalar_row(
        "terminal_nwc_pct_revenue",
        "Terminal net working capital (% of revenue, negative — payables dominate)",
        f"={layout.ref(SCHEDULES, 'net_working_capital', FINAL_COL)}"
        f"/{layout.ref(IS, 'revenue', FINAL_COL)}",
        PERCENT_FORMAT,
    )
    scalar_row(
        "terminal_revenue",
        "Terminal revenue (the FY2030 LEVEL, not FY2031's)",
        f"={layout.ref(IS, 'revenue', FINAL_COL)}",
        is_link=True,
    )
    # The operating margin is the final forecast year's, unchanged: the
    # re-basing is about the investment and depreciation intensities, which
    # FY2030 gets wrong, not about the P&L margin, which is already a settled
    # steady-state judgement in the drivers.
    scalar_row(
        "terminal_ebitda_margin",
        "Terminal EBITDA margin (FY2030 gross margin less FY2030 opex ratio)",
        f"={path('gross_margin', FINAL_COL)}-{path('opex_pct_revenue', FINAL_COL)}",
        PERCENT_FORMAT,
    )
    scalar_row(
        "terminal_ebitda",
        "Terminal EBITDA (margin x revenue)",
        f"={scalar('terminal_ebitda_margin')}*{scalar('terminal_revenue')}",
    )
    scalar_row(
        "terminal_da",
        "Terminal depreciation and amortisation",
        f"={scalar('terminal_da_pct_revenue')}*{scalar('terminal_revenue')}",
    )
    scalar_row(
        "terminal_ebit",
        "Terminal EBIT",
        f"={scalar('terminal_ebitda')}-{scalar('terminal_da')}",
    )
    scalar_row(
        "terminal_capex",
        "Terminal total cash capex",
        f"={scalar('terminal_capex_pct_revenue')}*{scalar('terminal_revenue')}",
    )
    scalar_row(
        "terminal_rou_additions",
        "Terminal ROU asset additions",
        f"={scalar('terminal_rou_additions_pct_revenue')}*{scalar('terminal_revenue')}",
    )
    # NWC grows with revenue, so the movement is the intensity times the growth
    # step. Negative for Greggs, so growth RELEASES cash and this is an inflow.
    scalar_row(
        "terminal_change_in_nwc",
        "Terminal increase in net working capital (negative = cash released)",
        f"={scalar('terminal_nwc_pct_revenue')}*{scalar('perpetuity_growth')}"
        f"/(1+{scalar('perpetuity_growth')})*{scalar('terminal_revenue')}",
    )
    scalar_row(
        "terminal_fcf",
        "Terminal unlevered free cash flow",
        f"={scalar('terminal_ebit')}*(1-{driver('tax_rate')})+{scalar('terminal_da')}"
        f"-{scalar('terminal_capex')}-{scalar('terminal_rou_additions')}"
        f"-{scalar('terminal_change_in_nwc')}",
    )
    # Read by Comps, which derives the exit multiple from it.
    scalar_row(
        "terminal_da_over_ebitda",
        "Terminal D&A / EBITDA (the capital intensity Comps prices)",
        f"={scalar('terminal_da')}/{scalar('terminal_ebitda')}",
        PERCENT_FORMAT,
    )

    # --- 4. Terminal value -------------------------------------------------
    writer.blank()
    writer.title("Terminal value")
    scalar_row(
        "terminal_value_gordon",
        "Terminal value (Gordon growth)",
        f"={scalar('terminal_fcf')}*(1+{scalar('perpetuity_growth')})"
        f"/({scalar('wacc')}-{scalar('perpetuity_growth')})",
    )
    # Measured at FY2029, not FY2030: the shield formula decays E once before
    # its first term, so E x (1 - d) stands in for the FY2030 excess. That step
    # is exact only while the capex drivers stay calibrated to this anchor.
    scalar_row(
        "excess_ppe",
        "Excess PP&E over the re-based base, at FY2029",
        f"={layout.ref(BS, 'ppe', PENULTIMATE_COL)}-{scalar('terminal_ppe_intensity')}"
        f"*{layout.ref(IS, 'revenue', PENULTIMATE_COL)}",
    )
    scalar_row(
        "excess_ppe_decay_factor",
        "Decay factor x = (1 - PP&E depreciation rate) / (1 + WACC)",
        f"=(1-{driver('ppe_depreciation_rate')})/(1+{scalar('wacc')})",
        RATIO_FORMAT,
    )
    scalar_row(
        "excess_ppe_tax_shield",
        "Value at the terminal date of the excess PP&E tax shield",
        f"={driver('tax_rate')}*{driver('ppe_depreciation_rate')}*{scalar('excess_ppe')}"
        f"*{scalar('excess_ppe_decay_factor')}/(1-{scalar('excess_ppe_decay_factor')})",
    )
    scalar_row(
        "terminal_value_exit_multiple",
        "Terminal value (exit multiple)",
        f"={layout.ref(IS, 'ebitda', FINAL_COL)}*{driver('exit_ev_ebitda')}",
    )
    # The caveat, on the sheet rather than only in the docstring.
    note(
        "note_exit_multiple_is_not_a_second_method",
        "READ THIS BEFORE USING THE ROW ABOVE: it is NOT an independent second "
        "method and it must not be taken as corroboration of the Gordon value. "
        "EV/EBITDA = EV/EBIT x (1 - D&A/EBITDA) is an identity, and the exit "
        "multiple on Assumptions IS the peer median EV/EBIT read at this "
        "terminal year's own D&A/EBITDA, so the EBITDA cancels and this row is "
        "exactly the peer median EV/EBIT x terminal EBIT — one peer statistic "
        "(the median of five is J D Wetherspoon alone) applied to the model's "
        "own EBIT. The two rows that follow are the proof. It builds no part of "
        "the enterprise value below.",
    )
    scalar_row(
        "exit_multiple_tv_over_terminal_ebit",
        "Memo: exit-multiple TV / terminal EBIT (equals the peer median EV/EBIT)",
        f"={scalar('terminal_value_exit_multiple')}/{scalar('terminal_ebit')}",
        MULTIPLE_FORMAT,
    )
    scalar_row(
        "peer_median_ev_ebit",
        "Memo: peer median EV/EBIT from Comps (the row above, to 2dp rounding)",
        f"={aref(layout, COMPS, 'ev_ebit', MEDIAN_COL)}",
        MULTIPLE_FORMAT,
        is_link=True,
    )
    scalar_row(
        "gordon_implied_ev_ebitda",
        "Gordon terminal value / terminal EBITDA (the multiple Gordon implies)",
        f"={scalar('terminal_value_gordon')}/{scalar('terminal_ebitda')}",
        MULTIPLE_FORMAT,
    )
    scalar_row(
        "gordon_implied_ev_ebit",
        "Gordon terminal value / terminal EBIT (the like-for-like peer comparison)",
        f"={scalar('terminal_value_gordon')}/{scalar('terminal_ebit')}",
        MULTIPLE_FORMAT,
    )
    note(
        "note_gordon_vs_peers",
        "The comparison to make against the peer set is the EV/EBIT one, not the "
        "EV/EBITDA one. The model deliberately builds a more capital-intensive "
        "Greggs by FY2030, and a higher D&A share mechanically lowers the "
        "coherent EBITDA multiple without saying anything about rating: across "
        "the three scenarios the Gordon terminal value sits 14% to 26% below the "
        "peer median on EV/EBIT against 17% to 50% below on EV/EBITDA. What is "
        "left after that artefact is a real disagreement about terminal "
        "reinvestment intensity, and it is not tuned away.",
    )

    # --- 5. The bridge -----------------------------------------------------
    writer.blank()
    writer.title("Enterprise value and the bridge to equity")
    # An addition chain over the five explicit years rather than SUM(F:J): the
    # rule this workbook follows everywhere is that a range which silently grows
    # to include an inserted row is the error the row registry exists to remove.
    scalar_row(
        "pv_explicit_period",
        "PV of the explicit forecast period",
        total([me("pv_fcf", col) for col in FCST_COLS]),
    )
    # The terminal value and its shield are discounted on the SAME mid-year
    # factor as the final explicit year — 4.5 years, not 5.
    scalar_row(
        "pv_terminal_value",
        "PV of the terminal value (Gordon plus the excess PP&E shield)",
        f"=({scalar('terminal_value_gordon')}+{scalar('excess_ppe_tax_shield')})"
        f"/{me('discount_factor', FINAL_COL)}",
    )
    scalar_row(
        "enterprise_value",
        "Enterprise value",
        f"={scalar('pv_explicit_period')}+{scalar('pv_terminal_value')}",
    )
    scalar_row(
        "terminal_share_of_ev",
        "Terminal value as a share of enterprise value",
        f"={scalar('pv_terminal_value')}/{scalar('enterprise_value')}",
        PERCENT_FORMAT,
    )
    # Both deductions are OPENING (FY2025 actual) balances, because the DCF
    # discounts to the FY2025 year end and EV is therefore a value at that date.
    # Greggs is in a net CASH position excluding leases, so the first line adds
    # value back; the lease liability is much the larger item.
    scalar_row(
        "net_debt",
        "Net debt at FY2025 (borrowings less cash, excluding leases)",
        f"={actual('borrowings')}-{actual('cash')}",
    )
    scalar_row(
        "lease_liabilities",
        "Lease liabilities at FY2025 (deducted as debt, as in the WACC weight)",
        f"={actual('lease_liabilities')}",
        is_link=True,
    )
    scalar_row(
        "equity_value",
        "Equity value",
        f"={scalar('enterprise_value')}-{scalar('net_debt')}-{scalar('lease_liabilities')}",
    )
    scalar_row(
        "share_count",
        "Shares in issue (weighted average diluted, m)",
        f"={layout.ref(HISTORICALS, 'share_count', LAST_ACTUAL_COL)}",
        RATIO_FORMAT,
        is_link=True,
    )
    scalar_row(
        "share_price_pence",
        "Implied share price (p)",
        f"={scalar('equity_value')}/{scalar('share_count')}*{PENCE_PER_POUND}",
        PENCE_FORMAT,
    )
    scalar_row(
        "share_price_vs_traded",
        "Implied share price against the traded price on Comps",
        f"={scalar('share_price_pence')}/{aref(layout, COMPS, 'greggs_share_price', SCALAR_COL)}"
        f"-1",
        PERCENT_FORMAT,
    )
