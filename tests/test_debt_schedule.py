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
