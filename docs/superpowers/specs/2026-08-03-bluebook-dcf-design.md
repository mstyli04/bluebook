# Bluebook — 3-Statement + DCF Model

**Date:** 2026-08-03
**Status:** Design approved, not yet implemented
**Repo:** `~/bluebook`

## Purpose

Build a genuine, auditable valuation model for a real listed company, generated
and tested from Python. The project closes the investment-banking / valuation
gap in an otherwise quant- and web-heavy portfolio, and unblocks the
"Financial Modelling" entry that has been held out of both CVs' Key Skills
sections pending a real DCF project.

Success means an interviewer can open the workbook, click any cell, see a live
formula, trace it back to a sourced historical figure, and question the
assumptions — and that the repository proves the model's arithmetic is
machine-verified rather than asserted.

## Subject

Greggs plc, a UK-listed bakery and food-to-go retailer. Chosen for a clean,
simple P&L that can be defended line by line, and for UK-market relevance to
placement applications. The engine is company-agnostic: one company is one
input module, so a second name can be added without touching the model logic.

Historical financials cover the three most recent reported full years
(FY2023–FY2025), taken from the published annual reports. Greggs reports on a
52/53-week retail year; the exact period-end convention is to be confirmed
against the filings and stated on the Cover sheet.

**Data-sourcing requirement:** no historical figure enters the model without a
source reference — the annual report and page number — recorded alongside it in
the input module and surfaced as a cell comment in the workbook. Figures are
transcribed from the filings, never recalled from memory or estimated.

## Approach

Model structure is declared in Python as data; a builder writes **live Excel
formulas** into the workbook. Cells contain formulas, not computed values, so
the delivered `.xlsx` is a working model rather than an exported snapshot.

Correctness is established by two independent expressions of the same model
that must agree:

- `reference.py` — the maths in pure Python, fast to test.
- `workbook/` — the same model as Excel formulas.

An integration test recalculates the generated workbook headlessly through
LibreOffice (`soffice`, already installed) and asserts the values Excel
computes match the Python reference within tolerance. This is what makes the
claim "the model is unit-tested" literally true: it verifies the Excel
formulas, not merely the Python.

Two rejected alternatives, recorded so they are not revisited: computing
everything in pandas and exporting values (produces a dead workbook of
hardcodes, defeating the purpose), and hand-building in Excel with Python
auditing only (forfeits reproducibility; retained as the fallback if
formula-writing proves unworkable).

## Architecture

```
bluebook/
  src/bluebook/
    inputs/greggs.py      # historicals + drivers; one company = one file
    reference.py          # pure-Python model: the maths, no Excel
    schedules/            # debt, ppe/d&a, working capital, leases
    valuation.py          # WACC, FCF, TV, EV→equity bridge
    comps.py
    lbo.py
    workbook/
      styles.py           # colour conventions, number formats
      build.py            # orchestrates sheet writers
      sheet_*.py          # one writer module per sheet
  tests/
    test_reference.py
    test_workbook.py
    test_conventions.py
  dist/greggs_model.xlsx  # generated, committed
  README.md
```

The boundary that matters: `reference.py` knows the maths and nothing about
Excel; `workbook/` knows Excel and defers all arithmetic meaning to the model
definition. Neither imports the other's concerns. Each sheet writer is a
separate module so no single file grows past what can be held in context at
once.

## Workbook structure

Thirteen sheets:

| # | Sheet | Contents |
|---|---|---|
| 1 | Cover | Company, valuation date, scenario in force, lease-treatment statement, usage notes |
| 2 | Checks | Every integrity check, positioned second rather than last |
| 3 | Assumptions | All hardcoded inputs; scenario switch at top |
| 4 | Historicals | As-reported figures, each sourced to report and page |
| 5 | Income Statement | Forecast years fully linked |
| 6 | Balance Sheet | Balances every year with no plug |
| 7 | Cash Flow | Ties to balance-sheet cash movement |
| 8 | Schedules | Debt & revolver, PP&E/D&A, working capital, leases |
| 9 | DCF | WACC build, unlevered FCF, terminal value by both Gordon growth and exit multiple, EV→equity bridge, implied share price |
| 10 | Sensitivity | WACC × perpetuity growth; WACC × exit multiple |
| 11 | Comps | Approximately five peers; EV/EBITDA and P/E |
| 12 | LBO | Sources & uses, debt paydown, IRR and money multiple |
| 13 | Football field | Chart comparing DCF, comps and 52-week trading range |

Forecast horizon is five years.

