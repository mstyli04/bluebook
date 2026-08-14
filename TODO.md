# Bluebook — what is left to do

**Updated 2026-08-13**, after the independent review of Tasks 13-16. Repo: `~/bluebook`,
branch `build-model`. 305 tests passing, tree clean.

This file is the handoff. It is written for whoever picks this up — including a future
Claude session with no memory of building it.

---

## 1. Where the project stands

**All sixteen tasks are built and independently reviewed.** Tasks 13–16 were reviewed
on 13 Aug 2026 by two agents working in parallel, one on the sheet writers and one on
the test infrastructure. Both found real defects; everything they rated Major is fixed
and verified, and section 4 lists what was deliberately left.

The review earned its keep, and the way it did is worth recording: **both reviewers
independently found the same Major defect, and it was in the test infrastructure written
to prevent exactly that class of thing.** Nothing in the suite failed when a check on the
Checks sheet read FALSE — and the coverage audit excluded that sheet on the strength of a
comment claiming it "had its own tests", which no test did. Set `TERMINAL_SHARE_CEILING`
to 0.50 and 298 tests passed while the delivered workbook showed a FALSE on tab two. A
self-review had already been run over this code and did not find it.

The model is complete and verified. The workbook is complete and shipped.

| | Bear | Base | Bull |
|---|---|---|---|
| Implied share price | 624.68p | **1,506.50p** | 2,560.65p |
| Enterprise value | £1,044.2m | £1,947.9m | £3,028.2m |
| Terminal value / EV | 95.2% | 94.0% | 93.1% |

WACC 7.7311%. Peer median EV/EBIT 13.4277×. FY2025 net debt including leases £404.0m.
Peak borrowings £190.2m / £207.1m / £210.9m at FY2028.

**Verification as it now stands.** The generated workbook is recalculated through headless
LibreOffice and compared against the Python model across **730 cells per scenario** in all
three scenarios: 720 at 1e-9 (worst observed difference 5.0e-12) and 10 — the peer tie
rows — at £0.01, which is as close as a market cap transcribed to £0.001m can tie. All 863
formulas parse into a 2,495-edge reference graph over 1,085 nodes with zero cycles,
asserted exactly (not as a floor) on every run. Eight of eight Checks rows read TRUE in all
three scenarios, now asserted by `tests/test_checks_sheet.py` rather than by inspection,
along with the sheet's ability to read FALSE at all. Zero error cells.

### The plan and the ledger

- **Plan:** `docs/superpowers/plans/2026-08-03-bluebook-model.md`, amended in place as
  findings came in — but only through Task 12. **It is stale for Task 14** (see section 4);
  read it as the spec for Tasks 1-12 and read the commit messages for 13-16.
- **Spec:** `docs/superpowers/specs/2026-08-03-bluebook-dcf-design.md`.
- **Ledger:** `.superpowers/sdd/2026-08-03-bluebook-model/progress.md` — git-ignored, and
  the single most useful file here. Every ruling and its reasoning.
- **The circularity record:** `docs/superpowers/spike-circularity.md`. Non-obvious and
  load-bearing.

---

## 2. What Task 15 did

The plan's Task 15 was mostly already built by Task 12, so this was an audit rather than a
build, and the audit found a real gap.

`_compare_against_reference` now records every address it asserts, and a coverage test
subtracts that set from every computed cell on the nine calculation sheets. Anything left
must appear in `CROSS_CHECK_EXEMPTIONS` with a stated reason. This is why counting table
entries would not have worked: the fifty sensitivity-grid cells are checked at literal
addresses and appear in no table.

**Twelve cells were mutated by 1% against the pre-Task-15 commit and eleven failed
nothing.** The largest family was the peer table — `PEER_CELLS` checked ratios, and a ratio
pins only its own two operands, so a wrong peer share price, shares outstanding, lease
liability or minority interest left every derived multiple agreeing. Also unchecked: the
comps-implied share prices (which are what the football field's comps bar draws), the
football field's own bars, the peer capital-intensity statistics, the three discounts to
the peer median, Sensitivity's two "for comparison" links, and three LBO leaves. All are
now checked against the modules that own them.

One correction worth keeping: the peer tie rows **cannot** hold to 1e-9 and are asserted at
`comps.py`'s own 0.01 band, because each market capitalisation is transcribed rounded to
£0.001m. Forcing them into the 1e-9 family would have been wrong.

Everything still outside the comparison is a working that feeds a checked total. That
reasoning was measured, not asserted: fourteen mutations, one from every exempt family, all
caught.

Also added: an error-value scan (`#REF!`, `#DIV/0!`, `Err:522`…) over every cell of every
sheet, which the comparison could not provide because it only sees cells it was told about.

---

## 3. What Task 16 did

`tests/test_conventions.py` — the four house rules, checked against the finished `.xlsx`
rather than the code that wrote it, so a writer that bypassed `SheetWriter` would fail
them. Hardcoded numbers only on the five sheets `HARDCODE_ALLOWED` names (imported, never
redefined); inputs blue and formulas not; a non-empty title in A1; and no circular
references.

**The acyclicity test is the one nothing else covered.** Acyclicity had been proved once by
a reviewer parsing formulas by hand, but that proof lived in a transcript, and nothing in
the suite would have failed if an average-basis interest row returned — the failure is
silent, because LibreOffice returns a plausible wrong number rather than an error. Two
tests guard the guard: one asserting the graph's exact size (a regex that stopped expanding
ranges drops 66 edges and would otherwise pass a floor, leaving the acyclicity test blind to
the very "cycle through one cell of a MIN(...) range" that range expansion exists to catch),
and one that reinstates the average-basis row the spike rejected and requires the finder to
report the cycle.

