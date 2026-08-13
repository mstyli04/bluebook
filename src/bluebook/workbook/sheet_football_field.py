"""Football field — the valuation ranges, side by side, as a chart.

The sheet an interviewer looks at first and the only one that answers the
question the workbook exists to answer: what is Greggs worth, and how wide is
the honest error bar? Each bar spans a low and a high from ONE method, with
that method's own central figure marked beside it, and every number on the
sheet is a link — `Football Field` is not in `HARDCODE_ALLOWED`, so nothing
here may restate a figure computed elsewhere.

--------------------------------------------------------------------------
Which methods get a bar, and which deliberately does not
--------------------------------------------------------------------------
Three bars, and the omission matters as much as the inclusions:

* **DCF (Gordon)** — low and high are the extremes of the Sensitivity sheet's
  5x5 implied-price grid, so the bar is WACC +/-100bp against perpetuity
  growth +/-50bp. The central mark is the DCF's own answer, which is the
  grid's centre cell.
* **Trading comps** — the peer minimum to the peer maximum EV/EBITDA applied
  to Greggs, with the peer median as the central mark. The spread is wide
  because the peer set is five names of which not one is a structural match
  for leased-estate food-to-go; the Comps sheet says so in its own notes and
  quantifies the median's sensitivity at about -4.6%.
* **52-week traded range** — the market's own answer, as the reference every
  other bar is read against.

**The exit-multiple terminal value gets no bar.** It is tempting: the model
computes one, and a second DCF bar would look like corroboration. It is not.
The exit multiple is derived as ``peer median EV/EBIT x (1 - terminal
D&A/EBITDA)``, and because ``EV/EBITDA = EV/EBIT x (1 - D&A/EBITDA)`` is an
identity, the resulting terminal value is arithmetically the peer median
EV/EBIT applied to terminal EBIT. It contains one peer statistic and nothing
else. Drawn beside the Gordon bar it would assert that two methods agree when
what actually happened is that one statistic was used twice. The Comps bar
already carries that statistic honestly.

--------------------------------------------------------------------------
How the bars are drawn
--------------------------------------------------------------------------
`openpyxl` has no floating-bar chart type, so the standard construction is
used: a stacked horizontal bar chart of two series, where the first is the
low value drawn with no fill and the second is the span. The invisible first
series pushes the visible second one out to its starting value. The span
column exists on the sheet for that reason and is a formula like every other
cell, not a chart-only artefact.
"""

from __future__ import annotations

from openpyxl.chart import BarChart, Reference
from openpyxl.chart.marker import DataPoint
from openpyxl.chart.shapes import GraphicalProperties

from bluebook.workbook.formulas import aref
from bluebook.workbook.layout import Layout
from bluebook.workbook.sheet import SheetWriter
from bluebook.workbook.styles import PENCE_FORMAT

SHEET = "Football Field"
COMPS = "Comps"
DCF = "DCF"
SENSITIVITY = "Sensitivity"

SCALAR_COL = "C"
# Low, high, span, and the method's own central figure. The span is what the
# chart's visible series reads; the central mark is read by eye against it.
BAR_COLS = ("C", "D", "E", "F")
LOW_COL, HIGH_COL, SPAN_COL, MARK_COL = BAR_COLS

# The five rows of the Sensitivity sheet's implied-price grid, and the columns
# it occupies. Taken as registered keys rather than as a block reference: the
# five rows are written consecutively today, and a MIN over a range that
# assumed so would silently widen if a row were ever inserted between them.
PRICE_GRID_KEYS = tuple(f"price_{index}" for index in range(5))
PRICE_GRID_FIRST_COL = "D"
PRICE_GRID_LAST_COL = "H"

CHART_ANCHOR = "B14"
CHART_TITLE = "Greggs plc — implied value per share (pence)"
CHART_WIDTH = 24.0
CHART_HEIGHT = 9.0


