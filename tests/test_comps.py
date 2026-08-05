import pytest

from bluebook.assumptions import SCENARIOS
from bluebook.comps import (
    GREGGS_52_WEEK_HIGH,
    GREGGS_52_WEEK_LOW,
    GREGGS_SHARE_PRICE,
    PEERS,
    PRICE_OBSERVATION_DATE,
    Peer,
    exit_multiple_from_peers,
    greggs_trading_multiples,
    implied_value_from_comps,
    intensity_matched_multiple,
    multiples,
    post_ifrs16_multiple,
)
from bluebook.inputs.greggs import GREGGS_HISTORICALS
from bluebook.reference import build_model


# ---------------------------------------------------------------------------
# The brief's tests, verbatim
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# The peer set is an audit trail, not a table of numbers
# ---------------------------------------------------------------------------

def test_every_peer_ev_is_the_stated_build_up():
    """EV = market cap + net debt INCLUDING leases + minority interests.

    The build-up is the whole point of the sheet: an EV that did not tie to
    its own components would be a number nobody could re-derive from the
    filings, and the lease term is the one that puts it on the model's basis.
    """
    for p in PEERS:
        assert p.ev == pytest.approx(
            p.market_cap + p.net_debt_incl_leases + p.minority_interests
        ), p.name


def test_every_peer_market_cap_is_price_times_shares():
    for p in PEERS:
        assert p.market_cap == pytest.approx(p.share_price_pence / 100.0 * p.shares), p.name


def test_every_peer_carries_a_document_and_a_date():
    for p in PEERS:
        assert p.source.strip(), p.name
        # Sources name the announcement and the year end; the price date is
        # recorded once, on PRICE_OBSERVATION_DATE, because it is shared.
        assert "20" in p.source, p.name
    assert PRICE_OBSERVATION_DATE.strip()


def test_no_peer_carries_lease_liabilities_outside_ev():
    """Every peer's net debt is the lease-INCLUSIVE figure.

    Guards the one silent-mixing failure this sheet exists to avoid: a peer
    whose net debt excluded leases would show a spuriously low EV against an
    EBITDA that still had rent added back.
    """
    for p in PEERS:
        assert p.lease_liabilities > 0.0, p.name
        assert p.net_debt_incl_leases > p.lease_liabilities * 0.5, p.name


def test_peer_ebitda_exceeds_peer_ebit_by_the_da_charge():
    for p in PEERS:
        assert p.ebitda > p.ebit, p.name


# ---------------------------------------------------------------------------
# Mutation coverage on the transcribed figures
# ---------------------------------------------------------------------------
#
# A comps sheet whose tests only check that a median is ordered would not
# notice a transcribed figure being wrong, and a wrong peer figure is the most
# likely defect in this module. Every numeric field on every Peer is pinned
# below, through a ratio that depends on it:
#
#   share_price_pence, shares -> market_cap (test_every_peer_market_cap_...)
#   market_cap, net_debt_incl_leases, minority_interests -> ev (the tie test)
#   ev, ebitda                -> ev_ebitda
#   ev, ebit                  -> ev_ebit
#   market_cap, net_income    -> pe
#   net_debt_incl_leases, lease_liabilities -> lease_share
#
# so mutating any single one of them fails at least one assertion here.

_EXPECTED = {
    # SSP's earnings ratio is NEGATIVE and pinned anyway: pinning only its sign
    # left a ±1% mutation of its net income undetected, which the mutation
    # sweep found.
    #                        EV/EBITDA  EV/EBIT   mcap/NI    leases / net debt
    "SSP Group":            (5.2717,   13.4623,   -21.7607,  0.6840),
    "Domino's Pizza Group": (10.1197,  12.8683,    14.1797,  0.4576),
    "J D Wetherspoon":      (7.5376,   13.4277,    12.3046,  0.3606),
    "Mitchells & Butlers":  (6.4494,    9.1284,     9.5465,  0.3399),
    "Whitbread":            (8.7349,   14.4820,    19.5716,  0.8645),
}


