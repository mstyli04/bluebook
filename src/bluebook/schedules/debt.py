"""Debt schedule: revolving credit facility, interest on the opening balance.

Pure function of opening debt, opening cash, exogenous pre-financing cash
generation and the debt drivers. Does not import the other schedule modules
(working_capital, fixed_assets, leases) — each schedule is independent and
gets wired together downstream in the linked three-statement model.

--------------------------------------------------------------------------
Interest basis — the spike decision, and why it was reversed
--------------------------------------------------------------------------
Interest on the revolver can be charged either on the *opening* debt balance
(no circularity — interest is fixed before repayment/draw is known) or on
the *average* of opening and closing balances (circular — the closing
balance depends on interest, which depends on the closing balance).

``INTEREST_BASIS`` was originally ``"average"``, on the strength of Task 2's
spike (``docs/superpowers/spike-circularity.md``): headless LibreOffice does
honour the ``wb.calculation.iterate`` settings openpyxl writes, and it did
converge that spike's circular formula to its analytical fixed point (within
~3e-6 of 1500/19).

**Owner ruling, Task 12 fix round 1: the basis is now ``"opening"``.** The
spike's conclusion was true but did not generalise, and Task 12 established
where it stops. The spike's circularity was a *single* two-cell loop.
Measured against LibreOffice 24.2.7, iterative calculation resolves exactly
that and no more:

* a **branched** circular group — one cell inside the loop read by two cells
  that are also inside it — converges with the second branch frozen at the
  value it held on the seeding pass, so two cells containing the identical
  formula end up disagreeing;
* a **chain** of circular groups resolves only the first link, leaving each
  later group reading a frozen input.

A five-year average-balance debt schedule is inherently such a chain — one
circular group per year, linked by the closing balance — so on the average
basis the recalculated workbook was exact in FY2026 and wrong in FY2027-30,
unfixably: raising ``iterateCount`` to 10,000, tightening ``iterateDelta`` to
1e-12 and recalculating seven times over all returned bit-identical answers,
and rearranging the block into a single simple chain per year bought FY2026
alone. Both LibreOffice behaviours are pinned in
``tests/test_libreoffice_iteration_limits.py``, twelve cells apiece.

On the opening basis the workbook is completely acyclic: interest depends only
on the prior year's closing balance, so Task 15 can cross-check every cell of
the financing block rather than having to exclude the one block whose
construction was the reason for choosing "average" in the first place. The
cost is real and worth naming: charging interest on the opening balance
understates it in a year of rising debt, by roughly half a year's interest on
the increase. It is common practice in production models for exactly this
reason, and it is now a measured decision rather than a fallback.

Both bases remain implemented: the Python side is cheap, and the comparison
test in tests/test_debt_schedule.py needs both to exist to be meaningful. The
"average" solve deliberately mirrors Excel's iterative calculation —
fixed-point iteration seeded at the opening balance, not a closed-form solve
— even though the closed form is available (see the spike's analytical fixed
point). On the "opening" basis the same loop converges on its first pass.
"""

from __future__ import annotations

from dataclasses import dataclass

from bluebook.assumptions import Drivers

# Which basis the WORKBOOK uses, and therefore which one `reference.py` runs so
# the two agree. "opening" by owner ruling — see the module docstring above for
# the LibreOffice measurements that reversed the spike's "average".
INTEREST_BASIS = "opening"

MAX_ITERATIONS = 50
CONVERGENCE_TOLERANCE = 1e-9


class DebtScheduleConvergenceError(RuntimeError):
    """Raised when a year's fixed-point iteration fails to converge.

    Deliberately not swallowed: a partially-converged closing balance would
    silently feed a wrong interest figure into the P&L and every downstream
    statement, and Task 15's Python-vs-workbook cross-check would then be
    comparing a converged Excel answer against an unconverged Python one.
    """


@dataclass(frozen=True)
class DebtSchedule:
    opening: list[float]
    interest: list[float]
    repayment: list[float]
    revolver_draw: list[float]
    closing: list[float]
    cash_balance: list[float]


