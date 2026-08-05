"""LBO return analysis — a sponsor-return exercise, not a buyout thesis.

**What this module is.** It asks one question: if a financial sponsor bought
Greggs at the price the market puts on it today, financed it as far as this
balance sheet allows, ran the model's own Base operating case for five years and
sold at the multiple it paid, what would the equity return? That is a
DISCIPLINE, not a recommendation. An LBO screen is the cheapest available test
of whether a DCF's cash flows are real: a discounted cash flow can be flattered
by a terminal value, but a sponsor return cannot, because it is driven by cash
that actually pays down debt inside the hold period.

**What this module is NOT.** It is not a claim that Greggs is a live buyout
candidate, and nothing here should be read as one. Two facts make that plain
before any of the arithmetic:

  * **The business is LOW-LEVERAGE.** At FY2025 Greggs holds £25.0m of drawn
    revolver against £70.8m of cash — a NET CASH position of £45.8m excluding
    leases. There is no existing capital structure to lever against and no
    stressed balance sheet to fix.
  * **The business is LEASE-HEAVY.** The £449.8m IFRS 16 lease liability is
    1.28x FY2025 EBITDA of £351.2m and it is contractual, non-negotiable and
    already senior in economic substance to anything a sponsor would raise.
    Debt capacity is not a blank sheet: a lender underwriting a 4.0x
    lease-adjusted structure is underwriting 2.72x of new money, because the
    first 1.28x is spoken for.

Those two facts are what make the exercise instructive rather than fanciful. A
lease-heavy retailer with a running capital programme is close to the worst case
for an LBO, and saying so with numbers is more useful than not running one.

--------------------------------------------------------------------------
The structure, and which parts are sourced and which are judgement
--------------------------------------------------------------------------
Sourced, and traceable to a filing or a market observation:

  * entry enterprise value — Greggs' own traded EV from ``comps.py``,
    £2,406.5m, being a 5 August 2026 market capitalisation of £2,002.5m plus
    the FY2025 net debt including leases of £404.0m;
  * entry EBITDA £351.2m and the £449.8m opening lease liability, both from
    ``inputs/greggs.py``;
  * the whole operating case — unlevered FCF, ROU additions, lease principal
    and lease interest — from ``reference.build_model`` and
    ``valuation.unlevered_fcf``, i.e. the model this repo already ships.

Judgement, stated here rather than buried:

  * ``SPONSOR_ENTRY_LEVERAGE`` = 4.0x total net debt INCLUDING leases. This
    is not sourced from anything. It is the round number a UK leveraged
    retail/hospitality structure is typically underwritten near, and it is set
    lease-inclusive because that is the only definition consistent with the
    rest of this model. Reading it lease-EXCLUSIVE would imply 5.28x total,
    which no lender would fund against this cash flow profile.
  * the cost of the new debt is ``drivers.interest_rate_debt``, 5.50%, which is
    Greggs' own revolver rate. A real buyout facility on this credit would
    price materially wider, so the IRR below is if anything FLATTERED. It is
    used because inventing a leveraged spread would be inventing a number, and
    the model already carries a defensible borrowing rate.
  * ``SPONSOR_IRR_HURDLE`` = 20%, the conventional underwriting hurdle. Also a
    convention, not a fact.
  * exit at the ENTRY multiple. No multiple expansion is assumed, which is the
    standard conservative convention and, here, the only defensible one: the
    entry multiple is an observed market price and any other exit multiple
    would be an opinion dressed as an input.

--------------------------------------------------------------------------
The cash sweep, and the one subtlety in it
--------------------------------------------------------------------------
Financial debt is swept by

    cash available = unlevered FCF
                   + new ROU additions
                   - lease principal repaid
                   - lease interest x (1 - tax rate)
                   - financial interest x (1 - tax rate)

The ROU additions term is the subtlety and it is not a fudge. ``valuation.
unlevered_fcf`` DEDUCTS new ROU additions as an investing outflow, on the
ruling that funding a leased shop is economically the same act as funding an
owned one. Under that ruling a new lease is also a financing INFLOW of the same
amount — the liability that funds the asset — so it is added back here, and the
lease is then serviced through the principal and interest lines like any other
debt. Deducting the additions and the principal without the add-back would
charge the same leases twice, which is the mirror image of the double-count
``valuation.py`` documents on the other side.

Interest is taxed at ``drivers.tax_rate`` because unlevered FCF taxes EBIT and
so carries no interest shield of any kind. Both interest lines get the shield;
neither got one upstream.

--------------------------------------------------------------------------
What it returns, and the finding
--------------------------------------------------------------------------
Base case, five years, entry at the traded 6.85x and exit at the same:

    equity cheque                £1,001.7m
    financial debt at entry        £955.0m   (4.0x total less the 1.28x of leases)
    financial debt at exit          £967.1m
    exit equity                  £1,822.5m
    money multiple                    1.82x
    IRR                              12.72%

**Below the 20% hurdle, and the shape of the path is the reason.** Unlevered
FCF is NEGATIVE in FY2026 (-£44.8m) and FY2027 (-£10.7m) because the
distribution-centre programme is still running, so the sponsor FUNDS the capex
rather than sweeping cash against the debt. Net financial debt therefore RISES
for three years, peaking at £1,098.0m in FY2028, and **there is no net
deleveraging at all across the hold**: financial debt ends at £967.1m, £12.1m
HIGHER than the £955.0m drawn at entry. The two positive sweep years (£43.5m in
FY2029, £87.4m in FY2030) do not recover the £143.0m drawn across FY2026-28.
Meanwhile the lease book GROWS by £106.2m, because the model opens more shops
than it closes, so total debt including leases is £118.2m HIGHER at exit
(£1,523.0m) than at entry (£1,404.8m). The 1.82x is therefore **entirely** an
EBITDA-growth story (£351.2m to £488.2m, +39.0%) applied to a static multiple,
with de-gearing contributing nothing and in fact working against it.

Clearing 20% would need an exit at 8.22x against an entry at 6.85x — 1.37 turns
of multiple expansion, above the peer median of 7.54x though still inside the
peer range. That is the honest statement of what the case needs; it is not
unreachable, but it is not underwritable either, because it requires the exit
multiple to do work the cash flows do not.

Across the three scenarios, on the same entry price and structure:

    Bear   money multiple 0.87x   IRR  -2.73%   (equity loses money)
    Base   money multiple 1.82x   IRR  12.72%
    Bull   money multiple 2.89x   IRR  23.66%

Only Bull clears the hurdle, and Bear loses capital outright: 4.0x leverage on a
business whose free cash flow starts negative gives back 12.9% of the equity
over five years if the operating case merely disappoints. That asymmetry — a
23.7% upside against a nil-to-negative downside, on a spread that is entirely
operating — is the substantive output of the sheet.

**This corroborates the DCF rather than contradicting it.** The DCF says the
same thing in a different currency: 93-95% of the enterprise value sits in the
terminal value precisely because the explicit period generates so little free
cash. An LBO cannot borrow against a terminal value, so it simply reports that
fact as a low IRR.
"""