def test_every_transcribed_peer_figure_is_pinned():
    assert set(_EXPECTED) == {p.name for p in PEERS}
    for p in PEERS:
        ev_ebitda, ev_ebit, earnings_ratio, lease_share = _EXPECTED[p.name]
        assert p.ev / p.ebitda == pytest.approx(ev_ebitda, abs=5e-5), p.name
        assert p.ev / p.ebit == pytest.approx(ev_ebit, abs=5e-5), p.name
        assert p.lease_liabilities / p.net_debt_incl_leases == pytest.approx(
            lease_share, abs=5e-5
        ), p.name
        assert p.market_cap / p.net_income == pytest.approx(
            earnings_ratio, abs=5e-4
        ), p.name


def test_exactly_one_peer_is_loss_making():
    assert [p.name for p in PEERS if p.net_income < 0.0] == ["SSP Group"]


# ---------------------------------------------------------------------------
# multiples()
# ---------------------------------------------------------------------------

def test_ev_ebit_is_a_much_tighter_spread_than_ev_ebitda():
    """The finding the sheet turns on.

    Post-IFRS 16 EV/EBITDA spans 5.27x to 10.12x across five names in one
    sector, because D&A/EBITDA spans 21% to 61%. On EV/EBIT the same five
    names span 9.13x to 14.48x. The EBITDA multiple is largely reporting
    capital intensity; the EBIT multiple is not.
    """
    m = multiples(PEERS)
    ebitda_spread = m["ev_ebitda"]["max"] / m["ev_ebitda"]["min"]
    ebit_spread = m["ev_ebit"]["max"] / m["ev_ebit"]["min"]
    assert ebitda_spread > 1.9
    assert ebit_spread < 1.6


def test_pe_excludes_the_loss_making_peer():
    """SSP's FY2025 statutory attributable result is a loss, so its P/E is not
    a multiple at all. It is dropped from the P/E statistics rather than
    allowed to drag a median negative, and the EV/EBITDA set keeps all five."""
    m = multiples(PEERS)
    assert m["pe"]["count"] == 4
    assert m["ev_ebitda"]["count"] == 5
    assert m["pe"]["min"] > 0.0


def test_multiples_reject_an_empty_peer_set():
    with pytest.raises(ValueError, match="at least one peer"):
        multiples([])


def test_multiples_reject_a_peer_set_with_no_positive_earnings():
    loss_maker = [p for p in PEERS if p.net_income < 0.0]
    assert loss_maker, "the fixture depends on there being a loss-making peer"
    with pytest.raises(ValueError, match="positive net income"):
        multiples(loss_maker)


def test_median_of_an_even_set_is_the_midpoint():
    m = multiples(PEERS[:4])
    ordered = sorted(p.ev / p.ebitda for p in PEERS[:4])
    assert m["ev_ebitda"]["median"] == pytest.approx((ordered[1] + ordered[2]) / 2.0)


# ---------------------------------------------------------------------------
# The basis conversion — the arithmetic the handover asked for
# ---------------------------------------------------------------------------

def test_conversion_is_neutral_when_leases_capitalise_at_the_multiple():
    """The closed form, stated as a property.

        m_post = m_pre - (R / EBITDA_post) x (m_pre - L / R)

    so the conversion moves nothing at all when the lease liability happens to
    capitalise the rent at the same multiple the business trades on. Rent
    inflating the denominator is only half the story; the lease liability
    inflates the numerator too.
    """
    assert post_ifrs16_multiple(
        pre_ifrs16_multiple=8.0, ebitda_post=400.0, lease_liabilities=800.0,
        fixed_lease_payments=100.0,
    ) == pytest.approx(8.0)


def test_conversion_cuts_the_multiple_when_leases_capitalise_below_it():
    got = post_ifrs16_multiple(
        pre_ifrs16_multiple=8.0, ebitda_post=400.0, lease_liabilities=500.0,
        fixed_lease_payments=100.0,
    )
    # 8 - (100/400) x (8 - 5) = 8 - 0.75
    assert got == pytest.approx(7.25)