def write_football_field(writer: SheetWriter, layout: Layout) -> None:
    """Write the valuation-range table and the chart drawn from it."""

    def comps(key: str) -> str:
        return aref(layout, COMPS, key, SCALAR_COL)

    def dcf(key: str) -> str:
        return aref(layout, DCF, key, SCALAR_COL)

    def grid_extreme(function: str) -> str:
        """MIN or MAX across all twenty-five cells of the price grid."""
        blocks = ",".join(
            f"'{SENSITIVITY}'!{PRICE_GRID_FIRST_COL}{layout.row_of(SENSITIVITY, key)}"
            f":{PRICE_GRID_LAST_COL}{layout.row_of(SENSITIVITY, key)}"
            for key in PRICE_GRID_KEYS
        )
        return f"={function}({blocks})"

    def bar(key: str, label: str, low: str, high: str, mark: str) -> int:
        """One bar: low, high, the span the chart draws, and the central mark."""
        row = writer.row
        span = f"={HIGH_COL}{row}-{LOW_COL}{row}"
        return writer.formula_row(
            key, label, [low, high, span, mark], PENCE_FORMAT, cols=BAR_COLS
        )

    def note(key: str, text: str) -> None:
        writer.formula_row(key, text, [])

    writer.title("Football field — valuation ranges, pence per share")
    writer.blank()
    writer.year_header(("Low", "High", "Span", "Central"), cols=BAR_COLS)

    first_bar = writer.row
    bar(
        "bar_dcf_gordon",
        "DCF (Gordon) — WACC +/-100bp, perpetuity growth +/-50bp",
        grid_extreme("MIN"),
        grid_extreme("MAX"),
        f"={dcf('share_price_pence')}",
    )
    bar(
        "bar_comps",
        "Trading comps — peer minimum to peer maximum EV/EBITDA",
        f"={comps('comps_implied_price_min')}",
        f"={comps('comps_implied_price_max')}",
        f"={comps('comps_implied_price_median')}",
    )
    last_bar = bar(
        "bar_traded_range",
        "52-week traded range — the market's own answer",
        f"={comps('greggs_52_week_low')}",
        f"={comps('greggs_52_week_high')}",
        f"={comps('greggs_share_price')}",
    )

    writer.blank()
    note(
        "note_no_exit_multiple_bar",
        "There is deliberately NO exit-multiple bar. The exit multiple is "
        "derived as peer median EV/EBIT x (1 - terminal D&A/EBITDA), and since "
        "EV/EBITDA = EV/EBIT x (1 - D&A/EBITDA) is an identity, its terminal "
        "value is arithmetically the peer median EV/EBIT applied to terminal "
        "EBIT. Drawn beside the Gordon bar it would present one peer statistic, "
        "already carried by the comps bar, as a second independent method.",
    )
    note(
        "note_traded_range_goes_stale",
        "The 52-week range and the traded price are market observations from "
        "one provider on one date -- see the observation date on Comps. They "
        "are the only figures in this workbook that are wrong tomorrow rather "
        "than merely out of date at the next reporting cycle. Re-read them "
        "before showing this sheet to anyone.",
    )
    note(
        "note_bar_widths_are_not_confidence",
        "A wider bar is not a less confident method. The comps bar spans the "
        "peer minimum to maximum across five names, none of which is a close "
        "structural match for leased-estate food-to-go; the DCF bar spans a "
        "deliberately chosen +/-100bp of WACC. They are different kinds of "
        "range and should not be compared by width.",
    )

    _add_chart(writer, first_bar, last_bar)


def _add_chart(writer: SheetWriter, first_bar: int, last_bar: int) -> None:
    """Stacked horizontal bars: an invisible low series, then the visible span.

    Written straight onto the worksheet rather than through `SheetWriter`
    because a chart is not a row and registers nothing in the `Layout`. It
    reads only cells the writer has already written and registered, so it
    cannot address a row nobody owns.
    """
    chart = BarChart()
    chart.type = "bar"          # horizontal
    chart.grouping = "stacked"
    chart.overlap = 100         # required, or a stacked bar chart draws side by side
    chart.title = CHART_TITLE
    chart.y_axis.title = "Pence per share"
    chart.x_axis.delete = False
    chart.y_axis.delete = False
    chart.width = CHART_WIDTH
    chart.height = CHART_HEIGHT
    chart.legend = None

    ws = writer.ws
    low = Reference(
        ws, min_col=ws[f"{LOW_COL}1"].column, min_row=first_bar, max_row=last_bar
    )
    span = Reference(
        ws, min_col=ws[f"{SPAN_COL}1"].column, min_row=first_bar, max_row=last_bar
    )
    categories = Reference(ws, min_col=2, min_row=first_bar, max_row=last_bar)

    chart.add_data(low, titles_from_data=False)
    chart.add_data(span, titles_from_data=False)
    chart.set_categories(categories)

    # The pedestal series carries each bar out to its low value and must not be
    # visible. `noFill` on the series, and again on each point, because some
    # readers honour only the point-level setting.
    invisible = GraphicalProperties(noFill=True)
    invisible.line.noFill = True
    pedestal = chart.series[0]
    pedestal.graphicalProperties = invisible
    pedestal.data_points = [
        DataPoint(idx=index, spPr=invisible)
        for index in range(last_bar - first_bar + 1)
    ]

    ws.add_chart(chart, CHART_ANCHOR)