**It also corrected the financing disclosure, which was quoting the measure the plan
explicitly rules out.** Both the Cover note and the peak-leverage check read gross
borrowings / EBITDA at ~0.5× — a lease-free numerator against a post-IFRS 16 denominator
already credited for those leases, and the most flattering of the defensible measures.
Both now use lease-inclusive net debt / EBITDA: 1.30× Bull, 1.51× Base, 1.78× Bear, ceiling
moved 1.0× → 2.0×. The gross figure stays on the sheet as a labelled memo so the gap is
visible. The check was mutation-tested and reads FALSE at +15% lease liabilities. No
valuation output moved — this was disclosure, not arithmetic.

Also: `README.md`, `dist/greggs_model.xlsx` committed and verified by recalculation, and
the `freeze_panes` deferred minor closed (the Cover is now unfrozen and wrapped with
explicit row heights; every other sheet keeps its C3 split, and a test pins both halves).

---

## 4. What is left

1. **Deliberately not fixed from the 13 Aug review.** None is load-bearing; each is
   recorded so the next reader does not have to rediscover it.
   - `_REFERENCE` in `test_conventions.py` under-matches two formula shapes that this
     workbook does not currently contain: lowercase column letters (`=c5+d6`, no
     `re.IGNORECASE`) and fully-qualified ranges (`'Sheet'!C5:'Sheet'!C7` drops the
     interior). Latent — `formulas.cell_range` never emits either — but it would make the
     acyclicity proof partial if a writer ever did.
   - Ten reported cells on `Historicals` (C38:C41, D39:D41, E39:E41 — capex, lease
     principal repaid, ROU additions, dividends) are referenced by no formula and asserted
     by nothing. They are transcription, not computation, but they are on a sheet a reader
     reads.
   - The coverage audit starts at row 3, so the 30 year-header link formulas on row 2 are
     outside it; only `IS!F2` and `BS!J2` are asserted anywhere. A wrong column link there
     is cosmetic but invisible.
   - `scripts/generate.py` has no test. It behaves as documented, including raising
     `ValueError` on an unknown scenario, but as an uncaught traceback.
   - `LBO!C35` ("exit EV/EBITDA that would clear the hurdle") is checked against the same
     identity arranged differently, so it would not catch an algebraically equivalent
     rearrangement. Every operand is independently pinned; the docstring says so.
   - `TEXT_FORMAT = 'General'` is a no-op and the name overstates it.
   - **The plan is stale for Task 14** and TODO.md used to tell the next reader it was the
     current spec. It still requires four football-field bars including the exit multiple,
     still requires a `sheet_cover.py` that does not exist (the Cover lives in `build.py`),
     and still names the 90% terminal bound. Every deviation was the right call and each is
     explained in `07398c2`'s commit message — but the plan was amended in place for Tasks
     4, 8, 11 and 12 and was not for 14. **Read the plan as the spec for Tasks 1–12 only.**

2. **The distribution plan is DONE (14 Aug 2026).**
   - Public repo: **https://github.com/mstyli04/bluebook**, `master` default, README as the
     front door, `dist/greggs_model.xlsx` committed.
   - `docs/football-field.png`, rendered by `scripts/render_football_field.py` from the
     SHIPPED workbook's own recalculated values rather than rebuilt from the model beside
     it, so the picture cannot drift from the artefact.
   - Portfolio row **03** on `cinematic-hero` (live at michaelstylianou.vercel.app), with
     CHART, DOWNLOAD and GITHUB links; rows 03-10 shifted down one, Placement Scout and
     Paper Alpha keep 01 and 02.
   - Both CVs carry a Bluebook Projects entry — first on the job version, third on the
     postgrad-AI version so the AI projects still lead — and "Financial Modelling
     (3-statement, DCF, LBO, comps)" was already in Key Skills from 13 Aug. PDFs
     re-exported; both still 3 pages. Backups in `Michael CVs/backup_20260814/`.

**Nothing is outstanding on this project.** What remains in section 5 is a triaged list of
known minors, none load-bearing, kept so nobody rediscovers them.