#: The Base ``exit_ev_ebitda`` as it stood BEFORE fix round 1 recalibrated it.
#: Kept as a literal because the conversion arithmetic below is a finding about
#: that number, and ``drivers.exit_ev_ebitda`` is no longer a pre-IFRS 16
#: figure to feed the conversion — it is now derived post-IFRS 16 from the peer
#: set, so converting it again would be a basis error in the other direction.
SUPERSEDED_BASE_EXIT_MULTIPLE = 10.0


def test_conversion_of_the_superseded_base_multiple_moves_it_by_under_one_turn():
    """Against the handover's expectation, and this is the finding.

    The handover said a 10x pre-IFRS 16 multiple is "roughly 7-8x" post-IFRS
    16. On Greggs' own FY2030 figures it is 9.03x: the lease liability
    capitalises the rent at only 5.40x, so the numerator gains almost as much
    as the denominator. The conversion closes about a fifth of the gap to
    Gordon, not most of it.

    This is why the driver could not simply be converted and kept: 9.03x is
    still above the whole peer read, which is what forced the derivation in
    ``exit_multiple_from_peers()``.
    """
    drivers = SCENARIOS["Base"]
    model = build_model(GREGGS_HISTORICALS, drivers)
    leases = model.leases
    converted = post_ifrs16_multiple(
        pre_ifrs16_multiple=SUPERSEDED_BASE_EXIT_MULTIPLE,
        ebitda_post=model.ebitda[-1],
        lease_liabilities=leases.closing_liability[-1],
        fixed_lease_payments=leases.principal_paid[-1] + leases.interest[-1],
    )
    assert converted == pytest.approx(9.0308, abs=1e-4)
    assert SUPERSEDED_BASE_EXIT_MULTIPLE - converted < 1.0
    # And the shipped driver is 2.72 turns below the converted old one: the
    # basis conversion alone would not have got there, which is the whole
    # reason the driver had to be re-derived rather than merely restated.
    assert converted - drivers.exit_ev_ebitda == pytest.approx(2.7173, abs=1e-3)


def test_the_shipped_driver_is_already_post_ifrs16_and_must_not_be_converted():
    """A guard against the most likely future misuse of this module.

    ``post_ifrs16_multiple()`` takes a PRE-IFRS 16 multiple. Feeding it the
    shipped driver — which is now derived post-IFRS 16 — would strip the lease
    basis out a second time and land at 6.12x for Base. The test records that
    number so the mistake is recognisable if anyone makes it.
    """
    drivers = SCENARIOS["Base"]
    model = build_model(GREGGS_HISTORICALS, drivers)
    leases = model.leases
    wrong = post_ifrs16_multiple(
        pre_ifrs16_multiple=drivers.exit_ev_ebitda,
        ebitda_post=model.ebitda[-1],
        lease_liabilities=leases.closing_liability[-1],
        fixed_lease_payments=leases.principal_paid[-1] + leases.interest[-1],
    )
    assert wrong == pytest.approx(6.1214, abs=1e-4)
    assert wrong < drivers.exit_ev_ebitda


def test_conversion_rejects_a_nil_ebitda():
    with pytest.raises(ValueError, match="EBITDA"):
        post_ifrs16_multiple(
            pre_ifrs16_multiple=10.0, ebitda_post=0.0, lease_liabilities=500.0,
            fixed_lease_payments=100.0,
        )


# ---------------------------------------------------------------------------
# The recalibrated exit multiple (owner ruling, fix round 1)
# ---------------------------------------------------------------------------

def _terminal_intensity(name):
    from bluebook.inputs.greggs import GREGGS_SHARE_COUNT
    from bluebook.valuation import value_model

    drivers = SCENARIOS[name]
    model = build_model(GREGGS_HISTORICALS, drivers)
    valuation = value_model(
        model, drivers, GREGGS_HISTORICALS, GREGGS_SHARE_COUNT.value
    )
    return valuation.terminal.da / model.ebitda[-1]


