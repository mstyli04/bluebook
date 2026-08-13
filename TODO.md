# Bluebook — what is left to do

**Written 2026-08-07, at a hard stop on the monthly spend limit.**
Repo: `~/bluebook`, branch `build-model`. HEAD `1ff8fe7`. 282 tests passing, tree clean.

This file is the handoff. It is written for whoever picks this up — including a future
Claude session with no memory of building it. Everything needed to resume is here or is
pointed at from here.

---

## 1. Where the project stands

**12 of 16 tasks are closed and reviewed. Task 13 is built but NOT reviewed. Task 14 is
built but NOT reviewed (13 Aug 2026). Tasks 15–16 have not been started.**

> **Update, 13 Aug 2026 — Task 14 built, uncommitted, unreviewed.** Adds
> `sheet_football_field.py` and `sheet_checks.py`, wires both into `build.py`, empties
> `PLACEHOLDER_TITLES`, and adds `scripts/generate.py` (which Task 16 also lists) and
> `tests/test_football_field.py`. 289 tests pass, up from 282. The generated workbook was
> recalculated through headless LibreOffice: all eight Checks rows read TRUE, the football
> field's three bars carry real values, and there are no error cells anywhere in the file.
> Peak borrowings recompute to £207.1m at 0.48x EBITDA, matching the figures the Cover
> notes already quote for Base — an independent confirmation the Checks rows address the
> intended lines. The Cover sheet half of Task 14 was already written by Task 12 and was
> not touched.
>
> **Reviewed by mutation the same day, and it found a real defect.** Twelve mutations were
> applied to the generated workbook, each recalculated through LibreOffice. Round 1 was
> partly invalid — three mutations matched `'Closing'` to the wrong Schedules rows (Closing
> PP&E, not Closing borrowings) and were re-run against exact cells. The finding that
> survived: **`check_cash_ties` was very nearly vacuous.** It compared `CF!closing_cash` to
> `BS!cash`, and `BS!cash` is literally `='CF'!closing_cash` — a cell against itself.
> Breaking the cash flow statement's own `net_change_in_cash` left it reading TRUE; only
> the balance-sheet check noticed, incidentally. Fixed by also tying to
> `Schedules!cash_closing`, the debt schedule's independently constructed cash track.
> Re-tested: the mutation that slipped through is now caught, and breaking the schedule's
> track alone is caught by this check and by nothing else, so the added comparison carries
> real coverage rather than restating the old one. All eight checks then verified TRUE in
> **all three scenarios** with zero error cells, and the implied share prices reproduce this
> file's own table exactly (624.68p / 1,506.50p / 2,560.65p).
>
> **Still not done for Task 14:** no independent agent has reviewed the code (this was a
> self-review, which section 6 would say is the weaker result), and `check_debt_never_negative`
> is a regression guard rather than a live test — closing borrowings cannot go negative by
> construction while the repayment formula caps at `debt_opening`, so it can only fail if a
> future edit removes that cap. It is worth keeping on those terms; it should not be read as
> evidence the model was checked.

The financial model is complete and verified. The workbook is substantially built.

| | Bear | Base | Bull |
|---|---|---|---|
| Implied share price | 624.68p | **1,506.50p** | 2,560.65p |
| Terminal unlevered FCF | £95.8m | £126.4m | £165.1m |
| Exit multiple (derived) | 5.07× | 6.31× | 7.24× |

WACC 7.7311%. Peer median EV/EBIT 13.4277×. FY2025 net debt including leases £404.0m.

**The six substantive sheets are live and cross-checked.** A test recalculates the generated
`.xlsx` through headless LibreOffice and asserts ~73 rows × 5 forecast years × 3 scenarios
against the Python model at a tolerance of **1e-9**. The workbook was proved acyclic by
parsing all 490 formulas into a 1,050-edge reference graph — zero cycles.

### The plan and the ledger

