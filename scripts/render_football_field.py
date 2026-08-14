"""Render the football field to ``docs/football-field.png``.

The picture is drawn from the SHIPPED WORKBOOK's own recalculated values, not
from the Python model. That is the point: this is a picture of what the file
in `dist/` actually says, so it cannot drift from the artefact the way a chart
rebuilt from the model alongside it could. If the workbook is wrong, so is the
image, which is the correct failure mode.

    python3 scripts/render_football_field.py

Reads `dist/greggs_model.xlsx` (run `scripts/generate.py` first) and needs
LibreOffice on PATH to recalculate it, like the tests do.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import openpyxl  # noqa: E402
from matplotlib.patches import FancyBboxPatch  # noqa: E402

from bluebook.recalc import recalc_values  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
WORKBOOK = ROOT / "dist" / "greggs_model.xlsx"
OUTPUT = ROOT / "docs" / "football-field.png"

# The portfolio site's palette, so the image sits in the page rather than on it.
BACKGROUND = "#05060a"
INK = "#e8f1ff"
ACCENT = "#bfe6ff"
DIM = "#6f93b8"
BAR_FACE = "#1b3347"
MONO = "DejaVu Sans Mono"

SHEET = "Football Field"
LOW_COL, HIGH_COL, CENTRAL_COL = "C", "D", "F"


def read_bars() -> list[tuple[str, float, float, float]]:
    """(label, low, high, central) per bar, read off the recalculated file."""
    formulas = openpyxl.load_workbook(WORKBOOK)[SHEET]
    values = recalc_values(WORKBOOK)[SHEET]

    bars = []
    for row in range(1, formulas.max_row + 1):
        label = formulas[f"B{row}"].value
        if not isinstance(label, str) or values.get(f"{LOW_COL}{row}") is None:
            continue
        # The sheet's labels carry their own explanation after an em dash;
        # the chart has axis room for the name only.
        bars.append((
            label.split("—")[0].strip(),
            float(values[f"{LOW_COL}{row}"]),
            float(values[f"{HIGH_COL}{row}"]),
            float(values[f"{CENTRAL_COL}{row}"]),
        ))
    return bars


def render(bars, traded: float) -> None:
    fig, ax = plt.subplots(figsize=(11, 4.4), dpi=200)
    fig.patch.set_facecolor(BACKGROUND)
    ax.set_facecolor(BACKGROUND)

    height = 0.34
    for index, (_, low, high, central) in enumerate(bars):
        y = len(bars) - 1 - index
        # Rounded bars: the span, then the central mark on top of it.
        ax.add_patch(FancyBboxPatch(
            (low, y - height / 2), high - low, height,
            boxstyle=f"round,pad=0,rounding_size={height / 2}",
            linewidth=1.1, facecolor=BAR_FACE, edgecolor=ACCENT, alpha=0.95,
        ))
        ax.plot([central, central], [y - height / 2 - 0.05, y + height / 2 + 0.05],
                color=ACCENT, linewidth=2.4, solid_capstyle="round", zorder=3)
        ax.annotate(f"{central:,.0f}p", (central, y + height / 2 + 0.12),
                    ha="center", va="bottom", color=ACCENT, fontsize=9,
                    fontfamily=MONO, fontweight="bold")
        for value, align, offset in ((low, "right", -28), (high, "left", 28)):
            ax.annotate(f"{value:,.0f}", (value, y), xytext=(offset, 0),
                        textcoords="offset points", ha=align, va="center",
                        color=DIM, fontsize=8.5, fontfamily=MONO)

    ax.axvline(traded, color=INK, linewidth=1.0, linestyle=(0, (4, 4)), alpha=0.5, zorder=1)
    ax.annotate(f"traded  {traded:,.0f}p", (traded, len(bars) - 0.42),
                xytext=(7, 0), textcoords="offset points",
                color=INK, alpha=0.7, fontsize=8.5, fontfamily=MONO)

    ax.set_yticks(range(len(bars)))
    ax.set_yticklabels([label for label, *_ in reversed(bars)],
                       color=INK, fontsize=10, fontfamily=MONO)
    ax.tick_params(axis="x", colors=DIM, labelsize=8.5)
    for label in ax.get_xticklabels():
        label.set_fontfamily(MONO)
    for side, spine in ax.spines.items():
        spine.set_visible(side == "bottom")
        spine.set_color("#1b3347")

    lows = [low for _, low, _, _ in bars]
    highs = [high for _, _, high, _ in bars]
    margin = (max(highs) - min(lows)) * 0.16
    ax.set_xlim(min(lows) - margin, max(highs) + margin)
    ax.set_ylim(-0.75, len(bars) - 0.25)
    ax.set_xlabel("implied share price (pence)", color=DIM, fontsize=9,
                  fontfamily=MONO, labelpad=9)
    ax.set_title("Greggs plc — valuation range by method",
                 color=INK, fontsize=13, fontfamily=MONO, fontweight="bold",
                 loc="left", pad=16)

    fig.tight_layout()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUTPUT, facecolor=BACKGROUND, bbox_inches="tight", pad_inches=0.32)
    plt.close(fig)


def main() -> int:
    if not WORKBOOK.exists():
        sys.exit(f"{WORKBOOK} does not exist — run scripts/generate.py first")
    bars = read_bars()
    if len(bars) != 3:
        sys.exit(f"expected three bars on '{SHEET}', found {len(bars)}: "
                 f"{[label for label, *_ in bars]}")
    # The 52-week bar's central mark IS the traded price; the reference line
    # and that mark must be the same number rather than two sources for it.
    traded = bars[-1][3]
    render(bars, traded)
    for label, low, high, central in bars:
        print(f"{label:24} {low:9,.1f} .. {high:9,.1f}   central {central:9,.1f}")
    print(f"wrote {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