def test_the_shipped_exit_multiples_are_the_peer_derived_ones():
    """Ties the three literals in ``assumptions.py`` back to the peer set.

    ``assumptions.py`` cannot import ``comps`` (comps imports HIST_NET_INCOME
    from it, so that would close a cycle), which is why the drivers carry
    literals. This test is the thing that stops the literals and the derivation
    drifting apart — the same literal-plus-covering-test pattern the HIST_*
    constants use.
    """
    expected = {"Bear": 5.0679, "Base": 6.3135, "Bull": 7.2351}
    for name, literal in expected.items():
        derived = exit_multiple_from_peers(_terminal_intensity(name), PEERS)
        assert derived == pytest.approx(literal, abs=5e-5), name
        assert SCENARIOS[name].exit_ev_ebitda == pytest.approx(literal), name


def test_the_derived_exit_multiples_are_ordered_bull_above_base_above_bear():
    """The ordering is NOT imposed, it falls out of the capital intensities.

    Bear runs the heaviest asset base against the smallest revenue, so its
    terminal D&A absorbs the most EBITDA (62.26% against Bull's 46.12%) and its
    coherent EBITDA multiple is the lowest.
    """
    bear, base, bull = (SCENARIOS[n].exit_ev_ebitda for n in ("Bear", "Base", "Bull"))
    assert bear < base < bull
    intensities = [_terminal_intensity(n) for n in ("Bear", "Base", "Bull")]
    assert intensities[0] > intensities[1] > intensities[2]
    # The spread narrowed relative to the discarded +/-1.5 offsets (3.0 turns),
    # because capital intensity varies less across scenarios than they asserted.
    assert bull - bear == pytest.approx(2.1672, abs=1e-4)


def test_recalibrating_the_exit_multiple_leaves_the_terminal_intensity_untouched():
    """The derivation is one-pass, not a fixed point, and this proves it.

    ``exit_ev_ebitda`` feeds only ``terminal_value_exit_multiple``, which is
    reported and never used to build enterprise value. So it cannot move the
    terminal D&A share it is derived from. If a later task wires the exit
    multiple into the headline EV, this test fails and the derivation would need
    solving as a fixed point instead.
    """
    from dataclasses import replace

    for name in SCENARIOS:
        before = _terminal_intensity(name)
        drivers = replace(SCENARIOS[name], exit_ev_ebitda=99.0)
        model = build_model(GREGGS_HISTORICALS, drivers)
        from bluebook.inputs.greggs import GREGGS_SHARE_COUNT
        from bluebook.valuation import value_model

        valuation = value_model(
            model, drivers, GREGGS_HISTORICALS, GREGGS_SHARE_COUNT.value
        )
        after = valuation.terminal.da / model.ebitda[-1]
        assert after == pytest.approx(before), name
        # And the headline price is likewise untouched.
        assert valuation.share_price_pence == pytest.approx(
            value_model(
                build_model(GREGGS_HISTORICALS, SCENARIOS[name]),
                SCENARIOS[name],
                GREGGS_HISTORICALS,
                GREGGS_SHARE_COUNT.value,
            ).share_price_pence
        ), name


def test_exit_multiple_from_peers_rejects_an_impossible_intensity():
    with pytest.raises(ValueError, match="fraction"):
        exit_multiple_from_peers(1.0, PEERS)
    with pytest.raises(ValueError, match="fraction"):
        exit_multiple_from_peers(-0.01, PEERS)


def test_the_peer_median_ev_ebit_is_robust_to_dropping_the_property_outlier():
    """The derivation rests on the median EV/EBIT, so its robustness matters.

    Mitchells & Butlers at 9.13x is the one peer flagged as partly a property
    multiple. Dropping it moves the median EV/EBIT by 0.13%, which is why the
    derivation is not sensitive to that judgement call.
    """
    full = multiples(PEERS)["ev_ebit"]["median"]
    without = multiples([p for p in PEERS if p.name != "Mitchells & Butlers"])
    assert without["ev_ebit"]["median"] / full - 1.0 == pytest.approx(
        0.0013, abs=1e-4
    )