- **Plan:** `docs/superpowers/plans/2026-08-03-bluebook-model.md`. It has been amended
  several times as findings came in; those amendments are marked and dated in place. Read it
  as the current spec, not as a historical document.
- **Spec:** `docs/superpowers/specs/2026-08-03-bluebook-dcf-design.md`.
- **Ledger:** `.superpowers/sdd/2026-08-03-bluebook-model/progress.md` — git-ignored, and the
  single most useful file here. It records every task's outcome, every ruling and its
  reasoning, every deferred minor, and the recovery state after each of thirteen
  interruptions. **Read it before doing anything.**
- **Per-task briefs and reports:** same directory, `task-N-brief.md` / `task-N-report.md`.
- **The circularity record:** `docs/superpowers/spike-circularity.md`. Explains why the debt
  schedule charges interest on opening balances. Non-obvious and load-bearing.

### How the work was run

Each task was: extract a brief from the plan → dispatch a fresh implementer → independent
review → fix rounds until clean → record in the ledger. To continue that pattern:

```bash
SKILL=~/.claude/plugins/cache/claude-plugins-official/superpowers/6.2.0/skills/subagent-driven-development
"$SKILL/scripts/task-brief"     docs/superpowers/plans/2026-08-03-bluebook-model.md <N>
"$SKILL/scripts/review-package" docs/superpowers/plans/2026-08-03-bluebook-model.md <BASE> <HEAD>
```

The review step is not optional decoration. Every significant defect in this project was
found by an independent agent checking another's work — see section 6.

---

## 2. Task 13 — review only (built, unreviewed)

Commit `1ff8fe7` added `sheet_dcf.py`, `sheet_sensitivity.py`, `sheet_comps.py`,
`sheet_lbo.py` and 11 tests. **The spend limit hit while it was writing its report, so the
report is thin or absent and nothing has been independently checked.**

### Claims to verify

1. **Every forecast cell on DCF, Sensitivity and LBO is a formula.** Comps is on
   `HARDCODE_ALLOWED` and may hold constants; the other three may not. Load the generated
   workbook and check F:J directly rather than reading the test.
2. **The cross-check was extended, not duplicated.** Its rows should have been added to
   `CHECKED_ROWS` in `tests/test_workbook_sheets.py`, so they run inside the existing
   comparison against `valuation.py`, `comps.py` and `lbo.py`. A parallel test beside it
   would be a weaker result.
3. **The sensitivity grids are explicit formula grids**, 5×5, fully populated, each cell
   recomputing the implied share price from its own WACC and growth pair. Not Excel Data
   Tables — openpyxl cannot write those and LibreOffice would not recalculate them.
4. **The terminal year is mirrored from `valuation.py`, not re-derived.** It is re-based, not
   raw FY2030: one terminal growth rate used consistently, capex and ROU additions at
   sustaining intensities, and the excess PP&E tax shield added back explicitly as a decaying
   series.
5. **The exit-multiple caveat is stated on the sheet.** This one matters. Because
   `EV/EBITDA ≡ EV/EBIT × (1 − D&A/EBITDA)` is an identity and the multiple is derived from
   the peer median EV/EBIT, `terminal_value_exit_multiple` is arithmetically
   `13.4277 × terminal EBIT` in every scenario. It contains nothing beyond one peer
   statistic. Presenting it beside the Gordon result as corroboration would mislead.

### Verification worth repeating

The Task 12 review's method is the standard to hold this to: mutate a formula on a sheet and
confirm the cross-check fails. A cross-check that cannot fail is the single defect that would
invalidate the project's central claim.

---

## 3. Task 14 — Checks sheet, Cover sheet, football field

Brief: extract task 14 from the plan. Creates `sheet_checks.py`, `sheet_cover.py`,
`sheet_football_field.py`; modifies `build.py`.

### The Checks sheet

Every check a live `=` formula returning TRUE/FALSE, label in column B, result in column D,
positioned as the **second** tab so it is impossible to miss. The plan lists: balance sheet
balances each forecast year; cash flow ties to the balance-sheet cash movement; closing debt
never negative; cash never below the minimum; `g < WACC`; discounted terminal value below 90%
of EV; no forecast revenue growth outside ±50%.

