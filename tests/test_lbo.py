import pytest

from bluebook.assumptions import SCENARIOS
from bluebook.comps import greggs_trading_multiples
from bluebook.inputs.greggs import GREGGS_HISTORICALS
from bluebook.lbo import (
    SPONSOR_ENTRY_LEVERAGE,
    SPONSOR_IRR_HURDLE,
    greggs_lbo_case,
    lbo_returns,
)
from bluebook.reference import build_model


# ---------------------------------------------------------------------------
# The brief's tests, verbatim
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# The rest of the guard rail
# ---------------------------------------------------------------------------

def test_non_positive_entry_equity_is_rejected():
    with pytest.raises(ValueError, match="entry equity"):
        lbo_returns(entry_ev=1000.0, entry_debt=1000.0, exit_ev=1400.0,
                    exit_debt=300.0, years=5)


def test_a_zero_year_hold_is_rejected():
    with pytest.raises(ValueError, match="years"):
        lbo_returns(entry_ev=1000.0, entry_debt=600.0, exit_ev=1400.0,
                    exit_debt=300.0, years=0)


def test_a_flat_hold_returns_a_nil_irr():
    r = lbo_returns(entry_ev=1000.0, entry_debt=600.0, exit_ev=1000.0,
                    exit_debt=600.0, years=5)
    assert r.money_multiple == pytest.approx(1.0)
    assert r.irr == pytest.approx(0.0)


def test_returns_carry_the_two_equity_values_they_were_built_from():
    r = lbo_returns(entry_ev=1000.0, entry_debt=600.0, exit_ev=1400.0,
                    exit_debt=300.0, years=5)
    assert r.entry_equity == pytest.approx(400.0)
    assert r.exit_equity == pytest.approx(1100.0)


# ---------------------------------------------------------------------------
# The Greggs case
# ---------------------------------------------------------------------------

def _base_case():
    drivers = SCENARIOS["Base"]
    model = build_model(GREGGS_HISTORICALS, drivers)
    entry_ev = greggs_trading_multiples(GREGGS_HISTORICALS).ev
    return greggs_lbo_case(model, drivers, GREGGS_HISTORICALS, entry_ev)


def test_the_stated_conventions_are_pinned():
    """Both are judgement, not sourced figures, so the only thing a test can do
    is pin them — and pinning them is what makes a later change to either a
    visible change rather than a silent one. The mutation sweep found both
    could move ±1% undetected without this."""
    assert SPONSOR_ENTRY_LEVERAGE == pytest.approx(4.0)
    assert SPONSOR_IRR_HURDLE == pytest.approx(0.20)


def test_the_entry_debt_is_the_stated_multiple_of_entry_ebitda():
    case = _base_case()
    assert case.entry_debt == pytest.approx(SPONSOR_ENTRY_LEVERAGE * case.entry_ebitda)
    # Absolute, so the assertion above cannot pass tautologically if the
    # leverage convention moves: 4.0 x £351.2m.
    assert case.entry_debt == pytest.approx(1404.8)
    assert case.entry_financial_debt == pytest.approx(955.0)


def test_lease_liabilities_are_inside_entry_debt_not_beside_it():
    """The lease-heavy constraint, made arithmetic.

    £449.8m of the entry debt is already committed before the sponsor
    borrows anything, so the incremental financial debt is the balance, not
    the whole 4.0x.
    """
    case = _base_case()
    last = GREGGS_HISTORICALS[-1]
    assert case.entry_leases == pytest.approx(last.lease_liabilities.value)
    assert case.entry_financial_debt == pytest.approx(
        case.entry_debt - case.entry_leases
    )
    assert case.entry_leases / case.entry_ebitda == pytest.approx(1.2807, abs=1e-4)


def test_there_is_no_net_deleveraging_across_the_hold():
    """The headline finding of the LBO docstring, which had no assertion behind it.

    The docstring says financial debt "ends at £967.1m, £12.1m HIGHER than the
    £955.0m drawn at entry", that total debt including leases is £118.2m higher
    at exit, and that the money multiple is therefore entirely an EBITDA-growth
    story. In a project whose cardinal sin is a comment a later change falsifies,
    the headline claim needs a line behind it.
    """
    case = _base_case()
    assert case.financial_debt_closing[-1] > case.entry_financial_debt
    assert case.financial_debt_closing[-1] - case.entry_financial_debt == pytest.approx(
        12.05, abs=0.05
    )
    assert case.exit_debt - case.entry_debt == pytest.approx(118.22, abs=0.05)
    # And the counterfactual that makes "entirely EBITDA growth" precise: held at
    # entry debt, the money multiple would have been HIGHER, so de-gearing
    # contributed nothing and in fact worked against the return.
    flat_debt_mm = (case.exit_ev - case.entry_debt) / case.returns.entry_equity
    assert flat_debt_mm == pytest.approx(1.9375, abs=1e-3)
    assert flat_debt_mm > case.returns.money_multiple


