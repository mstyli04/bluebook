"""The Comps sheet: five UK-listed peers, post-IFRS 16, then Greggs beside them.

One COMPANY per column and one line item per row, which is the transpose of the
way a comps page is usually printed. The reason is the row registry: every other
sheet in this workbook puts a line item on a row and lets `Layout` address it,
and a sheet that put SSP Group on a row and EV/EBITDA in a column could not be
referenced by any of the machinery the rest of the workbook is built on. The
company names therefore occupy row 2 — the slot every other sheet gives its year
header, and for the same purpose: it labels what the columns are.

Columns C:G are the five peers in `comps.PEERS` order, I:K are the peer set's
minimum, median and maximum, and L carries each peer's source. Greggs is NOT a
sixth column: it sits in its own block below, in column C, because almost every
Greggs figure here is a formula off Historicals while every peer figure is a
transcription. Mixing the two in one row would have to give them one font, and
the font is the workbook's only signal for which is which.

--------------------------------------------------------------------------
Why the market caps and EVs are transcribed rather than computed
--------------------------------------------------------------------------
`comps.Peer` stores `market_cap` and `ev` as literals and checks them in
`__post_init__` against price x shares and against market cap + net debt +
minorities, so that the check is a real check rather than a tautology. This
sheet mirrors that exactly: both are blue inputs, and the two check rows below
them reproduce `__post_init__`'s two ties as formulas. The market-cap tie is
not nil to the last decimal — the literals are quoted to three decimals while
price x shares runs to six, so the row shows residuals of a few ten-thousandths
of a million — which is why `comps._TIE_TOLERANCE` is £0.01 and not zero.
Computing the market cap here instead would silently replace each transcribed
figure with a derived one and delete the check.

--------------------------------------------------------------------------
The two Greggs share counts, which are different numbers
--------------------------------------------------------------------------
The market capitalisation here uses `comps.GREGGS_SHARES_OUTSTANDING` (101.96m,
the price provider's shares-outstanding figure), because a market cap has to be
the provider's price times the provider's count. The per-share outputs — the
DCF's implied price and the comps-implied price on this sheet — use
`inputs/greggs.GREGGS_SHARE_COUNT` (102.482895m, the FY2025 weighted average
diluted count, FY2025 AR p.152), because that is the count the filing's own
earnings per share is struck on. They differ by 0.51%, and both are on the sheet
so a reader can see which is used where rather than wondering.

--------------------------------------------------------------------------
What the statistics do and do not include
--------------------------------------------------------------------------
The EV/EBITDA and EV/EBIT statistics run over all five peers, C:G. The P/E
statistics run over D:G, excluding SSP Group in column C: SSP's FY2025
statutory attributable result is a LOSS of £74.4m, so its P/E is not a small
multiple but not a multiple at all, and `comps.multiples()` drops it for the
same reason. It is dropped by naming the column rather than by a conditional,
so the exclusion is visible in the formula bar. SSP's own P/E cell is still
computed and still negative, which is the honest way to show why it is out.

Greggs is outside every statistic range by construction, being in its own block.
"""

from __future__ import annotations

from bluebook.comps import (
    FY2025_NET_IMPAIRMENT_PPE,
    FY2025_NET_IMPAIRMENT_ROU,
    GREGGS_52_WEEK_HIGH,
    GREGGS_52_WEEK_LOW,
    GREGGS_SHARE_PRICE,
    GREGGS_SHARES_OUTSTANDING,
    PEERS,
    PRICE_OBSERVATION_DATE,
)
from bluebook.workbook.formulas import aref, cell_range
from bluebook.workbook.layout import FCST_COLS, HIST_COLS, Layout
from bluebook.workbook.sheet import SheetWriter
from bluebook.workbook.styles import (
    MONEY_FORMAT,
    MULTIPLE_FORMAT,
    PENCE_FORMAT,
    PERCENT_FORMAT,
    RATIO_FORMAT,
    TEXT_FORMAT,
)

SHEET = "Comps"
ASSUMPTIONS = "Assumptions"
HISTORICALS = "Historicals"
DCF = "DCF"