from __future__ import annotations

from dataclasses import dataclass

from bluebook.assumptions import Drivers
from bluebook.inputs.schema import HistoricalYear
from bluebook.reference import Model
from bluebook.valuation import unlevered_fcf

# Total net debt INCLUDING lease liabilities, as a multiple of entry EBITDA.
# Judgement, not a sourced figure — see the module docstring.
SPONSOR_ENTRY_LEVERAGE = 4.0

# Conventional buyout underwriting hurdle. Also a convention, not a fact.
SPONSOR_IRR_HURDLE = 0.20


# ---------------------------------------------------------------------------
# The return calculation
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class LboReturns:
    """Sponsor equity return over a whole number of years."""

    entry_equity: float
    exit_equity: float
    money_multiple: float
    irr: float


def lbo_returns(
    entry_ev: float, entry_debt: float, exit_ev: float, exit_debt: float, years: int
) -> LboReturns:
    """Money multiple and IRR on a single-cheque, single-exit holding.

        entry equity = entry EV - entry debt
        exit equity  = exit EV  - exit debt
        money multiple = exit equity / entry equity
        IRR = money multiple ** (1 / years) - 1

    One cash flow in and one out, so the IRR is the geometric growth rate of
    the equity and nothing more; there are no interim distributions to solve
    around. ``entry_debt`` and ``exit_debt`` are NET debt INCLUDING lease
    liabilities on both sides, matching the enterprise values they are
    subtracted from.

    Both equity values must be positive. A negative exit equity is not a -100%
    return that the formula could report: raising it to a fractional power is
    not defined over the reals, and an equity that has gone through zero is a
    restructuring rather than an exit, so it is rejected outright.
    """
    if years <= 0:
        raise ValueError(f"years must be a positive holding period, got {years}")
    entry_equity = entry_ev - entry_debt
    if entry_equity <= 0.0:
        raise ValueError(
            f"entry equity must be positive, got {entry_equity} "
            f"(EV {entry_ev} less debt {entry_debt})"
        )
    exit_equity = exit_ev - exit_debt
    if exit_equity <= 0.0:
        raise ValueError(
            f"exit equity must be positive, got {exit_equity} "
            f"(EV {exit_ev} less debt {exit_debt})"
        )
    money_multiple = exit_equity / entry_equity
    return LboReturns(
        entry_equity=entry_equity,
        exit_equity=exit_equity,
        money_multiple=money_multiple,
        irr=money_multiple ** (1.0 / years) - 1.0,
    )


