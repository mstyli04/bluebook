# Spike: circular reference resolution via LibreOffice iterative calculation

**Date:** 2026-08-03

**Command run:**

```
python3 -m pytest tests/test_spike_circularity.py -v
```

**Result:** PASSED

```
tests/test_spike_circularity.py::test_libreoffice_resolves_circular_reference PASSED [100%]
```

**Literal observed values** (captured by calling `recalc_values()` directly on
the same workbook construction used in the test, to record the raw floats
rather than just the pass/fail boundary):

```
B4 (interest) = 8.947365625
B5 (closing debt) = 78.947365625
```

For reference, the exact analytical fixed point of
`closing = 100 - 30 + 0.10 * (100 + closing) / 2` is `closing = 1500/19 =
78.94736842105263`, `interest = 8.94736842105263`. The observed values differ
from the analytical fixed point by about 3e-6, consistent with LibreOffice's
iterative solver converging under the `iterateCount = 100` /
`iterateDelta = 0.0001` settings openpyxl wrote into the workbook.

**Decision (2026-08-03):** `INTEREST_BASIS = "average"`

**Rationale:** LibreOffice headless honours the `wb.calculation.iterate`
settings openpyxl writes and converges the circular interest/debt formula to
the correct fixed point, so the debt schedule can charge interest on the
average of opening and closing balances rather than falling back to opening
balances only.

---

## Amendment, 2026-08-06 (Task 12): the conclusion did not generalise, and the decision is reversed

**Decision now:** `INTEREST_BASIS = "opening"` (owner ruling, Task 12 fix round 1).

Everything recorded above is still true. It is also narrower than it reads. The
spike measured **one** circular group of **two** cells, and that is the only
shape it licenses. Task 12 built the real five-year debt schedule on the average
basis and found LibreOffice 24.2.7 will not resolve it. Measured behaviour, with
`iterate = True`, `iterateCount = 100`, `iterateDelta = 0.0001`:

| Shape | What LibreOffice does |
| --- | --- |
| One simple cycle (the shape above) | Resolves it, to ~2e-6 of the analytical fixed point — the `iterateDelta` stopping slack |
| A **branched** cycle: one cell inside the loop read by two cells also inside it | Iterates one branch and leaves the other holding the value it took on the seeding pass. Two cells containing the *identical formula* `=S!F6` end up 2.75 apart, and the group settles on a self-consistent but wrong fixed point |
| A **chain** of cycles: several groups linked by a shared cell (one per forecast year) | Resolves the first link exactly and leaves every later group reading a frozen input |

On the real workbook that meant FY2026 exact (balance check `-9.6e-07`) and
FY2027–30 each solved with the prior year's closing debt frozen at its seed, so
borrowings read 25.0 — the FY2025 actual — for the rest of the forecast, and the
balance check ran to £178m.

**It is not a configuration problem.** `iterateCount` at 10,000 and
`iterateDelta` at 1e-12 return a bit-identical answer, as does recalculating the
saved file seven times in sequence: a stable wrong result, not an unfinished
one. Nor is it a layout problem. Task 12 built a version reshaping each year's
loop into a single simple chain — a signed `net_borrowing` row instead of paired
repayment/draw rows, an indirect-basis cash line, tax and dividends re-expressed
inline — and it bought FY2026 alone, at the cost of two duplicated expressions
and an income statement whose below-EBIT lines were links. It was reverted. A
five-year average-balance schedule **is** a chain of five circular groups; no
arrangement of rows removes that.

**Reproductions:** `tests/test_libreoffice_iteration_limits.py`, twelve cells
each, named for what LibreOffice does rather than what the test does. They fail
loudly with an explanatory message if a future LibreOffice fixes either
behaviour.

**What the reversal costs and buys.** Charging interest on the opening balance
understates it in a year of rising debt, by roughly half a year's interest on the
increase; the reason for preferring "average" has not gone away, only the ability
to compute it in this toolchain. What it buys is that the workbook is now
completely acyclic, so Task 15 cross-checks **every** cell of it — including the
financing block, which under "average" would have had to be excluded, and which
was the whole reason for choosing "average". Measured after the change: the
recalculated workbook reproduces `reference.py` to a worst absolute difference of
**5.0e-12** across 1,080 checked cells (72 line items x 5 years x 3 scenarios),
i.e. floating-point association only. The cross-check tolerance no longer has to
accommodate iterative convergence slack.

Iterative calculation is still written into the workbook. It costs nothing on an
acyclic file and turns a future reintroduced circularity into a converged answer
rather than `Err:522` — while emphatically **not** making such an edit safe, for
the reasons in the table above.

**The lesson worth carrying, not just the fix.** The spike was correct about what
it measured and was read as answering a broader question than it asked. A spike
that clears a mechanism on a two-cell case has not cleared it on the topology the
model will actually have; the gap between the two went unnoticed for ten tasks
because nothing exercised the real shape until the sheets existed.