**Add one the plan does not list, per a ruling in the ledger:** peak borrowings against the
real £100m facility, as a **named** check. The model draws to roughly £191m / £207m / £211m at
its FY2028 peak. That is disclosed as a financing assumption, not hidden — see below.

Note the terminal-value check needs care. The plan's 0.9 bound was found to compare different
discount clocks and was re-banded during Task 9; actual concentration is 93–95% of EV, which
is high but is what a heavy-investment forecast period produces. Check what
`tests/test_valuation.py` now asserts before writing the sheet version.

### The Cover sheet

Already partly written by Task 12 — it carries five text notes in B3:B7 registered as
`cover_*` layout keys, so a Task 14 writer continuing the same cursor can append. **Do not
drop the existing disclosure.** It must state:

- **Lease treatment.** Post-IFRS 16 throughout: EBITDA excludes rent, right-of-use
  depreciation sits in D&A, lease liabilities are inside net debt in the EV bridge. Applied
  identically to the DCF, the comps and the LBO.
- **The circularity decision.** Interest is charged on **opening** debt balances, making the
  workbook acyclic. This was a measured decision, not a shortcut: headless LibreOffice cannot
  resolve a chained or branched circularity — it freezes the second branch of a branch and
  resolves only the first link of a chain, silently returning a self-consistent wrong answer.
  See `docs/superpowers/spike-circularity.md` and
  `tests/test_libreoffice_iteration_limits.py`.
- **The RCF-upsize financing assumption.** The model needs about £200m at peak against
  Greggs' actual £100m facility. Quote lease-inclusive net debt/EBITDA of **~1.50×** (Bear
  1.76×) as the evidence it is readily financeable — **not** the 0.46× gross figure, which is
  the most flattering of three defensible measures and inconsistent with a post-IFRS 16
  denominator.
- **The peer-provenance asymmetry.** Greggs' own figures were read line by line from annual
  report PDFs and reconciled to the filings. The peer figures came from RNS announcements via
  a summarising fetcher, cross-checked internally but not read from source documents. Those
  are different evidentiary standards and the workbook should say so rather than present both
  in one table as equivalents.
- **The impairment convention.** Historical `depreciation_ppe` and `depreciation_rou` include
  impairment, so D&A here exceeds the cash flow statement's depreciation lines by £3.9–6.9m a
  year. Deliberate, so impairment is added back as the non-cash charge it is.

### The football field

An `openpyxl.chart.BarChart` with horizontal bars spanning low/high for: DCF (Gordon), DCF
(exit multiple), comps, and the 52-week trading range. The 52-week range is
**1,407.20–2,046.00**, sourced on the Comps side with its provider and date — it is the one
figure in the workbook that goes stale, and it should say so.

**Label the exit-multiple bar honestly.** See Task 13 item 5. Two DCF bars where one is
`13.4277 × terminal EBIT` is not two methods.

---

## 4. Task 15 — verify cross-check coverage (much smaller than the plan says)

**The plan's Task 15 is largely already done.** It was written to build the cross-check
between the recalculated workbook and the Python model; Task 12 built it for the statement
sheets and Task 13 was instructed to extend it. **Do not rebuild it.**

What Task 15 should now do:

1. Confirm coverage is complete — every meaningful row on every sheet is inside
   `CHECKED_ROWS`, including the DCF, Sensitivity, Comps and LBO rows Task 13 added.
2. Confirm the tolerance is still honest. It is **1e-9**, and that is defensible only because
   the workbook is acyclic: LibreOffice evaluates every cell in one pass, so the only
   difference from Python is floating-point association. The earlier constraint that the
   tolerance must not be tighter than ~1e-4 (to leave room for iterative convergence slack)
   **no longer applies** and its note in the ledger is superseded.