# ---------------------------------------------------------------------------
# The Greggs case
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class LboCase:
    """A fully specified sponsor case, with every input it was built from."""

    years: int
    entry_ev: float
    entry_ebitda: float
    entry_multiple: float
    entry_debt: float                        # total, including leases
    entry_leases: float
    entry_financial_debt: float
    entry_leverage: float
    interest_rate: float
    financial_debt_closing: list[float]      # £m, one per forecast year
    cash_swept: list[float]                  # £m available to repay debt, per year
    exit_ebitda: float
    exit_multiple: float
    exit_ev: float
    exit_leases: float
    exit_debt: float                         # total, including leases
    returns: LboReturns


def greggs_lbo_case(
    model: Model,
    drivers: Drivers,
    historicals: list[HistoricalYear],
    entry_ev: float,
    entry_leverage: float = SPONSOR_ENTRY_LEVERAGE,
) -> LboCase:
    """Build the sponsor case on the model's own operating forecast.

    ``entry_ev`` is passed in rather than derived so the caller chooses the
    entry price explicitly; ``comps.greggs_trading_multiples().ev`` is the
    observed one. Entry EBITDA is the last reported year on the same
    definition the model forecasts, i.e. revenue less cost of sales less
    ``operating_costs``.

    Lease liabilities are NOT a separate schedule here: the closing balances
    come straight from ``model.leases``, so the sponsor case inherits exactly
    the lease book the DCF values, including the fact that it grows.
    """
    if entry_leverage <= 0.0:
        raise ValueError(f"entry leverage must be positive, got {entry_leverage}")

    last = historicals[-1]
    entry_ebitda = (
        last.revenue.value - last.cost_of_sales.value - last.operating_costs.value
    )
    entry_leases = last.lease_liabilities.value
    entry_debt = entry_leverage * entry_ebitda
    entry_financial_debt = entry_debt - entry_leases
    if entry_financial_debt < 0.0:
        raise ValueError(
            f"leverage of {entry_leverage}x on EBITDA of {entry_ebitda} is below the "
            f"existing lease liability of {entry_leases}: no new debt could be raised"
        )

    fcf = unlevered_fcf(model, drivers)
    leases = model.leases
    after_tax = 1.0 - drivers.tax_rate
    rate = drivers.interest_rate_debt

    closing: list[float] = []
    swept: list[float] = []
    financial_debt = entry_financial_debt
    for year in range(len(fcf)):
        # Interest on the OPENING balance: the sweep happens at the year end,
        # so it cannot reduce the interest the year itself carries.
        interest = rate * financial_debt
        cash = (
            fcf[year]
            + leases.additions[year]            # new leases fund their own assets
            - leases.principal_paid[year]
            - leases.interest[year] * after_tax
            - interest * after_tax
        )
        financial_debt -= cash                  # negative sweep DRAWS more debt
        swept.append(cash)
        closing.append(financial_debt)

    exit_leases = leases.closing_liability[-1]
    exit_debt = closing[-1] + exit_leases
    exit_ebitda = model.ebitda[-1]
    entry_multiple = entry_ev / entry_ebitda
    # No multiple expansion: the exit is struck at the multiple paid.
    exit_multiple = entry_multiple
    exit_ev = exit_multiple * exit_ebitda

    return LboCase(
        years=len(fcf),
        entry_ev=entry_ev,
        entry_ebitda=entry_ebitda,
        entry_multiple=entry_multiple,
        entry_debt=entry_debt,
        entry_leases=entry_leases,
        entry_financial_debt=entry_financial_debt,
        entry_leverage=entry_leverage,
        interest_rate=rate,
        financial_debt_closing=closing,
        cash_swept=swept,
        exit_ebitda=exit_ebitda,
        exit_multiple=exit_multiple,
        exit_ev=exit_ev,
        exit_leases=exit_leases,
        exit_debt=exit_debt,
        returns=lbo_returns(
            entry_ev=entry_ev,
            entry_debt=entry_debt,
            exit_ev=exit_ev,
            exit_debt=exit_debt,
            years=len(fcf),
        ),
    )