def test_the_peak_and_the_drawn_and_swept_amounts_are_pinned():
    """The £1,098.0m FY2028 peak and the £143.0m drawn across FY2026-28."""
    case = _base_case()
    assert max(case.financial_debt_closing) == pytest.approx(1097.96, abs=0.05)
    assert case.financial_debt_closing.index(max(case.financial_debt_closing)) == 2
    drawn = -sum(c for c in case.cash_swept if c < 0.0)
    swept = sum(c for c in case.cash_swept if c > 0.0)
    assert drawn == pytest.approx(142.97, abs=0.05)
    assert swept == pytest.approx(130.91, abs=0.05)
    assert swept < drawn


def test_the_scenario_returns_are_pinned():
    """Bear 0.87x/-2.73% and Bull 2.89x/23.66%, both quoted in the docstring.

    Bear losing capital is the asymmetry the sheet exists to show, so it is the
    one number here that must not be allowed to drift silently.
    """
    entry_ev = greggs_trading_multiples(GREGGS_HISTORICALS).ev
    expected = {
        "Bear": (0.8707, -0.02731),
        "Base": (1.8194, 0.12716),
        "Bull": (2.8914, 0.23658),
    }
    for name, (mm, irr) in expected.items():
        drivers = SCENARIOS[name]
        model = build_model(GREGGS_HISTORICALS, drivers)
        case = greggs_lbo_case(model, drivers, GREGGS_HISTORICALS, entry_ev)
        assert case.returns.money_multiple == pytest.approx(mm, abs=1e-3), name
        assert case.returns.irr == pytest.approx(irr, abs=1e-4), name
    # Only Bull clears the hurdle; Bear loses capital outright.
    assert expected["Bear"][0] < 1.0
    assert expected["Base"][1] < SPONSOR_IRR_HURDLE
    assert expected["Bull"][1] > SPONSOR_IRR_HURDLE


def test_a_control_premium_and_fees_both_reduce_the_return():
    """The two omissions that flatter the LBO, quantified.

    A 30% control premium costs surprisingly little — 1.82x/12.72% becomes
    1.66x/10.65% — because the exit is struck at the multiple PAID, so a higher
    entry multiple raises the exit EV proportionately and the premium largely
    self-cancels. That self-cancellation is an artefact of the no-expansion
    convention, not real insulation from overpaying, and the test asserts it
    explicitly so the mechanism is on the record.
    """
    drivers = SCENARIOS["Base"]
    model = build_model(GREGGS_HISTORICALS, drivers)
    g = greggs_trading_multiples(GREGGS_HISTORICALS)
    base = greggs_lbo_case(model, drivers, GREGGS_HISTORICALS, g.ev)

    premium_ev = g.market_cap * 1.30 + g.net_debt_incl_leases
    with_premium = greggs_lbo_case(model, drivers, GREGGS_HISTORICALS, premium_ev)
    assert with_premium.returns.money_multiple == pytest.approx(1.6585, abs=1e-3)
    assert with_premium.returns.irr == pytest.approx(0.10648, abs=1e-4)
    assert with_premium.returns.irr < base.returns.irr

    # Self-cancellation: a 30% higher equity price cuts the money multiple by
    # only ~9%, not ~30%, because the exit multiple rises with the entry one.
    assert with_premium.entry_multiple / base.entry_multiple == pytest.approx(
        1.2497, abs=1e-3
    )
    assert with_premium.returns.money_multiple / base.returns.money_multiple > 0.88

    # Fees at 2% of entry EV, funded from the equity cheque. A convention.
    fees = 0.02 * premium_ev
    with_fees_mm = with_premium.returns.exit_equity / (
        with_premium.returns.entry_equity + fees
    )
    assert fees == pytest.approx(60.14, abs=0.05)
    assert with_fees_mm == pytest.approx(1.5985, abs=1e-3)
    assert with_fees_mm ** 0.2 - 1.0 == pytest.approx(0.09836, abs=1e-4)
    assert with_premium.returns.irr - (with_fees_mm ** 0.2 - 1.0) == pytest.approx(
        0.00812, abs=1e-4
    )