3. Confirm the error-value scan — no `#REF!`, `#DIV/0!`, `Err:522` or similar anywhere.
4. Mutate several formulas across different sheets and confirm each is caught.

---

## 5. Task 16 — conventions scan, generation script, README, artefact

### The conventions test

`tests/test_conventions.py`. The plan has been amended and now requires **four** things:

1. **No hardcoded numbers outside the allow-list.** Import `HARDCODE_ALLOWED` from
   `bluebook.workbook.styles` — do **not** redefine it locally. It is
   `{"Assumptions", "Historicals", "Comps", "Cover", "Checks"}` and `SheetWriter` already
   enforces it at write time; this test is the belt to that braces.
2. **Input cells blue, formula cells not.**
3. **Every sheet has a non-empty title in A1.**
4. **`test_the_workbook_has_no_circular_references`** — added to the plan on 2026-08-06 and
   the highest-value item in this task. Parse every formula into `(sheet, cell)` edges and
   assert the reference graph is acyclic. Handle quoted and unquoted sheet prefixes, absolute
   markers and ranges. On failure, report the cycle.

   The reason this matters: the design depends on acyclicity, a reviewer proved it once by
   parsing 490 formulas into a 1,050-edge graph, and that proof lives in a review transcript
   rather than the repository. Nothing currently in the suite would fail if someone
   reinstated an average-basis interest row — and the failure would be silent, because
   LibreOffice returns a plausible wrong number rather than an error.

### The rest

- `scripts/generate.py` — writes `dist/greggs_model.xlsx`.
- **README.** Lead with what the project is and that the model is machine-verified. Cover:
  how to regenerate, how to run the tests, the lease treatment and why, the circularity
  decision and what the spike actually found, the sourcing rule for historicals, the peer
  provenance asymmetry, the RCF-upsize assumption, and an honest statement that the forecast
  drivers are the author's assumptions and not company guidance.
- **Commit `dist/greggs_model.xlsx`.** Then open it and confirm by eye that formulas appear
  in the formula bar and every Checks row reads TRUE.

---

## 6. Deferred minors, for the final whole-branch review

Accumulated across twelve tasks and deliberately not fixed. None is load-bearing; each was
judged not worth its own fix round at the time. The final review should triage which must be
closed before this is shown to anyone.

**Data and disclosure**
- Three of five peer EBITDAs are build-ups rather than printed subtotals (Wetherspoon, M&B,
  Whitbread). All five EBITs are printed, and the derived exit multiple depends only on the
  median EV/EBIT, so the load-bearing statistic rests entirely on printed figures.
- No page references exist for any peer figure. Greggs' own figures all have them.
- The impairment asymmetry understates the derived exit multiple by 3.5–6.7%. Disclosed, not
  adjusted — adjusting needs the Task 3 impairment convention reopened.
- `GREGGS_FY2025_LEASE_INTEREST = 16.7` is the last underived number in `assumptions.py`, a
  bare literal with a page citation because `finance_costs` bundles lease interest. It now
  sets the blended cost of debt and therefore the WACC, so it does more work than when it was
  first written. Closing it properly needs a `lease_interest` field on `HistoricalYear`.
- SSP's printed EBIT of 269.1 is an APM reconciliation-table subtotal, not an
  income-statement face line.
- An SSP amortisation figure of (10.4) was seen in the announcement and never located;
  deliberately not attributed to a table.

**Model**
- The share count is weighted-average diluted, an EPS construct. Period-end diluted is the
  more standard divisor for an implied share price. Sensitivity ~16p per 1%. Needs a sourced
  figure.
- No finance income on cash is modelled (~£2m/yr pre-tax, ~£1.5m after tax). No driver exists.
- The ROU mirror of the excess-PP&E tax shield is not applied (~3p/share).
- `ppe_depreciation_rate` includes impairment and is used as the perpetual asset decay rate,
  so the perpetuity assumes the estate is impaired at FY2025's rate forever. Conservative.