def _solve_year(
    opening_year_debt: float,
    cash_before_interest: float,
    minimum_cash: float,
    rate: float,
    basis: str,
) -> tuple[float, float, float, float]:
    """Fixed-point solve one year's interest/repayment/draw/closing debt.

    Seeds closing debt at the opening balance and iterates until the change
    in closing debt falls below CONVERGENCE_TOLERANCE or MAX_ITERATIONS is
    reached — mirroring Excel's iterative calculation (see module
    docstring). On the "opening" basis this converges on the first pass
    (interest never depends on the closing-debt guess), but is run through
    the same loop for a single code path.

    Returns (interest, repayment, revolver_draw, closing).
    """
    closing_guess = opening_year_debt
    previous_guess = closing_guess
    for _ in range(MAX_ITERATIONS):
        avg_debt = (
            (opening_year_debt + closing_guess) / 2 if basis == "average" else opening_year_debt
        )
        interest = avg_debt * rate
        cash_before_debt_service = cash_before_interest - interest

        if cash_before_debt_service >= minimum_cash:
            repayment = min(opening_year_debt, cash_before_debt_service - minimum_cash)
            revolver_draw = 0.0
        else:
            repayment = 0.0
            revolver_draw = minimum_cash - cash_before_debt_service

        new_closing = opening_year_debt - repayment + revolver_draw

        if abs(new_closing - closing_guess) < CONVERGENCE_TOLERANCE:
            return interest, repayment, revolver_draw, new_closing

        previous_guess = closing_guess
        closing_guess = new_closing

    raise DebtScheduleConvergenceError(
        f"debt schedule failed to converge after {MAX_ITERATIONS} iterations "
        f"(basis={basis!r}, opening_debt={opening_year_debt}, "
        f"last change={abs(closing_guess - previous_guess)!r}, "
        f"tolerance={CONVERGENCE_TOLERANCE})"
    )


def debt_schedule(
    opening_debt: float,
    opening_cash: float,
    cash_generated: list[float],
    drivers: Drivers,
    basis: str,
) -> DebtSchedule:
    """Roll forward the revolving credit facility, one year per entry in
    ``cash_generated`` (pre-financing cash generation for that year, i.e.
    before interest, repayment or revolver draw).

    Each year: cash available before debt service is opening cash plus that
    year's cash generation, less interest. If that clears
    ``drivers.minimum_cash``, the surplus repays debt down to zero (never
    below); if it doesn't, the revolver draws exactly enough to hold cash at
    ``drivers.minimum_cash``. Interest is charged on opening debt (basis=
    "opening") or on the average of opening and closing debt (basis=
    "average"), the latter solved by fixed-point iteration since closing
    debt depends on interest and interest depends on closing debt.
    """
    if basis not in {"average", "opening"}:
        raise ValueError(f"basis must be 'average' or 'opening', got {basis!r}")

    opening: list[float] = []
    interest: list[float] = []
    repayment: list[float] = []
    revolver_draw: list[float] = []
    closing: list[float] = []
    cash_balance: list[float] = []

    year_opening_debt = opening_debt
    year_opening_cash = opening_cash
    for year_cash_generated in cash_generated:
        cash_before_interest = year_opening_cash + year_cash_generated
        year_interest, year_repayment, year_revolver_draw, year_closing_debt = _solve_year(
            year_opening_debt,
            cash_before_interest,
            drivers.minimum_cash,
            drivers.interest_rate_debt,
            basis,
        )
        year_cash_balance = (
            cash_before_interest - year_interest - year_repayment + year_revolver_draw
        )

        opening.append(year_opening_debt)
        interest.append(year_interest)
        repayment.append(year_repayment)
        revolver_draw.append(year_revolver_draw)
        closing.append(year_closing_debt)
        cash_balance.append(year_cash_balance)

        year_opening_debt = year_closing_debt
        year_opening_cash = year_cash_balance

    return DebtSchedule(opening, interest, repayment, revolver_draw, closing, cash_balance)
