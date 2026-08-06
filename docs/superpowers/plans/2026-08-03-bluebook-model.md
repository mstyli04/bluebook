# Bluebook Model Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate a live-formula Excel valuation model of Greggs plc from Python, and prove its arithmetic correct by recalculating it headlessly and cross-checking against an independent pure-Python reference model.

**Architecture:** Model logic lives twice, deliberately. `reference.py` computes the model in pure Python. `workbook/` writes the same model as live Excel formulas. A test recalculates the generated `.xlsx` through headless LibreOffice and asserts the two agree. Neither side imports the other's concerns; they meet only in the test.

**Tech Stack:** Python 3, openpyxl 3.1.5, pandas 3.0.3, numpy 2.4.4, pytest 9.0.3, LibreOffice 24.2.7 (`soffice`). All already installed — do not install anything; `sudo` on this machine requires a password.

## Global Constraints

- Repo root: `~/bluebook`. Package root: `src/bluebook/`. Tests: `tests/`.
- Forecast horizon: **5 years**. Historicals: **3 years** (FY2023, FY2024, FY2025).
- Statement sheets use column B for labels, **C/D/E for historicals**, **F/G/H/I/J for forecast years**. Row 1 is the sheet title, row 2 the year header.
- Lease treatment is **post-IFRS 16 throughout**: EBITDA excludes rent, right-of-use depreciation sits in D&A, and lease liabilities are included in net debt in the EV→equity bridge. This basis applies identically to the DCF, comps and LBO. No sheet may deviate.
- Colour conventions: **blue** (`FF0000FF`) = hardcoded input, **black** (`FF000000`) = on-sheet formula, **green** (`FF008000`) = link from another sheet.
- Hardcoded numeric constants are permitted **only** on these five sheets, each for a stated reason, and nowhere else: `Assumptions` (the model's inputs), `Historicals` (transcribed reported figures), `Comps` (peer market data with no formula source), `Cover` (dates and identifiers), `Checks` (threshold constants in check formulas). Every calculation sheet — `IS`, `BS`, `CF`, `Schedules`, `DCF`, `Sensitivity`, `LBO`, `Football Field` — must contain formulas only. Task 16's `HARDCODE_ALLOWED` set is the enforcement of this rule and must match this list exactly.
- No historical figure may be entered without a source reference (annual report year + page). Figures are transcribed from filings, never recalled or estimated.
- Every Excel formula string written by `workbook/` must be produced via the `ref()` helper from Task 5 — never by hand-concatenating sheet names and cell addresses.
- Money is in £m unless a line is explicitly labelled otherwise. Share counts in millions. Per-share figures in pence.
- Commit after every task. Use `git -c user.name="Michael Stylianou" -c user.email="michael.stylianou7@gmail.com"` if git identity is unset.

---

### Task 1: Recalculation harness

The whole verification strategy depends on being able to make LibreOffice compute a workbook openpyxl wrote, then read the results back. Build and prove that first.

**Key insight to rely on:** openpyxl writes formula cells with **no cached value**. LibreOffice must therefore compute them on load in order to render the file, and writes the computed results as cached values when it converts. `openpyxl.load_workbook(path, data_only=True)` then reads those cached values.

**Files:**
- Create: `src/bluebook/__init__.py` (empty)
- Create: `src/bluebook/recalc.py`
- Create: `tests/test_recalc.py`
- Create: `pyproject.toml`
- Create: `.gitignore` (already exists from spec commit — verify it covers `__pycache__/`, `.pytest_cache/`, `.~lock.*`)

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `recalc(path: Path) -> Path` — recalculates the workbook at `path`, returns path to the recalculated copy.
  - `recalc_values(path: Path) -> dict[str, dict[str, float | str | bool | None]]` — recalculates and returns `{sheet_name: {cell_address: value}}` for every non-empty cell.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_recalc.py
from pathlib import Path

import openpyxl
import pytest

from bluebook.recalc import recalc_values


@pytest.fixture
def simple_workbook(tmp_path: Path) -> Path:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    ws["A1"] = 2.0
    ws["A2"] = 3.0
    ws["A3"] = "=A1*A2"
    ws["A4"] = "=SUM(A1:A2)"
    path = tmp_path / "simple.xlsx"
    wb.save(path)
    return path


def test_openpyxl_writes_no_cached_value(simple_workbook: Path):
    """Baseline: the generated file has formulas but no computed results."""
    wb = openpyxl.load_workbook(simple_workbook, data_only=True)
    assert wb["Sheet1"]["A3"].value is None


def test_recalc_values_computes_formulas(simple_workbook: Path):
    values = recalc_values(simple_workbook)
    assert values["Sheet1"]["A3"] == pytest.approx(6.0)
    assert values["Sheet1"]["A4"] == pytest.approx(5.0)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/bluebook && python -m pytest tests/test_recalc.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'bluebook.recalc'`

- [ ] **Step 3: Write `pyproject.toml` so the package imports**

```toml
[project]
name = "bluebook"
version = "0.1.0"
requires-python = ">=3.11"

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["tests"]
```

- [ ] **Step 4: Write the implementation**

```python
# src/bluebook/recalc.py
"""Recalculate openpyxl-generated workbooks through headless LibreOffice.

openpyxl writes formulas without cached results, so LibreOffice must evaluate
them on load. Converting the file back to xlsx persists those results, which
openpyxl can then read with data_only=True.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

import openpyxl

SOFFICE = "soffice"
TIMEOUT_SECONDS = 180


class RecalcError(RuntimeError):
    """LibreOffice failed to recalculate the workbook."""


def recalc(path: Path) -> Path:
    """Recalculate `path` and return the path of the recalculated copy.

    The copy lives in a temporary directory that persists for the process
    lifetime; callers that need it long-term should copy it out.
    """
    path = Path(path).resolve()
    outdir = Path(tempfile.mkdtemp(prefix="bluebook-recalc-"))
    # An isolated user profile lets this run alongside a desktop LibreOffice
    # and keeps concurrent test runs from clashing over one profile lock.
    profile = outdir / "profile"
    result = subprocess.run(
        [
            SOFFICE,
            f"-env:UserInstallation=file://{profile}",
            "--headless",
            "--norestore",
            "--convert-to",
            "xlsx",
            "--outdir",
            str(outdir),
            str(path),
        ],
        capture_output=True,
        text=True,
        timeout=TIMEOUT_SECONDS,
    )
    recalculated = outdir / path.name
    if not recalculated.exists():
        raise RecalcError(
            f"LibreOffice produced no output for {path}.\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
    return recalculated


def recalc_values(path: Path) -> dict[str, dict[str, object]]:
    """Recalculate `path` and return {sheet: {cell_address: computed value}}."""
    recalculated = recalc(path)
    wb = openpyxl.load_workbook(recalculated, data_only=True)
    out: dict[str, dict[str, object]] = {}
    for ws in wb.worksheets:
        cells: dict[str, object] = {}
        for row in ws.iter_rows():
            for cell in row:
                if cell.value is not None:
                    cells[cell.coordinate] = cell.value
        out[ws.title] = cells
    wb.close()
    shutil.rmtree(recalculated.parent / "profile", ignore_errors=True)
    return out
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd ~/bluebook && python -m pytest tests/test_recalc.py -v`
Expected: PASS (both tests). First run may take ~20s while LibreOffice builds its profile.

If `test_recalc_values_computes_formulas` returns `None` instead of `6.0`, LibreOffice is not recalculating on load. Before changing approach, try adding `--convert-to 'xlsx:Calc MS Excel 2007 XML'` with the explicit filter name. If that still fails, stop and report — the entire verification strategy needs rethinking and that is a decision for Styli, not a workaround to invent.

- [ ] **Step 6: Commit**

```bash
cd ~/bluebook
git add pyproject.toml src/bluebook/__init__.py src/bluebook/recalc.py tests/test_recalc.py
git commit -m "feat: headless LibreOffice recalculation harness"
```

> **As-built corrections (2026-08-03).** The `recalc.py` listed above shipped with three
> defects that review caught; `src/bluebook/recalc.py` as committed is canonical, not the
> listing above. (1) `recalc_values()` deleted only the `profile` subdirectory, leaking the
> enclosing temp directory on every call — it now removes the whole `mkdtemp()` directory in a
> `finally` block, and `recalc()` cleans up on its error paths too, while still persisting its
> successful output for the caller. (2) `subprocess.run` was unwrapped, so `TimeoutExpired` and
> `FileNotFoundError` escaped as bare exceptions and `returncode` was never inspected — all
> failures now raise `RecalcError`. (3) Tests were happy-path only; the suite is now 9 tests
> covering the error branches, string/bool cell types, multiple worksheets, `recalc()` in
> isolation, and temp-directory cleanup. The return annotation is
> `dict[str, dict[str, float | str | bool | None]]`.
>
> Also recorded for later tasks: `soffice` emits `javaldx` warnings on stderr during normal
> successful conversions. Do not treat stderr output as a failure signal — check `returncode`.

---

### Task 2: Circularity spike

Decides the shape of the debt schedule. Everything downstream waits on the result.

**Files:**
- Create: `tests/test_spike_circularity.py`
- Create: `docs/superpowers/spike-circularity.md`

**Interfaces:**
- Consumes: `recalc_values` from Task 1.
- Produces: a recorded decision — `INTEREST_BASIS = "average"` or `"opening"` — consumed by Task 8.

- [ ] **Step 1: Write the spike test**

This test asserts the *outcome we hope for*. It is allowed to fail; failing is a valid, informative result that selects the fallback design.

```python
# tests/test_spike_circularity.py
"""Spike: does LibreOffice honour iterative calculation from openpyxl?

Models one year of circular interest:
    interest = rate * average(opening debt, closing debt)
    closing debt = opening debt - (cash_before_interest - interest)

With opening=100, rate=10%, cash_before_interest=30, the converged solution is
closing = 100 - 30 + 0.10 * (100 + closing) / 2, i.e. closing ≈ 78.95,
interest ≈ 8.95.
"""

from pathlib import Path

import openpyxl
import pytest

from bluebook.recalc import recalc_values


def test_libreoffice_resolves_circular_reference(tmp_path: Path):
    wb = openpyxl.Workbook()
    wb.calculation.iterate = True
    wb.calculation.iterateCount = 100
    wb.calculation.iterateDelta = 0.0001

    ws = wb.active
    ws.title = "Debt"
    ws["B1"] = 100.0   # opening debt
    ws["B2"] = 0.10    # interest rate
    ws["B3"] = 30.0    # cash before interest
    ws["B4"] = "=B2*AVERAGE(B1,B5)"        # interest (circular)
    ws["B5"] = "=B1-(B3-B4)"               # closing debt (circular)

    path = tmp_path / "circular.xlsx"
    wb.save(path)

    values = recalc_values(path)["Debt"]
    assert values["B5"] == pytest.approx(78.95, abs=0.05)
    assert values["B4"] == pytest.approx(8.95, abs=0.05)
```

- [ ] **Step 2: Run the spike**

Run: `cd ~/bluebook && python -m pytest tests/test_spike_circularity.py -v`

Record which happened:
- **PASS** → LibreOffice converges. Interest basis is `"average"`.
- **FAIL with `Err:522`, `None`, or a wildly wrong number** → no convergence. Interest basis is `"opening"`.

- [ ] **Step 3: Record the decision**

Write `docs/superpowers/spike-circularity.md` containing: the date, the exact command run, the literal observed values of `B4` and `B5`, the chosen `INTEREST_BASIS`, and one sentence of rationale. Do not paraphrase the observed values — paste what the test actually reported.

- [ ] **Step 4: Adjust the test to lock in the finding**

If the spike passed, leave the test as-is; it is now a regression guard.
If it failed, rewrite the assertion to document the real behaviour so the suite stays green, e.g.:

```python
def test_libreoffice_does_not_resolve_circular_references(tmp_path: Path):
    """Recorded limitation: iterative calculation is not honoured.

    See docs/superpowers/spike-circularity.md. The debt schedule therefore
    computes interest on opening balances.
    """
    # ... same workbook construction ...
    values = recalc_values(path)["Debt"]
    assert values["B5"] != pytest.approx(78.95, abs=0.05)
```

- [ ] **Step 5: Run the suite**

Run: `cd ~/bluebook && python -m pytest -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
cd ~/bluebook
git add tests/test_spike_circularity.py docs/superpowers/spike-circularity.md
git commit -m "spike: record LibreOffice iterative calculation behaviour"
```

---

### Task 3: Greggs historical inputs

**This task requires the real annual reports.** Do not proceed from memory or estimate any figure. Fetch the Greggs plc investor-relations annual report PDFs for FY2023, FY2024 and FY2025 (`https://corporate.greggs.co.uk/investors` → annual reports). If they cannot be fetched, stop and ask Styli to supply the PDFs.

The validation tests below are the real deliverable: they catch transcription errors, which are the single most likely defect in the whole project.

**Files:**
- Create: `src/bluebook/inputs/__init__.py` (empty)
- Create: `src/bluebook/inputs/schema.py`
- Create: `src/bluebook/inputs/greggs.py`
- Create: `tests/test_inputs_greggs.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `Sourced` — dataclass with `value: float`, `source: str` (e.g. `"FY2025 AR p.118"`).
  - `HistoricalYear` — dataclass, one per reported year, fields listed below.
  - `GREGGS_HISTORICALS: list[HistoricalYear]` — three entries, oldest first.
  - `GREGGS_SHARE_COUNT: Sourced`, `GREGGS_FYE_CONVENTION: str`.

- [ ] **Step 1: Write the schema**

```python
# src/bluebook/inputs/schema.py
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
    operating_costs: Sourced        # distribution + admin, excluding D&A
    depreciation_ppe: Sourced
    depreciation_rou: Sourced       # right-of-use asset depreciation
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
```

- [ ] **Step 2: Write the failing validation tests**

```python
# tests/test_inputs_greggs.py
import pytest

from bluebook.inputs.greggs import GREGGS_HISTORICALS, GREGGS_SHARE_COUNT
from bluebook.inputs.schema import HistoricalYear


def test_three_historical_years_oldest_first():
    assert len(GREGGS_HISTORICALS) == 3
    labels = [y.label for y in GREGGS_HISTORICALS]
    assert labels == sorted(labels)


def test_every_figure_carries_a_source():
    for year in GREGGS_HISTORICALS:
        for name, field in vars(year).items():
            if name == "label":
                continue
            assert field.source.strip(), f"{year.label}.{name} has no source"


@pytest.mark.parametrize("year", GREGGS_HISTORICALS, ids=lambda y: y.label)
def test_balance_sheet_balances(year: HistoricalYear):
    """Transcription check: assets must equal liabilities plus equity."""
    assets = (
        year.ppe.value
        + year.rou_assets.value
        + year.intangibles.value
        + year.inventories.value
        + year.trade_receivables.value
        + year.cash.value
        + year.other_assets.value
    )
    liabilities_and_equity = (
        year.trade_payables.value
        + year.lease_liabilities.value
        + year.borrowings.value
        + year.other_liabilities.value
        + year.equity.value
    )
    assert assets == pytest.approx(liabilities_and_equity, abs=0.5)


def test_share_count_is_positive():
    assert GREGGS_SHARE_COUNT.value > 0
```

- [ ] **Step 3: Run to verify failure**

Run: `cd ~/bluebook && python -m pytest tests/test_inputs_greggs.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'bluebook.inputs.greggs'`

- [ ] **Step 4: Transcribe the filings**

Open each annual report. For every field in `HistoricalYear`, record the reported figure and the page it came from. Use `other_assets` and `other_liabilities` as genuine balancing categories — the sum of everything on that side of the balance sheet not itemised — rather than as plugs. If the balance test fails by more than £0.5m, the error is a transcription mistake; find it rather than adjusting `other_*` to hide it.

Write `src/bluebook/inputs/greggs.py`:

```python
# src/bluebook/inputs/greggs.py
"""Greggs plc reported financials, transcribed from published annual reports.

Every figure carries the report and page it came from. Figures are £m on the
reported post-IFRS 16 basis. Do not edit a value without re-checking the filing.
"""

from __future__ import annotations

from bluebook.inputs.schema import HistoricalYear, Sourced

GREGGS_FYE_CONVENTION = "..."   # state the exact convention from the filings
GREGGS_SHARE_COUNT = Sourced(0.0, "FY2025 AR p.___")   # millions, weighted average diluted

FY2023 = HistoricalYear(
    label="FY2023",
    revenue=Sourced(0.0, "FY2023 AR p.___"),
    # ... every field, each with its real value and page reference
)

FY2024 = HistoricalYear(label="FY2024", ...)
FY2025 = HistoricalYear(label="FY2025", ...)

GREGGS_HISTORICALS = [FY2023, FY2024, FY2025]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd ~/bluebook && python -m pytest tests/test_inputs_greggs.py -v`
Expected: PASS. A balance failure means a transcription error — fix the figure, not the test.

- [ ] **Step 6: Commit**

```bash
cd ~/bluebook
git add src/bluebook/inputs tests/test_inputs_greggs.py
git commit -m "feat: Greggs FY2023-FY2025 historicals with source references"
```

---

### Task 4: Driver assumptions and scenarios

**Files:**
- Create: `src/bluebook/assumptions.py`
- Create: `tests/test_assumptions.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `Drivers` — frozen dataclass of forecast assumptions (fields below).
  - `SCENARIOS: dict[str, Drivers]` with keys `"Bear"`, `"Base"`, `"Bull"`.
  - `FORECAST_YEARS: list[str]` — five labels, e.g. `["FY2026", ..., "FY2030"]`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_assumptions.py
import pytest

from bluebook.assumptions import FORECAST_YEARS, SCENARIOS


def test_five_forecast_years():
    assert len(FORECAST_YEARS) == 5


def test_three_scenarios():
    assert set(SCENARIOS) == {"Bear", "Base", "Bull"}


def test_scenarios_are_ordered_on_revenue_growth():
    bear, base, bull = SCENARIOS["Bear"], SCENARIOS["Base"], SCENARIOS["Bull"]
    assert bear.revenue_growth[0] < base.revenue_growth[0] < bull.revenue_growth[0]


def test_each_scenario_has_one_rate_per_forecast_year():
    for name, drivers in SCENARIOS.items():
        assert len(drivers.revenue_growth) == len(FORECAST_YEARS), name
        assert len(drivers.gross_margin) == len(FORECAST_YEARS), name


def test_perpetuity_growth_below_wacc_in_every_scenario():
    for name, drivers in SCENARIOS.items():
        assert drivers.perpetuity_growth < drivers.risk_free_rate + 0.02, name


@pytest.mark.parametrize("name", ["Bear", "Base", "Bull"])
def test_rates_are_fractions_not_percentages(name: str):
    drivers = SCENARIOS[name]
    assert 0.0 < drivers.tax_rate < 1.0
    assert all(-0.5 < g < 0.5 for g in drivers.revenue_growth)


# --- Calibration against actuals -------------------------------------------
# These exist because an earlier draft of this plan set opex_pct_revenue to
# 0.50 against a FY2025 actual of ~45.1%, which silently near-halved the
# forecast EBIT margin. Drivers must be anchored to the transcribed
# historicals, and any deliberate divergence must be explicit.

def _last_actual_ratios():
    from bluebook.inputs.greggs import GREGGS_HISTORICALS

    y = GREGGS_HISTORICALS[-1]
    revenue = y.revenue.value
    da = y.depreciation_ppe.value + y.depreciation_rou.value + y.amortisation.value
    ebit = revenue - y.cost_of_sales.value - y.operating_costs.value - da
    return {
        "gross_margin": (revenue - y.cost_of_sales.value) / revenue,
        "opex_pct_revenue": y.operating_costs.value / revenue,
        "da_pct_revenue": da / revenue,
        "ebit_margin": ebit / revenue,
    }


def test_base_gross_margin_anchored_to_last_actual():
    actual = _last_actual_ratios()["gross_margin"]
    assert abs(SCENARIOS["Base"].gross_margin[0] - actual) <= 0.015


def test_base_opex_ratio_anchored_to_last_actual():
    actual = _last_actual_ratios()["opex_pct_revenue"]
    assert abs(SCENARIOS["Base"].opex_pct_revenue[0] - actual) <= 0.015


def test_base_case_year_one_ebit_margin_tracks_last_actual():
    """The base case must not silently re-rate profitability in year one."""
    actual = _last_actual_ratios()
    base = SCENARIOS["Base"]
    implied = base.gross_margin[0] - base.opex_pct_revenue[0] - actual["da_pct_revenue"]
    assert abs(implied - actual["ebit_margin"]) <= 0.015, (
        f"base-case year-1 EBIT margin {implied:.1%} diverges from "
        f"FY2025 actual {actual['ebit_margin']:.1%} by more than 150bp"
    )
```

- [ ] **Step 2: Run to verify failure**

Run: `cd ~/bluebook && python -m pytest tests/test_assumptions.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'bluebook.assumptions'`

- [ ] **Step 3: Implement**

All rates are fractions (`0.05`, not `5`).

**Calibration is mandatory, and the values in the listing below are NOT usable as written.**
They are structural placeholders that demonstrably fail the calibration tests above: the
listed `opex_pct_revenue` of 0.50 sits against a FY2025 actual near 45.1%, which would
near-halve the forecast EBIT margin against an actual of ~8.5% and produce a valuation no
interviewer would accept.

Compute each operating driver from `GREGGS_HISTORICALS` before setting it — gross margin,
opex as a share of revenue, and the depreciation rates as a share of the relevant *opening
balance* (not of revenue, though the resulting D&A should land near the historical ~7.8% of
revenue). Anchor year-one values to the most recent actual, then let them drift across the
forecast only where you can state a reason. Write the actual historical ratio in a comment
beside every driver you set, so a reader can see what it was anchored to.

> **As-built correction (2026-08-04) — terminal capex.** An earlier ruling required capex to
> stay within the historical range and land near 11% of revenue. **That ruling was wrong and has
> been reversed.** Its stated justification — that ending below the historical low "would
> understate terminal value" — has the sign backwards: lower capex raises free cash flow and
> therefore raises terminal value. Worse, all three historical years sit inside an active
> distribution-centre build, so the historical range is an *expansion-phase* range and is not a
> valid bound on a *terminal* assumption. Capex at 11% implies a steady-state PP&E/revenue of
> 61-69% against Greggs' actual 38.7%, and a historical capex/depreciation ratio of ~3.0x.
>
> Measured consequence: terminal unlevered FCF of -£15.5m (Bear), giving a **negative enterprise
> value**; negative implied equity in the Base case; and Gordon-growth versus exit-multiple
> terminal values disagreeing by 8.4x. The model also drew a revolver to £334m against Greggs'
> actual £100m facility, with cash pinned at the minimum in all 15 forecast years.
>
> **Corrected:** terminal capex ~7.0% of revenue, terminal ROU additions ~3.4%. Three independent
> derivations (asset intensity, reinvestment rate = g/ROIC, and re-running the model) converge
> there, and all three symptoms clear simultaneously — ~£16/share and ~£96m drawn, inside the
> real facility. The two tests bounding terminal capex by the historical range encode the
> expansion-phase fallacy and must be replaced, not satisfied.

Market-rate drivers (risk-free rate, equity risk premium, beta, cost of debt) come from
outside the filings; state the basis for each in a comment. Where a driver is deliberately
set away from its historical anchor, say why in the comment — the calibration tests permit
150bp of divergence, and anything wider needs the reason written down.

```python
# src/bluebook/assumptions.py
from __future__ import annotations

from dataclasses import dataclass

FORECAST_YEARS = ["FY2026", "FY2027", "FY2028", "FY2029", "FY2030"]


@dataclass(frozen=True)
class Drivers:
    """Forecast assumptions. All rates are fractions, not percentages."""

    revenue_growth: tuple[float, ...]      # one per forecast year
    gross_margin: tuple[float, ...]        # gross profit / revenue
    opex_pct_revenue: tuple[float, ...]
    capex_pct_revenue: tuple[float, ...]
    rou_additions_pct_revenue: tuple[float, ...]
    inventory_days: float
    receivable_days: float
    payable_days: float
    ppe_depreciation_rate: float           # of opening PP&E
    rou_depreciation_rate: float           # of opening ROU assets
    tax_rate: float

    # WACC build
    risk_free_rate: float
    equity_risk_premium: float
    beta: float
    cost_of_debt: float
    target_debt_weight: float

    # Terminal value
    perpetuity_growth: float
    exit_ev_ebitda: float

    # Debt
    interest_rate_debt: float
    minimum_cash: float
    dividend_payout_ratio: float


BASE = Drivers(
    revenue_growth=(0.06, 0.055, 0.05, 0.045, 0.04),
    gross_margin=(0.62, 0.62, 0.62, 0.62, 0.62),
    opex_pct_revenue=(0.50, 0.50, 0.50, 0.50, 0.50),
    capex_pct_revenue=(0.07, 0.065, 0.06, 0.06, 0.06),
    rou_additions_pct_revenue=(0.04, 0.04, 0.04, 0.04, 0.04),
    inventory_days=25.0,
    receivable_days=10.0,
    payable_days=45.0,
    ppe_depreciation_rate=0.12,
    rou_depreciation_rate=0.15,
    tax_rate=0.25,
    risk_free_rate=0.04,
    equity_risk_premium=0.055,
    beta=0.85,
    cost_of_debt=0.055,
    target_debt_weight=0.20,
    perpetuity_growth=0.02,
    exit_ev_ebitda=8.0,
    interest_rate_debt=0.055,
    minimum_cash=30.0,
    dividend_payout_ratio=0.45,
)


def _shift(base: Drivers, *, growth_delta: float, margin_delta: float) -> Drivers:
    """Derive a scenario by shifting growth and margin off the base case."""
    from dataclasses import replace

    return replace(
        base,
        revenue_growth=tuple(g + growth_delta for g in base.revenue_growth),
        gross_margin=tuple(m + margin_delta for m in base.gross_margin),
    )


SCENARIOS = {
    "Bear": _shift(BASE, growth_delta=-0.03, margin_delta=-0.02),
    "Base": BASE,
    "Bull": _shift(BASE, growth_delta=0.025, margin_delta=0.015),
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/bluebook && python -m pytest tests/test_assumptions.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd ~/bluebook
git add src/bluebook/assumptions.py tests/test_assumptions.py
git commit -m "feat: forecast drivers and bull/base/bear scenarios"
```

---

### Task 5: Layout registry and the `ref()` helper

This is the abstraction that keeps every formula in the project honest. Sheet writers register which row a line item occupies; formulas are then built from line-item names, never from literal cell addresses.

**Files:**
- Create: `src/bluebook/workbook/__init__.py` (empty)
- Create: `src/bluebook/workbook/layout.py`
- Create: `tests/test_layout.py`

**Interfaces:**
- Consumes: `FORECAST_YEARS` from Task 4.
- Produces:
  - `Layout` — class with `register(sheet: str, key: str, row: int)`, `row_of(sheet, key) -> int`, `ref(sheet, key, col: str) -> str`, `col_for_year(index: int, historical: bool) -> str`.
  - `HIST_COLS = ("C", "D", "E")`, `FCST_COLS = ("F", "G", "H", "I", "J")`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_layout.py
import pytest

from bluebook.workbook.layout import FCST_COLS, HIST_COLS, Layout


def test_ref_builds_a_qualified_reference():
    layout = Layout()
    layout.register("IS", "revenue", 5)
    assert layout.ref("IS", "revenue", "F") == "'IS'!F5"


def test_column_helpers():
    assert HIST_COLS == ("C", "D", "E")
    assert FCST_COLS == ("F", "G", "H", "I", "J")
    layout = Layout()
    assert layout.col_for_year(0, historical=True) == "C"
    assert layout.col_for_year(2, historical=False) == "H"


def test_duplicate_registration_is_rejected():
    layout = Layout()
    layout.register("IS", "revenue", 5)
    with pytest.raises(ValueError, match="already registered"):
        layout.register("IS", "revenue", 9)


def test_unknown_key_raises_with_a_useful_message():
    layout = Layout()
    layout.register("IS", "revenue", 5)
    with pytest.raises(KeyError, match="gross_profit"):
        layout.row_of("IS", "gross_profit")


def test_two_rows_may_not_share_one_position_on_a_sheet():
    layout = Layout()
    layout.register("IS", "revenue", 5)
    with pytest.raises(ValueError, match="row 5"):
        layout.register("IS", "cost_of_sales", 5)
```

- [ ] **Step 2: Run to verify failure**

Run: `cd ~/bluebook && python -m pytest tests/test_layout.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'bluebook.workbook.layout'`

- [ ] **Step 3: Implement**

```python
# src/bluebook/workbook/layout.py
"""Maps line-item names to workbook rows so formulas never hardcode addresses."""

from __future__ import annotations

HIST_COLS = ("C", "D", "E")
FCST_COLS = ("F", "G", "H", "I", "J")


class Layout:
    def __init__(self) -> None:
        self._rows: dict[tuple[str, str], int] = {}

    def register(self, sheet: str, key: str, row: int) -> None:
        if (sheet, key) in self._rows:
            raise ValueError(f"{sheet}.{key} already registered")
        taken = {r: k for (s, k), r in self._rows.items() if s == sheet}
        if row in taken:
            raise ValueError(f"{sheet} row {row} already holds '{taken[row]}'")
        self._rows[(sheet, key)] = row

    def row_of(self, sheet: str, key: str) -> int:
        try:
            return self._rows[(sheet, key)]
        except KeyError:
            raise KeyError(f"{sheet!r} has no line item {key!r}") from None

    def ref(self, sheet: str, key: str, col: str) -> str:
        return f"'{sheet}'!{col}{self.row_of(sheet, key)}"

    @staticmethod
    def col_for_year(index: int, *, historical: bool) -> str:
        cols = HIST_COLS if historical else FCST_COLS
        return cols[index]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/bluebook && python -m pytest tests/test_layout.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd ~/bluebook
git add src/bluebook/workbook tests/test_layout.py
git commit -m "feat: layout registry and ref() formula helper"
```

---

### Task 6: Supporting schedules in the reference model

Working capital, PP&E/D&A and leases. Debt is deliberately excluded — it depends on the spike result and gets its own task.

**Files:**
- Create: `src/bluebook/schedules/__init__.py` (empty)
- Create: `src/bluebook/schedules/working_capital.py`
- Create: `src/bluebook/schedules/fixed_assets.py`
- Create: `src/bluebook/schedules/leases.py`
- Create: `tests/test_schedules.py`

**Interfaces:**
- Consumes: `Drivers` (Task 4), `HistoricalYear` (Task 3).
- Produces:
  - `working_capital(revenue: list[float], cost_of_sales: list[float], drivers: Drivers) -> WorkingCapital` with fields `inventories`, `receivables`, `payables`, `net_working_capital`, `change_in_nwc` (each `list[float]`, one per forecast year).
  - `fixed_assets(opening_ppe: float, revenue: list[float], drivers: Drivers) -> FixedAssets` with `capex`, `depreciation`, `closing_ppe`.
  - `leases(opening_rou: float, opening_liability: float, revenue: list[float], drivers: Drivers) -> Leases` with `additions`, `depreciation`, `closing_rou`, `interest`, `principal_paid`, `closing_liability`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_schedules.py
import pytest

from bluebook.assumptions import SCENARIOS
from bluebook.schedules.fixed_assets import fixed_assets
from bluebook.schedules.leases import leases
from bluebook.schedules.working_capital import working_capital

BASE = SCENARIOS["Base"]
REVENUE = [2000.0, 2100.0, 2200.0, 2300.0, 2400.0]
COGS = [760.0, 798.0, 836.0, 874.0, 912.0]


def test_working_capital_uses_day_counts():
    wc = working_capital(REVENUE, COGS, BASE)
    assert wc.inventories[0] == pytest.approx(COGS[0] * BASE.inventory_days / 365)
    assert wc.receivables[0] == pytest.approx(REVENUE[0] * BASE.receivable_days / 365)
    assert wc.payables[0] == pytest.approx(COGS[0] * BASE.payable_days / 365)


def test_net_working_capital_is_current_assets_less_payables():
    wc = working_capital(REVENUE, COGS, BASE)
    assert wc.net_working_capital[0] == pytest.approx(
        wc.inventories[0] + wc.receivables[0] - wc.payables[0]
    )


def test_change_in_nwc_first_year_measures_against_opening():
    wc = working_capital(REVENUE, COGS, BASE, opening_nwc=50.0)
    assert wc.change_in_nwc[0] == pytest.approx(wc.net_working_capital[0] - 50.0)
    assert wc.change_in_nwc[1] == pytest.approx(
        wc.net_working_capital[1] - wc.net_working_capital[0]
    )


def test_ppe_rolls_forward():
    fa = fixed_assets(opening_ppe=1000.0, revenue=REVENUE, drivers=BASE)
    assert fa.capex[0] == pytest.approx(REVENUE[0] * BASE.capex_pct_revenue[0])
    assert fa.depreciation[0] == pytest.approx(1000.0 * BASE.ppe_depreciation_rate)
    assert fa.closing_ppe[0] == pytest.approx(1000.0 + fa.capex[0] - fa.depreciation[0])
    assert fa.depreciation[1] == pytest.approx(fa.closing_ppe[0] * BASE.ppe_depreciation_rate)


def test_lease_liability_rolls_forward_on_additions_and_principal():
    lz = leases(opening_rou=800.0, opening_liability=850.0, revenue=REVENUE, drivers=BASE)
    assert lz.closing_rou[0] == pytest.approx(800.0 + lz.additions[0] - lz.depreciation[0])
    # IFRS 16: accrued interest and interest PAID cancel each year (Greggs pays
    # lease interest in cash separately from principal), so interest must NOT
    # capitalise into the balance. Verified 2026-08-04: including it drifts the
    # ROU-vs-liability gap to -24% by FY2030 against a stable historical -7/-8%.
    assert lz.closing_liability[0] == pytest.approx(
        850.0 + lz.additions[0] - lz.principal_paid[0]
    )


def test_rou_asset_and_liability_stay_within_sight_of_each_other():
    """Sanity guard: a runaway gap means the roll-forward is wrong."""
    lz = leases(opening_rou=800.0, opening_liability=850.0, revenue=REVENUE, drivers=BASE)
    for rou, liability in zip(lz.closing_rou, lz.closing_liability):
        assert abs(rou - liability) < 0.5 * max(rou, liability)
```

- [ ] **Step 2: Run to verify failure**

Run: `cd ~/bluebook && python -m pytest tests/test_schedules.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'bluebook.schedules'`

- [ ] **Step 3: Implement the three modules**

Each is a small pure function returning a frozen dataclass. Sketch for one; follow the same shape for the others.

```python
# src/bluebook/schedules/working_capital.py
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
    opening_nwc: float = 0.0,
) -> WorkingCapital:
    inventories = [c * drivers.inventory_days / DAYS_IN_YEAR for c in cost_of_sales]
    receivables = [r * drivers.receivable_days / DAYS_IN_YEAR for r in revenue]
    payables = [c * drivers.payable_days / DAYS_IN_YEAR for c in cost_of_sales]
    nwc = [i + r - p for i, r, p in zip(inventories, receivables, payables)]
    prior = [opening_nwc, *nwc[:-1]]
    change = [n - p for n, p in zip(nwc, prior)]
    return WorkingCapital(inventories, receivables, payables, nwc, change)
```

Interest on lease liabilities uses `drivers.cost_of_debt`. Lease principal paid is set so the liability amortises over an implied average lease term — derive it as `opening_liability / implied_term_years + additions * 0.1`; state the implied term as a named constant with a comment explaining it came from the lease maturity table in the filings.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/bluebook && python -m pytest tests/test_schedules.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd ~/bluebook
git add src/bluebook/schedules tests/test_schedules.py
git commit -m "feat: working capital, fixed asset and lease schedules"
```

---

### Task 7: Debt schedule

Shape depends on Task 2's recorded result. Read `docs/superpowers/spike-circularity.md` before starting.

**Files:**
- Create: `src/bluebook/schedules/debt.py`
- Create: `tests/test_debt_schedule.py`

**Interfaces:**
- Consumes: `Drivers` (Task 4), the spike decision (Task 2).
- Produces: `debt_schedule(opening_debt, opening_cash, cash_generated: list[float], drivers, basis: str) -> DebtSchedule` with `opening`, `interest`, `repayment`, `revolver_draw`, `closing`, `cash_balance`.
- `INTEREST_BASIS: str` module constant, set to the spike's finding.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_debt_schedule.py
import pytest

from bluebook.assumptions import SCENARIOS
from bluebook.schedules.debt import INTEREST_BASIS, debt_schedule

BASE = SCENARIOS["Base"]
CASH_GENERATED = [120.0, 130.0, 140.0, 150.0, 160.0]


def test_interest_basis_is_recorded():
    assert INTEREST_BASIS in {"average", "opening"}


def test_debt_amortises_when_cash_is_generated():
    ds = debt_schedule(
        opening_debt=200.0, opening_cash=50.0,
        cash_generated=CASH_GENERATED, drivers=BASE, basis=INTEREST_BASIS,
    )
    assert ds.closing[0] < 200.0
    assert ds.closing == sorted(ds.closing, reverse=True)


def test_debt_never_goes_negative():
    ds = debt_schedule(
        opening_debt=50.0, opening_cash=50.0,
        cash_generated=CASH_GENERATED, drivers=BASE, basis=INTEREST_BASIS,
    )
    assert all(c >= 0.0 for c in ds.closing)


def test_revolver_draws_when_cash_would_fall_below_minimum():
    ds = debt_schedule(
        opening_debt=0.0, opening_cash=BASE.minimum_cash,
        cash_generated=[-100.0] * 5, drivers=BASE, basis=INTEREST_BASIS,
    )
    assert ds.revolver_draw[0] > 0.0
    assert all(c >= BASE.minimum_cash - 0.01 for c in ds.cash_balance)


def test_opening_balance_chains_from_prior_closing():
    ds = debt_schedule(
        opening_debt=200.0, opening_cash=50.0,
        cash_generated=CASH_GENERATED, drivers=BASE, basis=INTEREST_BASIS,
    )
    assert ds.opening[1] == pytest.approx(ds.closing[0])


def test_average_basis_charges_less_interest_than_opening_when_debt_falls():
    """Only meaningful if the spike allowed the average basis."""
    kwargs = dict(opening_debt=200.0, opening_cash=50.0,
                  cash_generated=CASH_GENERATED, drivers=BASE)
    on_opening = debt_schedule(**kwargs, basis="opening")
    on_average = debt_schedule(**kwargs, basis="average")
    assert on_average.interest[0] < on_opening.interest[0]
```

- [ ] **Step 2: Run to verify failure**

Run: `cd ~/bluebook && python -m pytest tests/test_debt_schedule.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement**

Support both bases regardless of the spike result — the Python side is cheap and the comparison test above stays meaningful. `INTEREST_BASIS` records which one the *workbook* will use. On the `"average"` basis, solve each year by fixed-point iteration (seed closing = opening, iterate 50 times or until the change is below 1e-9); this mirrors what Excel's iterative calculation does.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/bluebook && python -m pytest tests/test_debt_schedule.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd ~/bluebook
git add src/bluebook/schedules/debt.py tests/test_debt_schedule.py
git commit -m "feat: debt schedule with revolver and configurable interest basis"
```

---

### Task 8: Linked three-statement reference model

The centrepiece. Produces the forecast income statement, balance sheet and cash flow statement, wired together with no plug.

**Files:**
- Create: `src/bluebook/reference.py`
- Create: `tests/test_reference.py`

**Interfaces:**
- Consumes: everything from Tasks 3, 4, 6, 7.
- Produces: `build_model(historicals: list[HistoricalYear], drivers: Drivers) -> Model`, where `Model` exposes `income_statement`, `balance_sheet`, `cash_flow` (each a `dict[str, list[float]]` keyed by line-item name, five entries per line) plus `ebitda`, `ebit`, `net_income`, `da_total`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_reference.py
import pytest

from bluebook.assumptions import SCENARIOS
from bluebook.inputs.greggs import GREGGS_HISTORICALS
from bluebook.reference import build_model

SCENARIO_NAMES = ["Bear", "Base", "Bull"]


@pytest.fixture
def model():
    return build_model(GREGGS_HISTORICALS, SCENARIOS["Base"])


@pytest.mark.parametrize("name", SCENARIO_NAMES)
def test_balance_sheet_balances_every_forecast_year(name: str):
    m = build_model(GREGGS_HISTORICALS, SCENARIOS[name])
    for i in range(5):
        assets = m.balance_sheet["total_assets"][i]
        claims = m.balance_sheet["total_liabilities_and_equity"][i]
        assert assets == pytest.approx(claims, abs=0.01), f"{name} year {i}"


@pytest.mark.parametrize("name", SCENARIO_NAMES)
def test_cash_flow_ties_to_balance_sheet_cash(name: str):
    m = build_model(GREGGS_HISTORICALS, SCENARIOS[name])
    for i in range(5):
        closing = m.cash_flow["closing_cash"][i]
        assert closing == pytest.approx(m.balance_sheet["cash"][i], abs=0.01)


def test_ebitda_excludes_all_depreciation_and_amortisation(model):
    for i in range(5):
        assert model.ebitda[i] == pytest.approx(
            model.ebit[i] + model.da_total[i], abs=0.01
        )


def test_retained_earnings_move_by_net_income_less_dividends(model):
    for i in range(1, 5):
        movement = (
            model.balance_sheet["equity"][i] - model.balance_sheet["equity"][i - 1]
        )
        expected = model.net_income[i] - model.cash_flow["dividends_paid"][i]
        assert movement == pytest.approx(expected, abs=0.01)


def test_bull_case_produces_higher_revenue_than_bear():
    bull = build_model(GREGGS_HISTORICALS, SCENARIOS["Bull"])
    bear = build_model(GREGGS_HISTORICALS, SCENARIOS["Bear"])
    assert bull.income_statement["revenue"][-1] > bear.income_statement["revenue"][-1]


def test_first_forecast_year_grows_off_the_last_historical(model):
    last_actual = GREGGS_HISTORICALS[-1].revenue.value
    expected = last_actual * (1 + SCENARIOS["Base"].revenue_growth[0])
    assert model.income_statement["revenue"][0] == pytest.approx(expected, abs=0.01)


def test_no_line_item_is_silently_missing(model):
    for statement in (model.income_statement, model.balance_sheet, model.cash_flow):
        for key, series in statement.items():
            assert len(series) == 5, key
            assert all(v is not None for v in series), key
```

- [ ] **Step 2: Run to verify failure**

Run: `cd ~/bluebook && python -m pytest tests/test_reference.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'bluebook.reference'`

- [ ] **Step 3: Implement**

Order of computation, which must not be rearranged: revenue → gross profit → opex → EBITDA → schedules (fixed assets, leases, working capital) → D&A → EBIT → cash generated before financing → debt schedule → interest → profit before tax → tax → net income → dividends → equity roll-forward → balance sheet → cash flow.

The balance sheet must **balance without a plug**. If it does not, the error is in the cash flow linkage — most often a schedule movement that reaches the balance sheet but not the cash flow, or vice versa. Do not add a balancing item.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/bluebook && python -m pytest tests/test_reference.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd ~/bluebook
git add src/bluebook/reference.py tests/test_reference.py
git commit -m "feat: linked three-statement reference model"
```

---

### Task 9: Valuation — WACC, FCF, terminal value, EV bridge

**Files:**
- Create: `src/bluebook/valuation.py`
- Create: `tests/test_valuation.py`

**Interfaces:**
- Consumes: `Model` (Task 8), `Drivers` (Task 4).
- Produces:
  - `wacc(drivers: Drivers) -> float`
  - `unlevered_fcf(model, drivers) -> list[float]`
  - `terminal_value_gordon(final_fcf, wacc_rate, g) -> float`
  - `terminal_value_exit_multiple(final_ebitda, multiple) -> float`
  - `enterprise_value(fcf, tv, wacc_rate) -> float`
  - `equity_bridge(ev, net_debt, lease_liabilities) -> float`
  - `implied_share_price(equity_value, shares) -> float` (returns pence)

**Unlevered FCF definition — use exactly this, post-IFRS 16:**
`FCF = EBIT × (1 − tax rate) + D&A (including ROU depreciation) − capex − new ROU additions − change in NWC`

New ROU additions are deducted because lease liabilities are treated as debt in the bridge; funding the leased asset is therefore an investing outflow. This keeps the DCF consistent with the bridge.

**Terminal-year construction — MANDATORY, added 2026-08-04 after Task 8's review.**

Do NOT strike the terminal value off the raw FY2030 forecast year. Analysis of the completed model found two errors of opposite sign, neither visible unless both are examined together:

1. **FY2030 is not a steady state.** PP&E/revenue is 46.9% / 46.3% / 45.9% against steady-state levels of 38.72% / 38.70% / 38.74%. The excess decays at the depreciation rate (14.23%/yr) and does not come within 1pp until FY2041. FY2030 D&A is therefore £32.3m above a steady-state-consistent year (Base). The FCF effect is **only the tax shield** — EBIT falls by the excess and D&A adds it back — so unlevered FCF is flattered by `excess × tax rate`, about +£8.1m Base (+6.8%). Capitalising that decaying item as a perpetuity overstates terminal value by ~£121m, ~£0.82/share.
2. **Larger and opposite: terminal capex and ROU ratios are derived at the drivers' terminal growth of 4.5%, but the terminal value grows at 2%.** At g = 2% the sustaining total capex is 6.575%, not 7.41%, and sustaining ROU additions 3.69%, not 4.06%. A coherent 2%-growth terminal year has FCF of £149.3m against the modelled £126.4m — the FY2030 strike **understates** by £22.9m (−15.3%), worth about −£2.77/share.

**Required construction.** Pick ONE terminal growth rate `g*` and use it in both the terminal year and the Gordon formula. Then build the terminal year explicitly:

```
capex          = p_ppe_anchor * (g* + d_ppe) / (1 + g*) / HIST_PPE_CAPEX_SHARE
rou_additions  = p_rou_anchor * (g* + d_rou) / (1 + g*)
D&A            = the steady-state charges those intensities imply
change_in_NWC  = (NWC / revenue) * g* / (1 + g*)
```

where `p_ppe_anchor` and `p_rou_anchor` are the FY2025 actual asset intensities (38.68% and 19.20%), and every input is derived from `GREGGS_HISTORICALS` — no literals.

The FY2029 excess PP&E is real and worth something. If it is to be valued, add it back **explicitly** as the present value of decaying tax shields, `tc × d × E × x / (1 − x)` where `x = (1 − d) / (1 + WACC)` — about £34m Base — not by leaving it inside a perpetuity. The £8.1m shield remains a legitimate FY2030 explicit-period cash flow; only the terminal value needs re-basing.

Do not extend the forecast horizon to reach steady state — that would need 11 to 17 years of driver paths nobody has justified. Do not merely disclose the distortion; at £0.8 to £2.8 per share against a ~£12 price it is too large to wave through.

**`exit_ev_ebitda` is currently 10.0 and is probably wrong** against post-IFRS 16 EBITDA, which is structurally higher because rent is added back, so the multiple should be structurally lower. Gordon and exit-multiple terminal values currently disagree by ~2.0×, with Gordon implying a 5.0× exit multiple. Do not re-guess it here: Task 10 builds the comps sheet, which gives a market-based multiple to calibrate against. Flag the disagreement in your report and leave the reconciliation to Task 10.

**Also tighten `test_perpetuity_growth_below_wacc_in_every_scenario`.** It currently checks `g < risk_free_rate + 2%` as a proxy. Once `wacc()` exists, assert against the real computed WACC, which is what the test's name has always promised.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_valuation.py
import pytest

from bluebook.assumptions import SCENARIOS
from bluebook.inputs.greggs import GREGGS_HISTORICALS
from bluebook.reference import build_model
from bluebook.valuation import (
    enterprise_value, equity_bridge, implied_share_price,
    terminal_value_exit_multiple, terminal_value_gordon, unlevered_fcf, wacc,
)

BASE = SCENARIOS["Base"]


def test_wacc_is_between_cost_of_debt_and_cost_of_equity():
    rate = wacc(BASE)
    cost_of_equity = BASE.risk_free_rate + BASE.beta * BASE.equity_risk_premium
    after_tax_debt = BASE.cost_of_debt * (1 - BASE.tax_rate)
    assert after_tax_debt < rate < cost_of_equity


def test_gordon_growth_requires_g_below_wacc():
    with pytest.raises(ValueError, match="perpetuity growth"):
        terminal_value_gordon(final_fcf=100.0, wacc_rate=0.05, g=0.06)


def test_gordon_growth_formula():
    assert terminal_value_gordon(100.0, 0.08, 0.02) == pytest.approx(100 * 1.02 / 0.06)


def test_exit_multiple_formula():
    assert terminal_value_exit_multiple(200.0, 8.0) == pytest.approx(1600.0)


def test_enterprise_value_discounts_mid_year_consistently():
    ev = enterprise_value(fcf=[100.0] * 5, tv=1000.0, wacc_rate=0.10)
    assert 0 < ev < sum([100.0] * 5) + 1000.0


def test_equity_bridge_subtracts_leases_as_debt():
    """Post-IFRS 16: lease liabilities reduce equity value."""
    with_leases = equity_bridge(ev=1000.0, net_debt=100.0, lease_liabilities=200.0)
    without = equity_bridge(ev=1000.0, net_debt=100.0, lease_liabilities=0.0)
    assert with_leases == pytest.approx(700.0)
    assert without - with_leases == pytest.approx(200.0)


def test_implied_share_price_returns_pence():
    # £700m equity over 100m shares = £7.00 = 700p
    assert implied_share_price(700.0, 100.0) == pytest.approx(700.0)


def test_terminal_value_is_not_an_implausible_share_of_ev():
    model = build_model(GREGGS_HISTORICALS, BASE)
    fcf = unlevered_fcf(model, BASE)
    rate = wacc(BASE)
    tv = terminal_value_gordon(fcf[-1], rate, BASE.perpetuity_growth)
    ev = enterprise_value(fcf, tv, rate)
    discounted_tv = tv / (1 + rate) ** 5
    assert 0.4 < discounted_tv / ev < 0.9


def test_bull_case_values_higher_than_bear():
    prices = {}
    for name in ("Bear", "Bull"):
        drivers = SCENARIOS[name]
        model = build_model(GREGGS_HISTORICALS, drivers)
        fcf = unlevered_fcf(model, drivers)
        rate = wacc(drivers)
        tv = terminal_value_gordon(fcf[-1], rate, drivers.perpetuity_growth)
        prices[name] = enterprise_value(fcf, tv, rate)
    assert prices["Bull"] > prices["Bear"]
```

- [ ] **Step 2: Run to verify failure**

Run: `cd ~/bluebook && python -m pytest tests/test_valuation.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement**

Discount at mid-year convention (`(1 + wacc) ** (t - 0.5)` for year `t` starting at 1) and apply the same convention to the terminal value's discount factor. `terminal_value_gordon` raises `ValueError("perpetuity growth must be below WACC")` when `g >= wacc_rate`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/bluebook && python -m pytest tests/test_valuation.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd ~/bluebook
git add src/bluebook/valuation.py tests/test_valuation.py
git commit -m "feat: WACC, unlevered FCF, terminal value and equity bridge"
```

---

### Task 10: Comps and LBO

**Files:**
- Create: `src/bluebook/comps.py`
- Create: `src/bluebook/lbo.py`
- Create: `tests/test_comps.py`
- Create: `tests/test_lbo.py`

**Interfaces:**
- Produces:
  - `Peer` — dataclass: `name`, `ev`, `ebitda`, `net_income`, `market_cap`, `source`.
  - `PEERS: list[Peer]` — five UK-listed food/hospitality names, each figure sourced.
  - `multiples(peers) -> dict[str, dict[str, float]]` returning `{"ev_ebitda": {"min", "median", "max"}, "pe": {...}}`
  - `implied_value_from_comps(ebitda, median_multiple, net_debt, leases, shares) -> float` (pence)
  - `lbo_returns(entry_ev, entry_debt, exit_ev, exit_debt, years) -> LboReturns` with `irr`, `money_multiple`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_comps.py
import pytest

from bluebook.comps import PEERS, implied_value_from_comps, multiples


def test_five_peers_each_sourced():
    assert len(PEERS) == 5
    assert all(p.source.strip() for p in PEERS)


def test_multiples_are_ordered():
    m = multiples(PEERS)
    assert m["ev_ebitda"]["min"] <= m["ev_ebitda"]["median"] <= m["ev_ebitda"]["max"]


def test_implied_value_subtracts_leases_on_the_post_ifrs16_basis():
    price = implied_value_from_comps(
        ebitda=250.0, median_multiple=8.0, net_debt=50.0, leases=200.0, shares=100.0
    )
    # (250*8 - 50 - 200) / 100 = £17.50 = 1750p
    assert price == pytest.approx(1750.0)
```

```python
# tests/test_lbo.py
import pytest

from bluebook.lbo import lbo_returns


def test_money_multiple_is_exit_equity_over_entry_equity():
    r = lbo_returns(entry_ev=1000.0, entry_debt=600.0, exit_ev=1400.0,
                    exit_debt=300.0, years=5)
    assert r.money_multiple == pytest.approx((1400 - 300) / (1000 - 600))


def test_irr_is_consistent_with_the_money_multiple():
    r = lbo_returns(entry_ev=1000.0, entry_debt=600.0, exit_ev=1400.0,
                    exit_debt=300.0, years=5)
    assert (1 + r.irr) ** 5 == pytest.approx(r.money_multiple)


def test_negative_exit_equity_is_rejected():
    with pytest.raises(ValueError, match="exit equity"):
        lbo_returns(entry_ev=1000.0, entry_debt=600.0, exit_ev=200.0,
                    exit_debt=300.0, years=5)
```

- [ ] **Step 2: Run to verify failure**

Run: `cd ~/bluebook && python -m pytest tests/test_comps.py tests/test_lbo.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement**

Peer figures come from published filings or market data with the source recorded, on the same post-IFRS 16 basis as the model. `lbo.py` carries a module docstring stating plainly that this is a sponsor-return exercise on a low-leverage, lease-heavy business rather than a live buyout thesis.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/bluebook && python -m pytest tests/test_comps.py tests/test_lbo.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd ~/bluebook
git add src/bluebook/comps.py src/bluebook/lbo.py tests/test_comps.py tests/test_lbo.py
git commit -m "feat: trading comps and LBO return analysis"
```

---

### Task 11: Workbook styles and sheet-writer scaffolding

**Files:**
- Create: `src/bluebook/workbook/styles.py`
- Create: `src/bluebook/workbook/sheet.py`
- Create: `tests/test_styles.py`

**Interfaces:**
- Produces:
  - `INPUT_FONT`, `FORMULA_FONT`, `LINK_FONT`, `HEADER_FONT` — `openpyxl.styles.Font` objects in blue/black/green/bold.
  - `MONEY_FORMAT = '#,##0.0;(#,##0.0)'`, `PERCENT_FORMAT = '0.0%'`, `MULTIPLE_FORMAT = '0.0"x"'`, `PENCE_FORMAT = '#,##0"p"'`
  - `SheetWriter` — wraps a worksheet and a `Layout`; methods `title(text)`, `year_header(labels, historical)`, `input_row(key, label, values, fmt)`, `formula_row(key, label, formulas, fmt, is_link=False)`, `blank()`. Each row method registers itself in the `Layout` and advances an internal cursor.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_styles.py
import openpyxl
import pytest

from bluebook.workbook.layout import Layout
from bluebook.workbook.sheet import SheetWriter
from bluebook.workbook.styles import INPUT_FONT, FORMULA_FONT, LINK_FONT


def test_fonts_use_the_agreed_colours():
    assert INPUT_FONT.color.rgb == "FF0000FF"
    assert FORMULA_FONT.color.rgb == "FF000000"
    assert LINK_FONT.color.rgb == "FF008000"


def test_input_row_writes_values_in_blue_and_registers_its_row():
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Assumptions"
    layout = Layout()
    writer = SheetWriter(ws, layout, historical=False)
    writer.title("Assumptions")
    writer.year_header(["FY2026", "FY2027", "FY2028", "FY2029", "FY2030"])
    writer.input_row("tax_rate", "Tax rate", [0.25] * 5)

    row = layout.row_of("Assumptions", "tax_rate")
    assert ws[f"F{row}"].value == pytest.approx(0.25)
    assert ws[f"F{row}"].font.color.rgb == "FF0000FF"


def test_formula_row_writes_formulas_in_black():
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "IS"
    layout = Layout()
    writer = SheetWriter(ws, layout, historical=False)
    writer.title("Income Statement")
    writer.year_header(["FY2026", "FY2027", "FY2028", "FY2029", "FY2030"])
    writer.formula_row("revenue", "Revenue", ["=1+1"] * 5)

    row = layout.row_of("IS", "revenue")
    assert ws[f"F{row}"].value == "=1+1"
    assert ws[f"F{row}"].font.color.rgb == "FF000000"
```

- [ ] **Step 2: Run to verify failure**

Run: `cd ~/bluebook && python -m pytest tests/test_styles.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement both modules**

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/bluebook && python -m pytest tests/test_styles.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd ~/bluebook
git add src/bluebook/workbook/styles.py src/bluebook/workbook/sheet.py tests/test_styles.py
git commit -m "feat: workbook styles and sheet-writer scaffolding"
```

---

### Task 12: Write the statement sheets

Assumptions, Historicals, IS, BS, CF, Schedules — as live formulas.

**Files:**
- Create: `src/bluebook/workbook/sheet_assumptions.py`
- Create: `src/bluebook/workbook/sheet_historicals.py`
- Create: `src/bluebook/workbook/sheet_statements.py`
- Create: `src/bluebook/workbook/sheet_schedules.py`
- Create: `src/bluebook/workbook/build.py`
- Create: `tests/test_build_smoke.py`

**Interfaces:**
- Consumes: `SheetWriter`, `Layout`, `ref()`, inputs, assumptions.
- Produces: `build_workbook(historicals, scenario_name, path) -> Path`.

Every forecast cell is a formula referencing the Assumptions sheet or the prior column — never a computed constant. The scenario switch lives at `Assumptions!C3` as a data-validated dropdown over Bear/Base/Bull; driver rows read `=CHOOSE(MATCH($C$3,{"Bear";"Base";"Bull"},0), <bear>, <base>, <bull>)`.

- [ ] **Step 1: Write the failing smoke test**

```python
# tests/test_build_smoke.py
from pathlib import Path

import openpyxl

from bluebook.inputs.greggs import GREGGS_HISTORICALS
from bluebook.workbook.build import build_workbook


def test_build_produces_all_expected_sheets(tmp_path: Path):
    path = build_workbook(GREGGS_HISTORICALS, "Base", tmp_path / "model.xlsx")
    wb = openpyxl.load_workbook(path)
    assert wb.sheetnames == [
        "Cover", "Checks", "Assumptions", "Historicals",
        "IS", "BS", "CF", "Schedules",
        "DCF", "Sensitivity", "Comps", "LBO", "Football Field",
    ]


def test_forecast_cells_are_formulas_not_constants(tmp_path: Path):
    path = build_workbook(GREGGS_HISTORICALS, "Base", tmp_path / "model.xlsx")
    wb = openpyxl.load_workbook(path)
    ws = wb["IS"]
    for row in ws.iter_rows(min_col=6, max_col=10):
        for cell in row:
            if cell.value is not None:
                assert isinstance(cell.value, str) and cell.value.startswith("="), (
                    f"IS!{cell.coordinate} holds a constant: {cell.value!r}"
                )
```

- [ ] **Step 2: Run to verify failure**

Run: `cd ~/bluebook && python -m pytest tests/test_build_smoke.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement, one sheet module at a time**

Build in dependency order — Assumptions, Historicals, Schedules, IS, BS, CF — running the smoke test after each so a broken reference surfaces immediately. Create the DCF, Sensitivity, Comps, LBO, Football Field and Checks sheets as titled-but-empty placeholders in `build.py` so the sheet-name test passes; Tasks 13 and 14 fill them.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/bluebook && python -m pytest tests/test_build_smoke.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd ~/bluebook
git add src/bluebook/workbook tests/test_build_smoke.py
git commit -m "feat: assumptions, historicals, statement and schedule sheets"
```

---

### Task 13: Write the DCF, sensitivity, comps and LBO sheets

**Files:**
- Create: `src/bluebook/workbook/sheet_dcf.py`
- Create: `src/bluebook/workbook/sheet_sensitivity.py`
- Create: `src/bluebook/workbook/sheet_comps.py`
- Create: `src/bluebook/workbook/sheet_lbo.py`
- Modify: `src/bluebook/workbook/build.py`
- Create: `tests/test_sheet_dcf.py`

The sensitivity grids are built as explicit formula grids — each cell recomputes the implied share price from its own WACC and growth pair — not as Excel Data Tables, which openpyxl cannot write and LibreOffice would not reliably recalculate.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_sheet_dcf.py
from pathlib import Path

import openpyxl
import pytest

from bluebook.inputs.greggs import GREGGS_HISTORICALS
from bluebook.workbook.build import build_workbook
from bluebook.workbook.layout import Layout


def test_dcf_sheet_has_the_key_output_rows(tmp_path: Path):
    path = build_workbook(GREGGS_HISTORICALS, "Base", tmp_path / "model.xlsx")
    wb = openpyxl.load_workbook(path)
    labels = {
        c.value for c in wb["DCF"]["B"] if isinstance(c.value, str)
    }
    for required in (
        "WACC", "Unlevered free cash flow", "Terminal value (Gordon growth)",
        "Terminal value (exit multiple)", "Enterprise value",
        "Equity value", "Implied share price (p)",
    ):
        assert required in labels, f"DCF sheet missing '{required}'"


def test_sensitivity_grid_is_fully_populated_with_formulas(tmp_path: Path):
    path = build_workbook(GREGGS_HISTORICALS, "Base", tmp_path / "model.xlsx")
    ws = openpyxl.load_workbook(path)["Sensitivity"]
    grid = [
        c for row in ws.iter_rows(min_row=5, max_row=9, min_col=4, max_col=8)
        for c in row
    ]
    assert len(grid) == 25
    assert all(isinstance(c.value, str) and c.value.startswith("=") for c in grid)
```

- [ ] **Step 2: Run to verify failure**

Run: `cd ~/bluebook && python -m pytest tests/test_sheet_dcf.py -v`
Expected: FAIL — the placeholder sheets are empty

- [ ] **Step 3: Implement the four sheet writers**

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/bluebook && python -m pytest -v`
Expected: PASS (whole suite)

- [ ] **Step 5: Commit**

```bash
cd ~/bluebook
git add src/bluebook/workbook tests/test_sheet_dcf.py
git commit -m "feat: DCF, sensitivity, comps and LBO sheets"
```

---

### Task 14: Checks sheet, Cover sheet and football field chart

**Files:**
- Create: `src/bluebook/workbook/sheet_checks.py`
- Create: `src/bluebook/workbook/sheet_cover.py`
- Create: `src/bluebook/workbook/sheet_football_field.py`
- Modify: `src/bluebook/workbook/build.py`
- Create: `tests/test_checks_sheet.py`

The Cover sheet states the lease treatment and the circularity decision in prose — an interviewer should learn both without opening another tab.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_checks_sheet.py
from pathlib import Path

import openpyxl

from bluebook.inputs.greggs import GREGGS_HISTORICALS
from bluebook.recalc import recalc_values
from bluebook.workbook.build import build_workbook


def test_every_check_evaluates_true(tmp_path: Path):
    path = build_workbook(GREGGS_HISTORICALS, "Base", tmp_path / "model.xlsx")
    checks = recalc_values(path)["Checks"]
    failures = {
        addr: value
        for addr, value in checks.items()
        if addr.startswith("D") and value is not True and isinstance(value, bool)
    }
    assert not failures, f"failing checks: {failures}"


def test_cover_sheet_states_the_lease_treatment(tmp_path: Path):
    path = build_workbook(GREGGS_HISTORICALS, "Base", tmp_path / "model.xlsx")
    ws = openpyxl.load_workbook(path)["Cover"]
    text = " ".join(
        str(c.value) for row in ws.iter_rows() for c in row if c.value is not None
    )
    assert "IFRS 16" in text
    assert "net debt" in text.lower()
```

Checks to implement, one per row in column D as a live `=` formula returning TRUE/FALSE, with the label in column B:
balance sheet balances (each forecast year), cash flow ties to balance-sheet cash, closing debt never negative, cash never below the minimum, `g < WACC`, discounted terminal value below 90% of EV, no forecast revenue growth outside ±50%, and the sum of scenario columns unchanged when the switch is toggled.

- [ ] **Step 2: Run to verify failure**

Run: `cd ~/bluebook && python -m pytest tests/test_checks_sheet.py -v`
Expected: FAIL — `Checks` sheet is an empty placeholder

- [ ] **Step 3: Implement the three sheet writers**

The football field is an `openpyxl.chart.BarChart` with horizontal bars spanning low/high for each of DCF (Gordon), DCF (exit multiple), comps, and 52-week range.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/bluebook && python -m pytest -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd ~/bluebook
git add src/bluebook/workbook tests/test_checks_sheet.py
git commit -m "feat: checks, cover and football field sheets"
```

---

### Task 15: The cross-check — Excel must agree with Python

The task the whole project exists to make possible.

**Files:**
- Create: `tests/test_workbook.py`
- Create: `tests/conftest.py`

**Interfaces:**
- Consumes: `build_workbook` (Tasks 12–14), `recalc_values` (Task 1), `build_model` and `valuation` (Tasks 8–9).

- [ ] **Step 1: Write the failing test**

```python
# tests/conftest.py
from pathlib import Path

import pytest

from bluebook.inputs.greggs import GREGGS_HISTORICALS
from bluebook.recalc import recalc_values
from bluebook.workbook.build import build_workbook


@pytest.fixture(scope="session")
def recalculated(tmp_path_factory) -> dict[str, dict[str, object]]:
    """Build and recalculate the Base-case workbook once for the session."""
    path = build_workbook(
        GREGGS_HISTORICALS, "Base", tmp_path_factory.mktemp("wb") / "model.xlsx"
    )
    return recalc_values(path)
```

```python
# tests/test_workbook.py
"""The workbook's Excel formulas must agree with the Python reference model."""

import pytest

from bluebook.assumptions import SCENARIOS
from bluebook.inputs.greggs import GREGGS_HISTORICALS
from bluebook.reference import build_model
from bluebook.valuation import (
    enterprise_value, equity_bridge, implied_share_price,
    terminal_value_gordon, unlevered_fcf, wacc,
)
from bluebook.workbook.layout import FCST_COLS

TOLERANCE = 0.02  # £m / pence


@pytest.fixture(scope="session")
def python_model():
    return build_model(GREGGS_HISTORICALS, SCENARIOS["Base"])


def _row_values(recalculated, sheet, row):
    return [recalculated[sheet].get(f"{col}{row}") for col in FCST_COLS]


@pytest.mark.parametrize(
    "sheet,line",
    [
        ("IS", "revenue"), ("IS", "ebitda"), ("IS", "ebit"), ("IS", "net_income"),
        ("BS", "total_assets"), ("BS", "cash"), ("BS", "equity"),
        ("CF", "closing_cash"),
    ],
)
def test_excel_matches_python_line_by_line(recalculated, python_model, sheet, line):
    from bluebook.workbook.build import LAYOUT  # populated during build

    row = LAYOUT.row_of(sheet, line)
    excel = _row_values(recalculated, sheet, row)
    statement = {
        "IS": python_model.income_statement,
        "BS": python_model.balance_sheet,
        "CF": python_model.cash_flow,
    }[sheet]
    expected = statement[line]
    for i, (got, want) in enumerate(zip(excel, expected)):
        assert got == pytest.approx(want, abs=TOLERANCE), f"{sheet}.{line} year {i}"


def test_excel_wacc_matches_python(recalculated):
    from bluebook.workbook.build import LAYOUT

    row = LAYOUT.row_of("DCF", "wacc")
    assert recalculated["DCF"][f"D{row}"] == pytest.approx(
        wacc(SCENARIOS["Base"]), abs=0.0001
    )


def test_excel_implied_share_price_matches_python(recalculated, python_model):
    from bluebook.workbook.build import LAYOUT

    drivers = SCENARIOS["Base"]
    fcf = unlevered_fcf(python_model, drivers)
    rate = wacc(drivers)
    tv = terminal_value_gordon(fcf[-1], rate, drivers.perpetuity_growth)
    ev = enterprise_value(fcf, tv, rate)
    equity = equity_bridge(
        ev,
        net_debt=python_model.balance_sheet["net_debt"][-1],
        lease_liabilities=python_model.balance_sheet["lease_liabilities"][-1],
    )
    from bluebook.inputs.greggs import GREGGS_SHARE_COUNT

    expected = implied_share_price(equity, GREGGS_SHARE_COUNT.value)
    row = LAYOUT.row_of("DCF", "implied_share_price")
    assert recalculated["DCF"][f"D{row}"] == pytest.approx(expected, abs=0.5)


def test_no_error_values_anywhere(recalculated):
    errors = {
        f"{sheet}!{addr}": value
        for sheet, cells in recalculated.items()
        for addr, value in cells.items()
        if isinstance(value, str) and value.startswith(("#", "Err:"))
    }
    assert not errors, f"error values in workbook: {errors}"
```

- [ ] **Step 2: Run to verify failure**

Run: `cd ~/bluebook && python -m pytest tests/test_workbook.py -v`
Expected: FAIL — mismatches, missing `LAYOUT` export, or missing line-item registrations

- [ ] **Step 3: Reconcile until they agree**

Every mismatch is a genuine bug in one side or the other. Find which side is wrong before changing anything — do not loosen `TOLERANCE` to make a test pass. Export the populated `LAYOUT` from `build.py` so tests can resolve rows by name.

- [ ] **Step 4: Run the full suite**

Run: `cd ~/bluebook && python -m pytest -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd ~/bluebook
git add tests/conftest.py tests/test_workbook.py src/bluebook/workbook/build.py
git commit -m "test: cross-check recalculated workbook against Python reference"
```

---

### Task 16: Convention enforcement, generated artifact and README

**Files:**
- Create: `tests/test_conventions.py`
- Create: `README.md`
- Create: `scripts/generate.py`
- Create: `dist/greggs_model.xlsx` (generated, committed)

- [ ] **Step 1: Write the failing conventions test**

```python
# tests/test_conventions.py
"""Structural rules the workbook must satisfy, enforced rather than trusted."""

import openpyxl
import pytest

from bluebook.inputs.greggs import GREGGS_HISTORICALS
from bluebook.workbook.build import build_workbook

from bluebook.workbook.styles import HARDCODE_ALLOWED  # single source of truth

# NOTE (2026-08-06): HARDCODE_ALLOWED was originally defined locally here. It is now a
# production constant that SheetWriter enforces at write time, so a hardcode on a
# calculation sheet fails where it is made rather than in this end-of-project scan.
# Import it; do NOT redefine it, or the two can drift apart.


@pytest.fixture(scope="module")
def workbook(tmp_path_factory):
    path = build_workbook(
        GREGGS_HISTORICALS, "Base", tmp_path_factory.mktemp("conv") / "model.xlsx"
    )
    return openpyxl.load_workbook(path)


def test_no_hardcoded_numbers_outside_input_sheets(workbook):
    offenders = []
    for ws in workbook.worksheets:
        if ws.title in HARDCODE_ALLOWED:
            continue
        for row in ws.iter_rows(min_col=3):
            for cell in row:
                if isinstance(cell.value, (int, float)):
                    offenders.append(f"{ws.title}!{cell.coordinate}={cell.value}")
    assert not offenders, f"hardcoded values in formula regions: {offenders}"


def test_input_cells_are_blue_and_formula_cells_are_not(workbook):
    ws = workbook["Assumptions"]
    for row in ws.iter_rows(min_col=6, max_col=10):
        for cell in row:
            if isinstance(cell.value, (int, float)):
                assert cell.font.color.rgb == "FF0000FF", (
                    f"Assumptions!{cell.coordinate} is an input but is not blue"
                )


def test_the_workbook_has_no_circular_references(workbook):
    """The acyclicity the design depends on, enforced rather than assumed.

    Added 2026-08-06. Task 12 established that headless LibreOffice cannot
    resolve a chained or branched circularity: it freezes the second branch of a
    branch and resolves only the first link of a chain, silently, returning a
    self-consistent but wrong fixed point. The interest basis was switched to
    "opening" precisely so the workbook is acyclic and every cell can be
    cross-checked. A reviewer proved acyclicity by parsing all 490 formulas into
    a 1,050-edge reference graph — but that proof lived in a review transcript,
    and nothing in the suite would have failed if someone reinstated an
    average-basis interest row. This is that proof, made permanent.

    Parse every formula into (sheet, cell) edges and assert the graph is acyclic.
    Handle quoted and unquoted sheet prefixes, absolute markers, and ranges. On
    failure, report the cycle found — a cycle is not a style violation, it is a
    workbook whose recalculated values cannot be trusted.
    """
    graph = _reference_graph(workbook)
    cycle = _find_cycle(graph)
    assert cycle is None, f"circular reference: {' -> '.join(cycle)}"


def test_every_sheet_has_a_title_in_a1(workbook):
    for ws in workbook.worksheets:
        assert isinstance(ws["A1"].value, str) and ws["A1"].value.strip(), ws.title
```

- [ ] **Step 2: Run to verify failure**

Run: `cd ~/bluebook && python -m pytest tests/test_conventions.py -v`
Expected: FAIL — expect real offenders on the first run; fix the writers, not the test

- [ ] **Step 3: Fix the writers until conventions hold**

- [ ] **Step 4: Write the generation script**

```python
# scripts/generate.py
"""Generate the distributable workbook: python scripts/generate.py"""

from pathlib import Path

from bluebook.inputs.greggs import GREGGS_HISTORICALS
from bluebook.workbook.build import build_workbook

if __name__ == "__main__":
    out = Path(__file__).resolve().parent.parent / "dist" / "greggs_model.xlsx"
    out.parent.mkdir(exist_ok=True)
    build_workbook(GREGGS_HISTORICALS, "Base", out)
    print(f"wrote {out}")
```

- [ ] **Step 5: Write the README**

Lead with what the project is and the fact that the model is machine-verified. Cover: how to regenerate (`python scripts/generate.py`), how to run the tests, the lease treatment and why, the circularity decision and what the spike found, the sourcing rule for historicals, and an honest statement that the forecast drivers are the author's assumptions rather than company guidance.

- [ ] **Step 6: Generate, verify, run everything**

```bash
cd ~/bluebook
python scripts/generate.py
python -m pytest -v
```
Expected: workbook written; full suite PASS. Open `dist/greggs_model.xlsx` and confirm by eye that formulas appear in the formula bar and every Checks row reads TRUE.

- [ ] **Step 7: Commit**

```bash
cd ~/bluebook
git add tests/test_conventions.py scripts/generate.py README.md dist/greggs_model.xlsx
git commit -m "feat: convention enforcement, generation script and README"
```

---

## Self-review

**Spec coverage:** Purpose → Task 16 README. Subject and data sourcing → Task 3. Approach (dual model + recalc cross-check) → Tasks 1, 8, 15. Architecture → file structure across Tasks 3–14. All thirteen sheets → Tasks 12, 13, 14. Colour conventions → Tasks 11, 16. Scenario switch → Tasks 4, 12. Lease treatment → Global Constraints, Tasks 6, 9, 10, 14. LBO framing → Task 10. Circularity spike → Task 2, consumed by Task 7. Three test layers → Tasks 8/9 (reference), 15 (workbook), 16 (conventions). Toolchain → Task 1. Distribution → deferred to a separate plan, as flagged at the top.

**Known gap:** the spec's football-field 52-week trading range needs a market data point that no task sources. It is entered as a sourced hardcode on the Comps sheet during Task 10 — `Comps` is on the `HARDCODE_ALLOWED` list in Task 16 for exactly this reason.

**Type consistency:** `Sourced`/`HistoricalYear` (Task 3) are consumed unchanged by Tasks 8, 12, 15. `Drivers` (Task 4) flows to Tasks 6, 7, 8, 9. `Layout.ref()` (Task 5) is used by Tasks 11–14 and `LAYOUT.row_of()` by Task 15, which is why Task 15 Step 3 requires exporting the populated instance. `build_model` → `Model` (Task 8) is consumed by Task 9's `unlevered_fcf` and Task 15. `recalc_values` (Task 1) is consumed by Tasks 2, 14, 15 with the same `{sheet: {cell: value}}` shape throughout.