def test_the_lbo_consumes_the_same_cash_flows_as_the_dcf():
    """Why this sheet cannot corroborate the DCF, asserted rather than asserted-away.

    The docstring used to claim an LBO screen tests whether a DCF's cash flows
    are real. It cannot, because it calls the same function. This test makes the
    dependency explicit so nobody restores the claim.
    """
    from bluebook.valuation import unlevered_fcf

    drivers = SCENARIOS["Base"]
    model = build_model(GREGGS_HISTORICALS, drivers)
    case = greggs_lbo_case(
        model, drivers, GREGGS_HISTORICALS, greggs_trading_multiples(GREGGS_HISTORICALS).ev
    )
    fcf = unlevered_fcf(model, drivers)
    # Reconstruct the first year's sweep from the DCF's own FCF path.
    expected = (
        fcf[0]
        + model.leases.additions[0]
        - model.leases.principal_paid[0]
        - model.leases.interest[0] * (1.0 - drivers.tax_rate)
        - case.interest_rate * case.entry_financial_debt * (1.0 - drivers.tax_rate)
    )
    assert case.cash_swept[0] == pytest.approx(expected)


def test_financial_debt_rises_for_three_years_before_it_falls():
    """The distribution-centre programme is still running at entry.

    Unlevered FCF is negative in FY2026 and FY2027, so the sponsor funds the
    capex rather than sweeping it, and net financial debt peaks in FY2028.
    An LBO on this business is a bet on the back half of the hold.
    """
    case = _base_case()
    closing = case.financial_debt_closing
    assert closing[0] > case.entry_financial_debt
    assert closing[1] > closing[0]
    assert closing[2] > closing[1]
    assert closing[3] < closing[2]
    assert closing[4] < closing[3]


def test_the_exit_takes_no_credit_for_multiple_expansion():
    case = _base_case()
    assert case.exit_multiple == pytest.approx(case.entry_multiple)
    assert case.exit_ev == pytest.approx(case.exit_multiple * case.exit_ebitda)


def test_exit_debt_carries_the_grown_lease_book():
    """The lease liability is £106.2m larger at exit than at entry, because
    the model opens more shops than it closes. A sponsor deleveraging the
    financial debt is partly running to stand still."""
    case = _base_case()
    model = build_model(GREGGS_HISTORICALS, SCENARIOS["Base"])
    assert case.exit_leases == pytest.approx(model.leases.closing_liability[-1])
    assert case.exit_leases - case.entry_leases == pytest.approx(106.2, abs=0.1)
    assert case.exit_debt == pytest.approx(
        case.financial_debt_closing[-1] + case.exit_leases
    )


def test_the_base_case_falls_short_of_a_sponsor_hurdle():
    """The headline finding of the sheet.

    Entry at the traded multiple, exit at the same multiple, five years of the
    model's own Base case: 1.82x and 12.7%. That is a long way below the 20%
    a buyout fund underwrites to, and it is not a leverage problem that more
    debt would fix — see the module docstring.
    """
    case = _base_case()
    assert case.returns.money_multiple == pytest.approx(1.8194, abs=1e-3)
    assert case.returns.irr == pytest.approx(0.12716, abs=1e-4)
    assert case.returns.irr < SPONSOR_IRR_HURDLE


def test_reaching_the_hurdle_needs_multiple_expansion_past_the_peer_median():
    """What it would take, stated rather than asserted.

    Holding the model's Base operating case, the exit multiple that clears a
    20% IRR is 8.22x against an entry at 6.85x — 1.37 turns of expansion. That
    is above the peer median of 7.54x but still inside the peer range, so the
    case is not impossible; it is simply underwritten on the exit multiple
    rather than on the cash flows.
    """
    from bluebook.comps import PEERS, multiples

    case = _base_case()
    peer = multiples(PEERS)["ev_ebitda"]
    required_equity = case.returns.entry_equity * (1 + SPONSOR_IRR_HURDLE) ** case.years
    required_multiple = (required_equity + case.exit_debt) / case.exit_ebitda
    assert required_multiple == pytest.approx(8.2245, abs=1e-3)
    assert required_multiple > case.entry_multiple
    assert peer["median"] < required_multiple < peer["max"]


def test_the_case_is_reproducible_from_its_own_recorded_inputs():
    case = _base_case()
    rebuilt = lbo_returns(
        entry_ev=case.entry_ev, entry_debt=case.entry_debt,
        exit_ev=case.exit_ev, exit_debt=case.exit_debt, years=case.years,
    )
    assert rebuilt.money_multiple == pytest.approx(case.returns.money_multiple)
    assert rebuilt.irr == pytest.approx(case.returns.irr)


def test_every_scenario_builds_without_a_negative_equity_cheque():
    entry_ev = greggs_trading_multiples(GREGGS_HISTORICALS).ev
    for name, drivers in SCENARIOS.items():
        model = build_model(GREGGS_HISTORICALS, drivers)
        case = greggs_lbo_case(model, drivers, GREGGS_HISTORICALS, entry_ev)
        assert case.returns.entry_equity > 0.0, name
        assert case.returns.exit_equity > 0.0, name