- Terminal EBITDA margin is left at the FY2030 driver rather than normalised.
- `schedules/leases.py` docstring says the additions coefficient is `k ≈ 0.093`; the true
  value is 0.09232. Zero consequence — the shipped constant comes from the joint solve, not
  that illustrative line.

**Tests and code**
- The ROU-side tests are closed-form and would inherit a blind spot if `leases()` ever gained
  a capex split.
- `test_iterated_schedule_agrees_with_the_closed_form` does not fire under value mutations,
  since both methods share the mutated input. It guards method-versus-formula only, and says so.
- `freeze_panes = "C3"` is applied to every sheet including Cover, whose column B holds
  110-character notes — they cannot be scrolled into view. Task 14 owns that sheet.
- The C3-toggle test's tail assertion compares two Python models rather than the file.
  Harmless; the 72-row comparison above it already pins the file.
- `TEXT_FORMAT = 'General'` is a no-op and the name overstates it.
- Fifteen `other_assets` cell comparisons carry no information (held flat at a reported nil).
- Three defensive branches are unexercised by any scenario: the `MIN` repayment cap, the
  `MAX` tax floor, the `MAX` dividend floor. Covered on the Python side.

---

## 7. After Task 16

1. **Final whole-branch review** on the most capable model, over
   `git merge-base main HEAD..HEAD`, pointed at section 6 so it can triage the deferred list.
2. **Then the distribution plan**, which was deliberately kept out of the build plan because
   it is not software and depends on the finished artefact:
   - Public GitHub repo with the `.xlsx` committed and the README as the front door.
   - A portfolio row on `cinematic-hero` with the football-field visual and a direct download.
     Row order: Placement Scout first, Paper Alpha second, then this.
   - Both CVs (`Michael_Stylianou_CV 0726.docx` and `0726 2.docx` in
     `/mnt/c/Users/Michael/Desktop/Michael CVs/`): a Projects entry, and **"Financial
     Modelling" added to Key Skills** — which is the line that was being held back until a
     real DCF project existed.
   - Mirror to `Desktop\Claude Code Projects` (already done as of 2026-08-07).

---

## 8. Things worth knowing before you touch anything

**The model modules are closed.** `reference.py`, `valuation.py`, `comps.py`, `lbo.py`,
`assumptions.py`, `inputs/`, `schedules/`, `lease_rate.py`. Twelve tasks of scrutiny sit
behind them, including two independent full recomputations of the valuation and 52 injected
mutations with zero escapes. Work in `src/bluebook/workbook/` and `tests/`.

**Prose drifting from code is this project's dominant defect.** It appeared in at least nine
places across twelve tasks: comments stating basis-point moves that didn't match the tuple
beside them, a comment claiming 7.41% above a value of 7.00%, `wacc()`'s docstring stating
the opposite of what `wacc()` does, a register asserting something the module's own peer
comment contradicted. **No test catches this class.** The durable fix, every time, was to
*derive* facts rather than restate them — see the `HIST_*` constants in `assumptions.py`.

**Tests that pass while proving nothing are the second theme.** Five instances: a unit test
that re-derived a formula from its own output; a concentration bound whose numerator and
denominator used different discount clocks; a sanity check loose enough to pass at three
times the historical norm; a row lookup that adapted to whatever offset the code chose; and a
robustness test that dropped the minimum from a five-set median, where the median barely
moves by construction. Ask of every test: *would this fail if the thing it names were broken?*

**Numbers in reports and comments must be recomputed, not copied.** Two agents reported
counts they had estimated rather than extracted. One left a figure in a design-rationale
document measured against a version that had been reverted and could not be re-derived. The
lesson one of them drew is worth keeping: diagnostic numbers get less scrutiny than model
numbers while often doing heavier work.

**Every ruling has its reasoning in the ledger.** If something looks arbitrary — why opening
balances, why beta 0.90, why a terminal anchor of 40.6%, why the exit multiple is 6.31× and
not 10× — the answer and the evidence are there. Read it before overturning anything.