# ---------------------------------------------------------------------------
# Matching the peer read to capital intensity
# ---------------------------------------------------------------------------

def test_intensity_matching_reproduces_a_peers_own_multiple():
    """Sanity: read the curve at a peer's own intensity and get its own
    multiple back. Interpolation that failed this would not be interpolation."""
    for p in PEERS:
        got = intensity_matched_multiple((p.ebitda - p.ebit) / p.ebitda, PEERS)
        assert got == pytest.approx(p.ev / p.ebitda), p.name


def test_matching_the_base_terminal_intensity_lands_between_wetherspoon_and_ssp():
    """The reconciliation number: 6.32x, not the raw median's 7.54x.

    The Base terminal year's D&A/EBITDA of 52.98% is bracketed by Wetherspoon
    (43.87%, 7.54x) and SSP (60.84%, 5.27x), and the interpolated read is
    17.9% above Gordon's 5.19x rather than 31.2% above it.
    """
    drivers = SCENARIOS["Base"]
    model = build_model(GREGGS_HISTORICALS, drivers)
    from bluebook.inputs.greggs import GREGGS_SHARE_COUNT
    from bluebook.valuation import value_model

    valuation = value_model(model, drivers, GREGGS_HISTORICALS, GREGGS_SHARE_COUNT.value)
    intensity = valuation.terminal.da / model.ebitda[-1]
    matched = intensity_matched_multiple(intensity, PEERS)
    gordon = valuation.terminal_value_gordon / model.ebitda[-1]
    assert intensity == pytest.approx(0.529813, abs=1e-6)
    assert matched == pytest.approx(6.3208, abs=1e-4)
    assert gordon == pytest.approx(5.1869, abs=1e-4)
    assert gordon / matched - 1.0 == pytest.approx(-0.1794, abs=1e-4)
    assert gordon / multiples(PEERS)["ev_ebitda"]["median"] - 1.0 == pytest.approx(
        -0.3119, abs=1e-4
    )


def test_the_bear_terminal_is_more_capital_intensive_than_every_peer():
    """Not a defensive branch — a live case.

    Bear's terminal D&A/EBITDA is 62.26%, above SSP's 60.84%, so the peer set
    cannot price it at all and the function says so instead of extrapolating.
    """
    drivers = SCENARIOS["Bear"]
    model = build_model(GREGGS_HISTORICALS, drivers)
    from bluebook.inputs.greggs import GREGGS_SHARE_COUNT
    from bluebook.valuation import value_model

    valuation = value_model(model, drivers, GREGGS_HISTORICALS, GREGGS_SHARE_COUNT.value)
    intensity = valuation.terminal.da / model.ebitda[-1]
    assert intensity == pytest.approx(0.622578, abs=1e-6)
    assert intensity > max((p.ebitda - p.ebit) / p.ebitda for p in PEERS)
    with pytest.raises(ValueError, match="outside the peer range"):
        intensity_matched_multiple(intensity, PEERS)


def test_intensity_matching_and_ev_ebit_agree_because_the_bracket_is_flat():
    """The honesty check on point 3 of the module docstring.

    Wetherspoon and SSP trade within 0.3% of each other on EV/EBIT, so across
    the bracketing segment the interpolation IS a constant-EV/EBIT line. The
    two normalisations agree because they are the same observation, and this
    test exists so nobody later reads their agreement as corroboration.
    """
    jdw = next(p for p in PEERS if p.name == "J D Wetherspoon")
    ssp = next(p for p in PEERS if p.name == "SSP Group")
    assert abs((ssp.ev / ssp.ebit) / (jdw.ev / jdw.ebit) - 1.0) < 0.003
    intensity = 0.529813
    via_interpolation = intensity_matched_multiple(intensity, PEERS)
    via_flat_ev_ebit = (jdw.ev / jdw.ebit) * (1.0 - intensity)
    assert via_interpolation == pytest.approx(via_flat_ev_ebit, rel=2e-3)


def test_intensity_matching_rejects_an_empty_peer_set():
    with pytest.raises(ValueError, match="at least one peer"):
        intensity_matched_multiple(0.5, [])