---

## 5. Deferred minors, for the final whole-branch review

Accumulated across the build and deliberately not fixed. None is load-bearing; each was
judged not worth its own fix round at the time. The final review should triage which must
be closed before this is shown to anyone.

**Data and disclosure**
- Three of five peer EBITDAs are build-ups rather than printed subtotals (Wetherspoon, M&B,
  Whitbread). All five EBITs are printed, and the derived exit multiple depends only on the
  median EV/EBIT, so the load-bearing statistic rests entirely on printed figures.
- No page references exist for any peer figure. Greggs' own figures all have them.
- The impairment asymmetry understates the derived exit multiple by 3.5–6.7%. Disclosed,
  not adjusted — adjusting needs the Task 3 impairment convention reopened.
- `GREGGS_FY2025_LEASE_INTEREST = 16.7` is the last underived number in `assumptions.py`, a
  bare literal with a page citation because `finance_costs` bundles lease interest. It now
  sets the blended cost of debt and therefore the WACC, so it does more work than when it
  was first written. Closing it properly needs a `lease_interest` field on `HistoricalYear`.
- SSP's printed EBIT of 269.1 is an APM reconciliation-table subtotal, not an
  income-statement face line.
- An SSP amortisation figure of (10.4) was seen in the announcement and never located;
  deliberately not attributed to a table.

**Model**
- The share count is weighted-average diluted, an EPS construct. Period-end diluted is the
  more standard divisor for an implied share price. Sensitivity ~16p per 1%. Needs a
  sourced figure.
- No finance income on cash is modelled (~£2m/yr pre-tax, ~£1.5m after tax). No driver
  exists.
- The ROU mirror of the excess-PP&E tax shield is not applied (~3p/share).
- `ppe_depreciation_rate` includes impairment and is used as the perpetual asset decay
  rate, so the perpetuity assumes the estate is impaired at FY2025's rate forever.
  Conservative.
- Terminal EBITDA margin is left at the FY2030 driver rather than normalised.
- `schedules/leases.py` docstring says the additions coefficient is `k ≈ 0.093`; the true
  value is 0.09232. Zero consequence — the shipped constant comes from the joint solve.

**Tests and code**
- The ROU-side tests are closed-form and would inherit a blind spot if `leases()` ever
  gained a capex split.
- `test_iterated_schedule_agrees_with_the_closed_form` does not fire under value mutations,
  since both methods share the mutated input. It guards method-versus-formula only, and
  says so.
- `check_debt_never_negative` is a regression guard rather than a live test — closing
  borrowings cannot go negative by construction while the repayment formula caps at
  `debt_opening`. Worth keeping on those terms; not evidence the model was checked.
- The C3-toggle test's tail assertion compares two Python models rather than the file.
  Harmless; the 72-row comparison above it already pins the file.
- `TEXT_FORMAT = 'General'` is a no-op and the name overstates it.
- Fifteen `other_assets` cell comparisons carry no information (held flat at a reported nil).
- Three defensive branches are unexercised by any scenario: the `MIN` repayment cap, the
  `MAX` tax floor, the `MAX` dividend floor. Covered on the Python side.
- `test_conventions.py` builds the reference graph twice (once per test that needs it).
  Cheap, but a module-scoped fixture would be tidier.

---

## 6. Things worth knowing before you touch anything

**The model modules are closed.** `reference.py`, `valuation.py`, `comps.py`, `lbo.py`,
`assumptions.py`, `inputs/`, `schedules/`, `lease_rate.py`. Twelve tasks of scrutiny sit
behind them, including two independent full recomputations of the valuation and 52 injected
mutations with zero escapes. Work in `src/bluebook/workbook/` and `tests/`.

**Prose drifting from code is this project's dominant defect.** It appeared in at least nine
places across twelve tasks, and Task 16 found a tenth — the Cover and the Checks sheet both
quoting a leverage basis the plan had ruled out. **No test catches this class.** The durable
fix, every time, was to *derive* facts rather than restate them.

**Tests that pass while proving nothing are the second theme.** Six instances now, the
latest being the peer table: a hundred cells of transcribed market data, every ratio over
them checked, and the transcription itself pinned by nothing. Ask of every test: *would this
fail if the thing it names were broken?* If the answer is not obviously yes, mutate
something and find out — that is how both of the last two real defects were found.

**Numbers in reports and comments must be recomputed, not copied.** Diagnostic numbers get
less scrutiny than model numbers while often doing heavier work. The 490-formula/1,050-edge
figure quoted in the Task 12 ledger entry is a good example: still true of the workbook as
it stood then, badly misleading as a description of the workbook now (862 and 2,464).

**Every ruling has its reasoning in the ledger.** If something looks arbitrary — why opening
balances, why beta 0.90, why a terminal anchor of 40.6%, why the exit multiple is 6.31× and
not 10× — the answer and the evidence are there. Read it before overturning anything.