# One column per peer, in `comps.PEERS` order.
PEER_COLS = ("C", "D", "E", "F", "G")
# Minimum, median, maximum of the peer set.
STAT_COLS = ("I", "J", "K")
STAT_NAMES = ("min", "median", "max")
# The median column, named so other sheets reference the statistic rather than
# a letter: the derived exit multiple and the DCF's own memo rows both read it.
MEDIAN_COL = STAT_COLS[STAT_NAMES.index("median")]
# Columns this sheet uses beyond the year grid `build._apply_presentation`
# already sizes, derived from the two tuples above so the widths follow the
# layout rather than a hand-kept second list.
EXTRA_COLS = tuple(
    col for col in PEER_COLS + STAT_COLS if col not in HIST_COLS + FCST_COLS
)

# SSP Group is PEERS[0] and therefore column C, so the P/E statistics start one
# column later. Derived from the peer order rather than written as "D", so
# reordering PEERS cannot leave a loss-making name inside a P/E median.
PE_STAT_FIRST_COL = PEER_COLS[1]

# Single-value column, as on every other sheet in the workbook.
SCALAR_COL = HIST_COLS[0]
SCALAR = (SCALAR_COL,)

# The last reported year, and the source column, as on Historicals.
LAST_ACTUAL_COL = HIST_COLS[-1]
SOURCE_COL = "L"

# (attribute on `comps.Peer`, row label, number format). Transcribed figures
# only — every derived line is a formula row below.
PEER_INPUT_FIELDS = (
    ("share_price_pence", "Share price (pence)", PENCE_FORMAT),
    ("shares", "Shares outstanding (m)", RATIO_FORMAT),
    ("market_cap", "Market capitalisation (£m)", MONEY_FORMAT),
    ("net_debt_incl_leases", "Net debt including lease liabilities (£m)", MONEY_FORMAT),
    ("lease_liabilities", "  of which lease liabilities (£m)", MONEY_FORMAT),
    ("minority_interests", "Minority interests (£m, book value)", MONEY_FORMAT),
    ("ev", "Enterprise value (£m)", MONEY_FORMAT),
    ("ebitda", "EBITDA (£m, post-IFRS 16, underlying)", MONEY_FORMAT),
    ("ebit", "EBIT (£m, post-IFRS 16, underlying)", MONEY_FORMAT),
    ("net_income", "Net income (£m, statutory, attributable)", MONEY_FORMAT),
)


