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

**Decision:** `INTEREST_BASIS = "average"`

**Rationale:** LibreOffice headless honours the `wb.calculation.iterate`
settings openpyxl writes and converges the circular interest/debt formula to
the correct fixed point, so the debt schedule can charge interest on the
average of opening and closing balances rather than falling back to opening
balances only.