# ---------------------------------------------------------------------------
# Greggs against the set
# ---------------------------------------------------------------------------

def test_greggs_trades_inside_the_peer_range_on_both_multiples():
    m = multiples(PEERS)
    g = greggs_trading_multiples(GREGGS_HISTORICALS)
    assert m["ev_ebitda"]["min"] < g.ev_ebitda < m["ev_ebitda"]["max"]
    assert m["ev_ebit"]["min"] < g.ev_ebit < m["ev_ebit"]["max"]


def test_greggs_ev_ebit_sits_far_closer_to_the_peer_median_than_ev_ebitda():
    """Greggs is 9% below the peer median on EV/EBITDA and 2% below it on
    EV/EBIT. The EBITDA discount is a capital-intensity artefact, not a rating
    discount, and that is what makes EV/EBIT the honest cross-check on the
    terminal value."""
    m = multiples(PEERS)
    g = greggs_trading_multiples(GREGGS_HISTORICALS)
    ebitda_gap = abs(g.ev_ebitda / m["ev_ebitda"]["median"] - 1.0)
    ebit_gap = abs(g.ev_ebit / m["ev_ebit"]["median"] - 1.0)
    assert ebitda_gap > 3.0 * ebit_gap


def test_greggs_ev_is_market_cap_plus_the_models_own_opening_net_debt():
    last = GREGGS_HISTORICALS[-1]
    net_debt_incl_leases = (
        last.borrowings.value - last.cash.value + last.lease_liabilities.value
    )
    g = greggs_trading_multiples(GREGGS_HISTORICALS)
    assert net_debt_incl_leases == pytest.approx(404.0)
    assert g.ev == pytest.approx(g.market_cap + net_debt_incl_leases)


# ---------------------------------------------------------------------------
# The 52-week range — the one figure with no formula behind it
# ---------------------------------------------------------------------------

def test_the_52_week_range_is_ordered_and_brackets_the_observed_price():
    assert GREGGS_52_WEEK_LOW.value < GREGGS_SHARE_PRICE.value < GREGGS_52_WEEK_HIGH.value


def test_the_52_week_range_and_price_are_pinned_to_the_provider_snapshot():
    """These three have NO formula behind them and no filing either.

    Every other figure in the workbook is either derived or checkable against a
    report; these are market observations, so the only guard against a
    transcription slip is pinning the literals. The mutation sweep found a ±1%
    change in either end of the range went undetected without this.
    """
    assert GREGGS_52_WEEK_LOW.value == pytest.approx(1407.20)
    assert GREGGS_52_WEEK_HIGH.value == pytest.approx(2046.00)
    assert GREGGS_SHARE_PRICE.value == pytest.approx(1964.00)
    assert PRICE_OBSERVATION_DATE == "5 August 2026"


def test_the_52_week_range_records_its_provider_and_date():
    for figure in (GREGGS_52_WEEK_LOW, GREGGS_52_WEEK_HIGH, GREGGS_SHARE_PRICE):
        assert "stockanalysis.com" in figure.source
        assert "2026" in figure.source


def test_the_peer_dataclass_refuses_an_unsourced_figure():
    with pytest.raises(ValueError, match="source"):
        Peer(
            name="Nowhere plc", share_price_pence=100.0, shares=10.0, market_cap=10.0,
            net_debt_incl_leases=5.0, lease_liabilities=3.0, minority_interests=0.0,
            ev=15.0, ebitda=2.0, ebit=1.0, net_income=1.0, source="   ",
        )


def test_the_peer_dataclass_refuses_an_ev_that_does_not_tie():
    with pytest.raises(ValueError, match="enterprise value"):
        Peer(
            name="Nowhere plc", share_price_pence=100.0, shares=10.0, market_cap=10.0,
            net_debt_incl_leases=5.0, lease_liabilities=3.0, minority_interests=0.0,
            ev=99.0, ebitda=2.0, ebit=1.0, net_income=1.0, source="made up",
        )