def write_comps(writer: SheetWriter, ref_layout: Layout) -> None:
    """Write the Comps sheet. `writer` needs no year mode: it names its columns."""
    layout = ref_layout

    def peer(key: str, col: str) -> str:
        """A reference to another row of this sheet, same company column."""
        return layout.ref(SHEET, key, col)

    def stat(key: str, which: str) -> str:
        """A reference to one of a row's three peer statistics."""
        return aref(layout, SHEET, key, STAT_COLS[STAT_NAMES.index(which)])

    def scalar(key: str) -> str:
        """A single-value cell on this sheet, absolute."""
        return aref(layout, SHEET, key, SCALAR_COL)

    def actual(key: str) -> str:
        """The last reported year's figure for a line on Historicals."""
        return layout.ref(HISTORICALS, key, LAST_ACTUAL_COL)

    def peer_row(key: str, label: str, build, fmt: str, *, stat_from: str | None = None) -> int:
        """One derived line across the five peers, optionally with its statistics.

        `stat_from` names the first peer column the statistics cover, which is
        how the P/E row drops SSP. The row is read off the writer's cursor
        BEFORE the row is written, because MIN/MEDIAN/MAX have to address cells
        on their own row and no row number is computed here.
        """
        row = writer.row
        values = [build(col) for col in PEER_COLS]
        if stat_from is not None:
            span = cell_range(stat_from, PEER_COLS[-1], row)
            values += [f"=MIN({span})", f"=MEDIAN({span})", f"=MAX({span})"]
        return writer.formula_row(
            key, label, values, fmt, cols=PEER_COLS + STAT_COLS
        )

    def scalar_row(key: str, label: str, formula: str, fmt: str, *, is_link: bool = False) -> int:
        return writer.formula_row(key, label, [formula], fmt, cols=SCALAR, is_link=is_link)

    def scalar_input(key: str, label: str, value, fmt: str) -> int:
        return writer.input_row(key, label, [value], fmt, cols=SCALAR)

    writer.title("Trading comparables — five UK-listed peers, post-IFRS 16, £m")
    writer.year_header(
        [p.name for p in PEERS] + ["Peer min", "Peer median", "Peer max"],
        cols=PEER_COLS + STAT_COLS,
    )

    # --- The peer table: transcriptions first ------------------------------
    for attr, label, fmt in PEER_INPUT_FIELDS:
        writer.input_row(
            attr,
            label,
            [getattr(p, attr) for p in PEERS],
            fmt,
            cols=PEER_COLS,
        )

    # `comps.Peer.__post_init__`'s two ties, as formulas. Not nil to the last
    # decimal: the literals above are quoted to three decimals against share
    # prices carried to four, so `comps._TIE_TOLERANCE` allows £0.01 and these
    # rows show the actual residual instead of asserting a zero that is not there.
    peer_row(
        "market_cap_check",
        "Check: price x shares less market capitalisation (£m, |x| < 0.01)",
        lambda c: f"={peer('share_price_pence', c)}/100*{peer('shares', c)}"
                  f"-{peer('market_cap', c)}",
        MONEY_FORMAT,
    )
    peer_row(
        "ev_check",
        "Check: market cap + net debt + minorities less EV (£m, |x| < 0.01)",
        lambda c: f"={peer('market_cap', c)}+{peer('net_debt_incl_leases', c)}"
                  f"+{peer('minority_interests', c)}-{peer('ev', c)}",
        MONEY_FORMAT,
    )

    # --- The multiples ----------------------------------------------------
    peer_row(
        "da_implied",
        "Implied D&A (£m, EBITDA less EBIT)",
        lambda c: f"={peer('ebitda', c)}-{peer('ebit', c)}",
        MONEY_FORMAT,
    )
    peer_row(
        "da_over_ebitda",
        "D&A / EBITDA (capital intensity)",
        lambda c: f"=({peer('ebitda', c)}-{peer('ebit', c)})/{peer('ebitda', c)}",
        PERCENT_FORMAT,
        stat_from=PEER_COLS[0],
    )
    peer_row(
        "ev_ebitda",
        "EV / EBITDA",
        lambda c: f"={peer('ev', c)}/{peer('ebitda', c)}",
        MULTIPLE_FORMAT,
        stat_from=PEER_COLS[0],
    )
    peer_row(
        "ev_ebit",
        "EV / EBIT",
        lambda c: f"={peer('ev', c)}/{peer('ebit', c)}",
        MULTIPLE_FORMAT,
        stat_from=PEER_COLS[0],
    )
    # SSP's own cell is computed and comes out negative, which is why it is
    # excluded; the statistics start at PE_STAT_FIRST_COL rather than filtering.
    peer_row(
        "pe",
        "P/E (SSP is a statutory loss and is excluded from the statistics)",
        lambda c: f"={peer('market_cap', c)}/{peer('net_income', c)}",
        MULTIPLE_FORMAT,
        stat_from=PE_STAT_FIRST_COL,
    )

    source_row = writer.input_row(
        "peer_source",
        "Source (results announcement, then the price snapshot)",
        [p.source for p in PEERS],
        TEXT_FORMAT,
        cols=PEER_COLS,
    )
    writer.ws[f"{SOURCE_COL}{source_row}"] = (
        "Peer figures were read through a summarising fetcher, NOT line by line "
        "from the source documents, and carry no page references — see comps.py. "
        "Every EBIT above is a printed operating-profit line; three of the five "
        "EBITDAs are constructed."
    )
    scalar_input(
        "price_observation_date",
        "All six share prices were observed at",
        PRICE_OBSERVATION_DATE,
        TEXT_FORMAT,
    )

    # --- Greggs on the same basis -----------------------------------------
    writer.blank()
    writer.title("Greggs plc at the observed market price, on the same basis")
    scalar_input(
        "greggs_share_price",
        "Greggs share price (pence)",
        GREGGS_SHARE_PRICE.value,
        PENCE_FORMAT,
    )
    # The provider's count, used for the market cap only. The DCF and the
    # comps-implied price below use the filing's weighted average diluted count
    # on Historicals — see the module docstring for why both are here.
    scalar_input(
        "greggs_shares_outstanding",
        "Greggs shares outstanding (m, price provider; the filing's diluted count is on Historicals)",
        GREGGS_SHARES_OUTSTANDING.value,
        RATIO_FORMAT,
    )
    scalar_row(
        "greggs_market_cap",
        "Greggs market capitalisation (£m)",
        f"={scalar('greggs_share_price')}/100*{scalar('greggs_shares_outstanding')}",
        MONEY_FORMAT,
    )
    # Lease-inclusive, matching the peers' EVs and `valuation.equity_bridge`.
    scalar_row(
        "greggs_net_debt",
        "Greggs net debt including lease liabilities (£m, FY2025 actual)",
        f"={actual('borrowings')}-{actual('cash')}+{actual('lease_liabilities')}",
        MONEY_FORMAT,
    )
    scalar_row(
        "greggs_ev",
        "Greggs enterprise value (£m)",
        f"={scalar('greggs_market_cap')}+{scalar('greggs_net_debt')}",
        MONEY_FORMAT,
    )
    scalar_row(
        "greggs_ebitda",
        "Greggs EBITDA (£m, FY2025, the basis the model forecasts)",
        f"={actual('ebitda')}",
        MONEY_FORMAT,
        is_link=True,
    )
    scalar_row(
        "greggs_ebit",
        "Greggs EBIT (£m, FY2025, struck AFTER impairment — see below)",
        f"={actual('ebit')}",
        MONEY_FORMAT,
        is_link=True,
    )
    scalar_row(
        "greggs_net_income",
        "Greggs net income (£m, FY2025)",
        f"={actual('net_income')}",
        MONEY_FORMAT,
        is_link=True,
    )
    scalar_row(
        "greggs_ev_ebitda",
        "Greggs EV / EBITDA",
        f"={scalar('greggs_ev')}/{scalar('greggs_ebitda')}",
        MULTIPLE_FORMAT,
    )
    scalar_row(
        "greggs_ev_ebit",
        "Greggs EV / EBIT",
        f"={scalar('greggs_ev')}/{scalar('greggs_ebit')}",
        MULTIPLE_FORMAT,
    )
    scalar_row(
        "greggs_pe",
        "Greggs P/E",
        f"={scalar('greggs_market_cap')}/{scalar('greggs_net_income')}",
        MULTIPLE_FORMAT,
    )
    scalar_row(
        "greggs_ev_ebitda_vs_peer_median",
        "Discount to the peer median on EV/EBITDA (negative = cheaper)",
        f"={scalar('greggs_ev_ebitda')}/{stat('ev_ebitda', 'median')}-1",
        PERCENT_FORMAT,
    )
    scalar_row(
        "greggs_ev_ebit_vs_peer_median",
        "Discount to the peer median on EV/EBIT (NOT like for like — see impairment below)",
        f"={scalar('greggs_ev_ebit')}/{stat('ev_ebit', 'median')}-1",
        PERCENT_FORMAT,
    )

    # --- The impairment asymmetry, made computable ------------------------
    writer.blank()
    writer.title("Impairment asymmetry on EBIT — a known bias, and it flatters the model")
    # inputs/greggs.py folds net impairment into the two depreciation fields, so
    # Greggs' EBIT is struck AFTER impairment while every peer's underlying EBIT
    # is struck BEFORE it. The two amounts exist only in prose in
    # inputs/greggs.py — HistoricalYear has no impairment field — so they are
    # transcribed here exactly as comps.py transcribes them.
    scalar_input(
        "impairment_ppe",
        "FY2025 net impairment of PP&E, inside depreciation (FY2025 AR p.148)",
        FY2025_NET_IMPAIRMENT_PPE,
        MONEY_FORMAT,
    )
    scalar_input(
        "impairment_rou",
        "FY2025 net impairment of ROU assets, inside depreciation (FY2025 AR p.148)",
        FY2025_NET_IMPAIRMENT_ROU,
        MONEY_FORMAT,
    )
    scalar_row(
        "impairment_total",
        "FY2025 net impairment inside D&A (£m)",
        f"={scalar('impairment_ppe')}+{scalar('impairment_rou')}",
        MONEY_FORMAT,
    )
    scalar_row(
        "greggs_ebit_pre_impairment",
        "Greggs EBIT on the peers' basis, before impairment (£m)",
        f"={scalar('greggs_ebit')}+{scalar('impairment_total')}",
        MONEY_FORMAT,
    )
    scalar_row(
        "greggs_ev_ebit_pre_impairment",
        "Peers'-basis EV / EBIT (Greggs, before impairment)",
        f"={scalar('greggs_ev')}/{scalar('greggs_ebit_pre_impairment')}",
        MULTIPLE_FORMAT,
    )
    scalar_row(
        "greggs_ev_ebit_pre_impairment_vs_peer_median",
        "Discount to the peer median on the peers'-basis EV/EBIT (the like-for-like read)",
        f"={scalar('greggs_ev_ebit_pre_impairment')}/{stat('ev_ebit', 'median')}-1",
        PERCENT_FORMAT,
    )

    # --- What the peer set implies for Greggs ------------------------------
    writer.blank()
    writer.title("Comps-implied value, and the traded range it is read against")
    # Lease liabilities are deducted separately from financial net debt so that
    # a lease-inclusive multiple and a lease-inclusive net debt cannot deduct
    # the leases twice — the same split `comps.implied_value_from_comps` makes.
    # The share count is the filing's diluted count on Historicals, not the
    # provider's count used for the market cap above.
    shares = layout.ref(HISTORICALS, "share_count", LAST_ACTUAL_COL)
    for which, label in (
        ("min", "at the peer minimum"),
        ("median", "at the peer median"),
        ("max", "at the peer maximum"),
    ):
        scalar_row(
            f"comps_implied_price_{which}",
            f"Comps-implied share price {label} EV/EBITDA (p)",
            f"=({scalar('greggs_ebitda')}*{stat('ev_ebitda', which)}"
            f"-({actual('borrowings')}-{actual('cash')})-{actual('lease_liabilities')})"
            f"/{shares}*100",
            PENCE_FORMAT,
        )
    # No formula and no filing behind these three: they are market observations
    # from one provider on one date, and they are the only figures in the
    # workbook that are wrong tomorrow rather than merely out of date at the
    # next reporting cycle. Whatever displays them must display the date above.
    scalar_input(
        "greggs_52_week_low",
        "52-week low (pence, market observation, no formula source)",
        GREGGS_52_WEEK_LOW.value,
        PENCE_FORMAT,
    )
    scalar_input(
        "greggs_52_week_high",
        "52-week high (pence, market observation, no formula source)",
        GREGGS_52_WEEK_HIGH.value,
        PENCE_FORMAT,
    )

    # --- The derived exit multiple ----------------------------------------
    writer.blank()
    writer.title("The exit multiple this peer set implies (it SETS the driver)")
    scalar_row(
        "terminal_da_over_ebitda",
        "Terminal D&A / EBITDA, from the DCF's re-based terminal year",
        f"={aref(layout, DCF, 'terminal_da_over_ebitda', SCALAR_COL)}",
        PERCENT_FORMAT,
        is_link=True,
    )
    # exit multiple = peer median EV/EBIT x (1 - terminal D&A/EBITDA). EV/EBIT is
    # the peer statistic and not EV/EBITDA because post-IFRS 16 EV/EBITDA across
    # these five is substantially a reading of capital intensity: it spans 1.92x
    # while D&A/EBITDA spans 17.0%-60.8%, where EV/EBIT spans 1.61x.
    scalar_row(
        "derived_exit_multiple",
        "Derived exit EV/EBITDA (= peer median EV/EBIT x (1 - terminal D&A/EBITDA))",
        f"={stat('ev_ebit', 'median')}*(1-{scalar('terminal_da_over_ebitda')})",
        MULTIPLE_FORMAT,
    )
    scalar_row(
        "shipped_exit_multiple",
        "Exit EV/EBITDA as shipped on Assumptions (the derived figure, 2dp)",
        f"={aref(layout, ASSUMPTIONS, 'exit_ev_ebitda', SCALAR_COL)}",
        MULTIPLE_FORMAT,
        is_link=True,
    )
    scalar_row(
        "exit_multiple_rounding",
        "Rounding carried by the shipped driver (derived less shipped)",
        f"={scalar('derived_exit_multiple')}-{scalar('shipped_exit_multiple')}",
        RATIO_FORMAT,
    )
    # Label-only rows: the note IS the row, as on the Cover sheet.
    for key, note in (
        (
            "note_median_is_one_peer",
            "The median of five observations IS one observation — here J D "
            "Wetherspoon, a majority-freehold pub company. Dropping any of the "
            "three highest names moves the EV/EBIT median about -4.6%, which is "
            "the honest error bar on everything derived from it.",
        ),
        (
            "note_comparability",
            "Not one of the five is a close structural match to leased-estate "
            "food-to-go retail. SSP is the closest and the cheapest; Domino's is "
            "an asset-light franchisor and its 10.1x EV/EBITDA is an upper bound "
            "on franchise economics, not a comparable capital structure.",
        ),
        (
            "note_provenance",
            "PROVENANCE IS NOT SYMMETRIC: Greggs' figures were read line by line "
            "from the filings with page numbers; the peer figures were not, and "
            "have no page references. Internal ties bound transcription error "
            "only — they say nothing about whether the right line was selected.",
        ),
    ):
        writer.formula_row(key, note, [])