### Conventions

Standard banker colour coding, enforced by test rather than by discipline:
blue for hardcoded inputs, black for on-sheet formulas, green for links from
other sheets. Hardcoded constants are permitted only on the Assumptions and
Historicals sheets; `test_conventions.py` scans the generated file and fails on
any stray constant inside a formula region.

### Scenario switch

A single cell on Assumptions drives a `CHOOSE`/`INDEX` row. Bull, base and bear
driver sets sit side by side and visibly re-drive the entire model, including
the DCF and LBO outputs.

### Lease treatment (IFRS 16)

Greggs leases substantially its entire shop estate, making lease liabilities a
material, deliberate modelling decision rather than a detail.

**Chosen treatment:** post-IFRS 16 throughout. EBITDA is struck after
depreciation of right-of-use assets is excluded (i.e. the reported,
post-IFRS 16 basis), and lease liabilities are included within net debt in the
EV→equity bridge. This is chosen because UK-listed peers all report on the same
basis, so the comps sheet requires no restatement to stay comparable.

This treatment is stated explicitly on the Cover sheet and applied consistently
across the DCF, the comps and the LBO. Consistency across those three is a hard
requirement; inconsistent lease treatment is the most common failure in
candidate models and the most likely line of interview questioning.

### LBO framing

The LBO sheet is presented as a sponsor-return exercise on a low-leverage,
lease-heavy business, with that constraint stated on the sheet. It does not
represent Greggs as a live buyout candidate.

## Circularity and the opening spike

The debt schedule with a revolver introduces a circular reference: interest
expense feeds net income, which feeds cash, which feeds the debt balance, which
feeds interest expense. Excel resolves this with iterative calculation. Whether
LibreOffice honours the iterative-calculation setting when written by openpyxl
is unverified and determines the debt schedule's shape.

**Therefore the first task, before any modelling work, is a spike:** generate a
throwaway workbook containing a deliberate circular reference, set
`wb.calculation.iterate`, recalculate through `soffice --headless`, read the
values back, and record whether LibreOffice converges or emits `Err:522`.

- **Converges:** interest is computed on average debt balances, with a
  circularity-breaker toggle on Assumptions.
- **Does not converge:** interest is computed on beginning-of-period debt
  balances — common practice in production models — with the breaker toggle
  still present and the reason recorded in the README.

Both outcomes are acceptable and defensible. All subsequent modelling waits on
the spike result.

## Testing

Implementation is test-first throughout.

**`test_reference.py`** — pure Python, fast:
- the balance sheet balances in every forecast year
- the cash flow statement ties to the balance-sheet cash movement
- scenario changes move outputs in the expected direction
- terminal value does not exceed a defined share of enterprise value
- perpetuity growth is below WACC

**`test_workbook.py`** — recalculates the generated `.xlsx` through `soffice`,
reads computed values back, and asserts agreement with `reference.py` within
tolerance. Verifies the Excel formulas themselves.

**`test_conventions.py`** — structural scan of the generated file: no hardcoded
constants in formula regions, every cell on the Checks sheet evaluating TRUE,
and no `#REF!`, `#DIV/0!` or other error values anywhere in the workbook.

## Toolchain

Already present on the machine; no installation required (note that `sudo` on
this box requires a password, so avoiding installs is deliberate):
`soffice` (LibreOffice 24.2.7), openpyxl 3.1.5, pandas 3.0.3, numpy 2.4.4,
pytest 9.0.3.

## Distribution

1. **Public GitHub repository** — Python source, tests, and the generated
   `.xlsx` committed. README walks through the model, states the lease
   treatment and the circularity decision, and leads with the test suite.
2. **Portfolio row on cinematic-hero** — football-field visual and a direct
   `.xlsx` download, placed below Placement Scout (row 1) and Paper Alpha
   (row 2) per the established row-order rule.
3. **CV updates** — a Projects entry in both maintained `.docx` files
   (`Michael_Stylianou_CV 0726.docx` and `Michael_Stylianou_CV 0726 2.docx` in
   `/mnt/c/Users/Michael/Desktop/Michael CVs/`), and "Financial Modelling"
   added to Key Skills in both.
4. **Desktop mirror** — copy the finished project to
   `Desktop\Claude Code Projects` per standing practice.

## Out of scope

- Additional companies beyond Greggs in the first build.
- Monte Carlo simulation over model drivers.
- Automated fetching of financials from an API or EDGAR; historicals are
  transcribed from filings by hand and sourced.
- Any web application beyond the single portfolio row.
