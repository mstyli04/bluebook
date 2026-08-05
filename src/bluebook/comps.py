"""Trading comparables: five UK-listed food and hospitality names, post-IFRS 16.

This is the first module in the model that brings evidence from OUTSIDE Greggs'
own filings. Everything before it was internally consistent but self-referential:
the terminal value, the WACC and the exit multiple were all calibrated against
each other. The peer set exists to settle one question the model could not settle
on its own — what multiple of EBITDA a business like this actually changes hands
at — and to price the FY2030 exit that ``drivers.exit_ev_ebitda`` asserts without
support.

--------------------------------------------------------------------------
The basis rule, which governs every figure below
--------------------------------------------------------------------------
Everything is POST-IFRS 16, matching the rest of the model:

  * EBITDA is struck after the rent add-back, i.e. operating profit plus
    depreciation of owned assets, depreciation of RIGHT-OF-USE assets, and
    amortisation. There is no rent line left in it.
  * enterprise value carries lease liabilities as debt, so EV = market
    capitalisation + net debt INCLUDING lease liabilities + minority interests.

Both halves have to move together. An EV that excluded leases divided by an
EBITDA that added rent back would be a number with no meaning, and it is the
single most likely way for this sheet to be silently wrong, so
``test_no_peer_carries_lease_liabilities_outside_ev`` and
``Peer.__post_init__`` both police it.

No peer needed restating from a pre-IFRS 16 basis. All five report under IFRS 16
and disclose lease liabilities on the face of the balance sheet or in the net
debt note. Two of them lead on pre-IFRS 16 alternative performance measures
(SSP's £364.1m "pre-IFRS 16 underlying EBITDA", Wetherspoon's £203.3m "EBITDA in
the last 12 months"); neither of those figures is used here, and the build-up
that replaces each is written out beside the peer.

--------------------------------------------------------------------------
Which EBITDA, and which net income
--------------------------------------------------------------------------
EBITDA is each company's UNDERLYING / pre-exceptional operating profit plus its
D&A, because that is the basis a comps page is read on and because it is the
basis Greggs' own model EBITDA sits closest to: ``inputs/greggs.py`` folds
impairment into ``depreciation_ppe`` / ``depreciation_rou``, so the model's
FY2025 EBITDA of £351.2m already adds back the £6.9m of FY2025 net impairment
(£3.9m PP&E + £3.0m ROU).

Net income is each company's STATUTORY profit attributable to equity holders —
no adjustment, straight off the income statement. The two bases differ, and for
SSP they differ enough to matter: SSP's statutory attributable result for FY2025
is a LOSS of £74.4m against an underlying operating profit of £269.1m. Its P/E
is therefore not a multiple at all, and ``multiples()`` drops it from the P/E
statistics rather than letting it drag a median negative. All five names stay in
the EV/EBITDA and EV/EBIT statistics, which is where the sheet's conclusion
comes from.

--------------------------------------------------------------------------
How comparable each name actually is — read this before the median
--------------------------------------------------------------------------
Greggs is **leased-estate food-to-go retail**: a shop estate that is
overwhelmingly leasehold (the £449.8m lease liability against £832.1m of owned
PP&E is the only measure of that in this repo, and no shop count is recorded
anywhere in it, so none is asserted here), vertically integrated manufacturing
and distribution, very high transaction volume at a very low ticket. **Not one
of the five is a close structural match
to that**, and the honest thing is to say where each one breaks rather than let
"UK food and hospitality" do the work.

* **SSP Group — closest match, and it matters that it is the cheapest.**
  High-volume, low-ticket food-to-go out of leased/concession units. Breaks on:
  travel footfall rather than high street; majority of revenue outside the UK;
  concession fees substantially turnover-linked, so a smaller share of its rent
  is capitalised than Greggs'; statutory loss-making in FY2025. **It trades at
  5.27x, the BOTTOM of the range, and 5.27x is within 1.6% of Gordon's Base
  implied 5.19x.** Any reading that "the peers contradict Gordon" has to
  account for the fact that the single most comparable name in the set does
  not.
* **J D Wetherspoon — comparable demand, wrong tenure.** UK-only, value-led,
  town-centre, food-and-drink at low average spend; the customer proposition is
  the nearest thing in the set to Greggs'. Breaks on: majority freehold estate,
  alcohol-led revenue mix, sit-down format. It is the MEDIAN of the set at
  7.54x, which means **the sheet's headline median is set by a pub company**.
* **Whitbread — a lease-intensity reference, not a format comp.** In the set
  because £4,523.1m of lease liabilities makes it the only name whose IFRS 16
  mechanics are as dominant as Greggs'. Breaks on: the product is a room-night,
  and demand is accommodation not food.
* **Mitchells & Butlers — weight DOWN.** UK eating-out demand, but a largely
  freehold estate carried at valuation, so its 6.45x is partly a property
  multiple rather than a trading one, and the format is sit-down dining. It is
  also the one peer whose EV/EBIT (9.13x) is far off the other four, which is
  consistent with property value sitting in EV without a matching earnings
  stream.
* **Domino's Pizza Group — weight DOWN hardest.** An asset-light FRANCHISOR:
  revenue is royalties and supply-chain sales to franchisees, and the
  franchisees hold the shop leases, which is why its D&A/EBITDA is 21.4%
  against Greggs' 47.7%. It is in the set because it is the only other listed
  UK food-to-go brand, but **its 10.12x should be read as an upper bound on
  franchise-model economics, not as a comparable capital structure.** Dropping
  it would cut the set's EV/EBITDA spread from 1.92x to 1.66x — though dropping
  SSP instead would cut it to 1.57x, so Domino's is not the largest single
  contributor to the spread and it would be wrong to say so.

**What that does to the median.** Five observations means the median IS a single
observation, and here that observation is Wetherspoon. With a 1.92x spread and
no two names sharing a business model, the median carries no meaningful
precision — it is a sector anchor, not a like-for-like read, and the RANGE
5.27x-10.12x is the honest output. Nothing below leans on the median alone; the
reconciliation that follows uses EV/EBIT and a capital-intensity match instead,
both of which are less sensitive to which pub company happens to sit third.

Nothing is excluded on comparability grounds. Dropping Domino's and M&B would
leave three names and a median set by whichever of Wetherspoon and Whitbread
survived, which is worse, not better: a narrow set of near-comps is only
preferable when the near-comps are actually near. Compass Group was excluded,
but on a data-basis ground rather than a comparability one — see the note above
``PEERS``.

--------------------------------------------------------------------------
What the set actually says
--------------------------------------------------------------------------
Post-IFRS 16 EV/EBITDA, at the prices in ``PRICE_OBSERVATION_DATE``:

    SSP Group             5.27x        D&A/EBITDA  60.8%
    Mitchells & Butlers   6.45x                    29.3%
    J D Wetherspoon       7.54x  <- median         43.9%
    Whitbread             8.73x                    39.7%
    Domino's Pizza Group 10.12x                    21.4%

That is a 1.92x spread between the cheapest and dearest name in one sector, and
the third column is most of the explanation. **Post-IFRS 16 EV/EBITDA in this
sector is substantially a reading of capital intensity, not of rating.** The
same five names on EV/EBIT run 9.13x (M&B) to 14.48x (Whitbread), a 1.59x
spread, with a median of 13.43x. ``test_ev_ebit_is_a_much_tighter_spread_than_
ev_ebitda`` pins the comparison.

Greggs itself, at 1,964.0p, is 6.85x EV/EBITDA and 13.10x EV/EBIT on FY2025.
Against the medians that is 9.1% cheap on EBITDA and 2.4% cheap on EBIT — the
EBITDA discount is almost entirely the capital-intensity artefact, because
Greggs' own D&A/EBITDA is 47.7%, above four of the five peers. On P/E Greggs is
16.39x against a peer median of 13.24x, i.e. at a PREMIUM, which is the same
fact seen from the other side: Greggs carries net CASH excluding leases, so its
equity is less geared than the peers' and capitalises the same enterprise more
dearly.

--------------------------------------------------------------------------
The basis conversion, and why the handover's estimate was wrong
--------------------------------------------------------------------------
Task 9 handed over the expectation that a 10x multiple struck pre-IFRS 16 is
"roughly 7-8x" post-IFRS 16, because the rent add-back inflates the denominator.
Half of that is right. The rent add-back also inflates the NUMERATOR, because
capitalising the leases puts the lease liability into EV. ``post_ifrs16_
multiple()`` does the arithmetic, and the closed form is

    m_post = m_pre - (R / EBITDA_post) x (m_pre - L / R)

with ``R`` the fixed cash lease cost (principal plus interest) and ``L`` the
lease liability. The conversion is NEUTRAL when the lease liability happens to
capitalise the rent at the multiple the business trades on, and it only bites to
the extent ``L / R`` falls short of ``m_pre``.

For Greggs at FY2030 Base, ``L`` is £556.0m against ``R`` of £102.9m, so ``L/R``
is 5.40x — well short of 10x, but not zero. The conversion is:

    Bear   8.5x pre  ->  7.70x post   (L 491.9, R  92.1, EBITDA 362.8)
    Base  10.0x pre  ->  9.03x post   (L 556.0, R 102.9, EBITDA 488.2)
    Bull  11.5x pre  -> 10.40x post   (L 623.1, R 114.2, EBITDA 626.7)

**So the basis conversion is worth 0.80x / 0.97x / 1.10x, not the 2-3x the
handover expected.** Against Gordon-implied multiples of 3.76x / 5.19x / 6.24x
it closes 17.0% / 20.1% / 20.9% of the gap, not most of it. The arithmetic was worth
doing first, exactly as the handover said; it just does not land where the
handover thought.

--------------------------------------------------------------------------
The residual disagreement, stated plainly
--------------------------------------------------------------------------
After conversion the three numbers for Base are: Gordon 5.19x, peer median
7.54x, converted driver 9.03x. **The peers do not vindicate Gordon.** A terminal
value struck at the peer median would be £3,680.2m against Gordon's £2,532.5m,
1.45x higher, and would lift the Base implied price from 1,506.5p to 2,288.6p.
That is a real finding and it is not smoothed over anywhere in this module.

Three things are worth putting beside it before anyone concludes Gordon is
simply wrong:

1. **The two multiples are not the same object.** The peer multiples are
   trailing multiples on businesses the market expects to grow. The Gordon
   multiple is a TERMINAL multiple on a business that has, by construction,
   already decelerated to 2% in perpetuity. A terminal multiple below a
   current trading multiple is what the arithmetic of a fading growth rate
   produces, not evidence of an error.

2. **On EV/EBIT the gap is a quarter of the size.** Gordon's Base terminal
   value is 11.03x the re-based terminal EBIT of £229.6m, against a peer
   median EV/EBIT of 13.43x — 17.9% below, not 31.2% below. The EV/EBITDA
   comparison is inflated by the terminal year's D&A/EBITDA of 53.0%, which is
   higher than Greggs' own FY2025 47.7% and higher than four of the five peers.
   The model deliberately builds a MORE capital-intensive Greggs by FY2030, so
   its coherent EBITDA multiple has to be lower than today's.

3. **Matched on capital intensity, the peer read falls to 6.32x.**
   ``intensity_matched_multiple()`` interpolates EV/EBITDA between the two peers
   that bracket a given D&A/EBITDA. At the Base terminal year's 52.98% the
   bracketing names are Wetherspoon (43.87%, 7.54x) and SSP (60.84%, 5.27x),
   giving **6.32x against Gordon's 5.19x — 17.9% below, and 1.13 turns rather
   than 2.35.** Bull matches to 7.24x against 6.24x, 13.8% below. Bear's
   terminal 62.26% is OUTSIDE the peer range entirely, above even SSP's 60.84%,
   which is its own finding: the Bear terminal Greggs is more capital-intensive
   than the most capital-intensive listed comparable available.

   **This is not independent evidence, and saying so matters.** Wetherspoon and
   SSP trade at 13.43x and 13.46x EV/EBIT — within 0.3% of each other — despite
   EV/EBITDA of 7.54x and 5.27x. Across the segment of the set that brackets
   Greggs' terminal intensity, EV/EBIT is effectively flat, so the
   interpolation and point 2 above are the SAME observation reached twice, not
   two confirmations. What they jointly establish is narrower but firmer: of the
   31.2% raw EV/EBITDA gap, roughly 13 points are capital-intensity artefact and
   roughly 18 points are a real disagreement.

4. **That real 18 points is a reinvestment assumption, and it can be stated as
   one.** The Gordon multiple decomposes exactly as
   ``(terminal FCF / terminal EBITDA) x (1 + g) / (WACC - g)``. The second
   factor is 17.7977 in every scenario. So 5.19x is precisely a terminal cash
   conversion of 29.14%, and the peer median of 7.54x is precisely a terminal
   cash conversion of 42.35%. The disagreement is not about the discount rate
   and not about the basis: it is the claim that Greggs converts 29% of
   post-IFRS 16 EBITDA to unlevered free cash flow in perpetuity, which follows
   from terminal capex of 6.90% of revenue plus ROU additions of 3.69%.

**Where that leaves the arithmetic against the judgement**, Base case, in order:

A. the driver against Gordon, 10.00x -> 5.19x, 4.81 turns, ADDITIVE:

     IFRS 16 basis conversion       10.00x -> 9.03x   0.97 turns    20.1%
     driver above ANY peer read      9.03x -> 6.32x   2.71 turns    56.3%
     genuine opinion residual        6.32x -> 5.19x   1.13 turns    23.6%
                                                      ----------   ------
                                                      4.81 turns   100.0%

B. the raw peer median against Gordon, 7.54x -> 5.19x, 2.35 turns, ADDITIVE:

     capital-intensity artefact      7.54x -> 6.32x   1.22 turns    51.8%
     genuine opinion residual        6.32x -> 5.19x   1.13 turns    48.2%
                                                      ----------   ------
                                                      2.35 turns   100.0%

The 6.32x is the hinge of both, and the 1.13-turn residual is the only line in
either that is genuinely a matter of opinion.

Read block A's middle line first. **The largest single component of the disagreement is
not Gordon being low; it is ``exit_ev_ebitda`` being high with nothing behind
it.** Even after the basis conversion, 9.03x is above the raw peer median of
7.54x and 42.9% above the capital-intensity-matched read of 6.32x, and the
driver has never moved.

**My reading**, for the owner rather than for the code:

* ``exit_ev_ebitda`` at 8.5 / 10.0 / 11.5 is not supportable on this evidence in
  any basis. Converted to post-IFRS 16 it is 7.70x / 9.03x / 10.40x, and the
  capital-intensity-matched peer read is 6.32x for Base. I am NOT changing the
  driver — the brief forbids it and it feeds a terminal value method that is not
  the headline — but it should be recalibrated, and the target is roughly 6.3x
  post-IFRS 16 for Base, not 10x.
* Gordon is the more defensible of the two, but **it is not vindicated
  outright.** It sits ~18% below the matched peer read on Base and ~14% on Bull,
  and that residual is real. The handover's expectation — that the basis
  conversion would close most of the gap and the peers would land near Gordon —
  is not what the evidence shows: the conversion explains a fifth, and the peers
  land above Gordon even after matching.
* The honest single output is a RANGE for the Base terminal multiple of **5.19x
  (Gordon) to 6.32x (intensity-matched peers)**, not the 5.19x-7.54x the raw
  median would suggest and not an average of anything. The burden sits on the
  terminal reinvestment intensity, which is a Task 9 construct and not mine to
  change.
* One genuine mitigant on Gordon's side, already noted: SSP, the closest
  structural comparable in the set, trades at 5.27x — within 1.6% of Gordon's
  5.19x. That is the strongest single piece of evidence FOR the Gordon
  construction, and it is a coincidence of capital intensity rather than a
  like-for-like validation, so it is worth exactly as much as that.

--------------------------------------------------------------------------
The 52-week range, which is the one figure that goes stale
--------------------------------------------------------------------------
``GREGGS_52_WEEK_LOW`` / ``GREGGS_52_WEEK_HIGH`` and ``GREGGS_SHARE_PRICE``
have no formula behind them and no filing either. They are market observations
from a named provider on a named date, and they are the only figures in the
workbook that are WRONG TOMORROW rather than merely out of date at the next
reporting cycle. The football field will show the range as a bar, and the bar is
only honest if it is labelled with the date it was struck. Same for every peer
share price: they are all from one snapshot, recorded once in
``PRICE_OBSERVATION_DATE``, so the whole sheet is internally consistent as at
one instant even as it ages.
"""

from __future__ import annotations

from dataclasses import dataclass
from statistics import median as _median

from bluebook.assumptions import HIST_NET_INCOME
from bluebook.inputs.schema import HistoricalYear, Sourced

PENCE_PER_POUND = 100.0

# Tolerance on the internal arithmetic of a Peer, £m. The literals below are
# quoted to two decimals against inputs carried to more, so a tie can be out by
# a few thousandths of a million and still be a correct transcription.
_TIE_TOLERANCE = 0.01


# ---------------------------------------------------------------------------
# Market observations — one snapshot, one date
# ---------------------------------------------------------------------------

PRICE_OBSERVATION_DATE = "5 August 2026"

_QUOTE = "stockanalysis.com delayed LSE quote, retrieved 5 August 2026"

# Greggs' own price, so the sheet can put the company on its own comps table.
GREGGS_SHARE_PRICE = Sourced(1964.00, f"{_QUOTE} 11:51 GMT (LON:GRG)")  # pence
GREGGS_SHARES_OUTSTANDING = Sourced(101.96, f"{_QUOTE} 11:51 GMT (LON:GRG)")  # millions

# The 52-week trading range. NO formula source and no filing source: a market
# observation with a provider and a date, and the one figure in the workbook
# that is stale the day after it is written. Anything that displays it must
# display PRICE_OBSERVATION_DATE beside it.
GREGGS_52_WEEK_LOW = Sourced(1407.20, f"{_QUOTE} 11:51 GMT (LON:GRG), 52-week range")
GREGGS_52_WEEK_HIGH = Sourced(2046.00, f"{_QUOTE} 11:51 GMT (LON:GRG), 52-week range")


# ---------------------------------------------------------------------------
# The peer record
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Peer:
    """One comparable company, post-IFRS 16, with its provenance.

    ``ev`` is stored rather than derived so that the literal in the table is
    the number the sheet uses and ``__post_init__`` is a genuine check on the
    transcription rather than a tautology.
    """

    name: str
    share_price_pence: float
    shares: float                   # millions, provider's shares outstanding
    market_cap: float               # £m
    net_debt_incl_leases: float     # £m, INCLUDING lease liabilities
    lease_liabilities: float        # £m, the lease component of the above
    minority_interests: float       # £m, book value; negative where a net liability
    ev: float                       # £m = market_cap + net debt + minorities
    ebitda: float                   # £m, post-IFRS 16, underlying
    ebit: float                     # £m, post-IFRS 16, underlying
    net_income: float               # £m, STATUTORY, attributable to equity holders
    source: str

    def __post_init__(self) -> None:
        if not self.source.strip():
            raise ValueError(f"{self.name}: every peer figure requires a source")
        tie = self.market_cap + self.net_debt_incl_leases + self.minority_interests
        if abs(self.ev - tie) > _TIE_TOLERANCE:
            raise ValueError(
                f"{self.name}: enterprise value {self.ev} does not tie to market cap "
                f"+ net debt incl leases + minorities ({tie})"
            )
        cap = self.share_price_pence / PENCE_PER_POUND * self.shares
        if abs(self.market_cap - cap) > _TIE_TOLERANCE:
            raise ValueError(
                f"{self.name}: market cap {self.market_cap} is not price x shares ({cap})"
            )


# ---------------------------------------------------------------------------
# The set
# ---------------------------------------------------------------------------
#
# Five UK-listed food and hospitality names. Compass Group was considered and
# EXCLUDED: it moved to US dollar reporting for FY2025, so putting it on this
# sheet would need a sourced FX rate and a translated balance sheet, and a
# global contract caterer is in any case a weaker read on a UK high-street
# food-to-go estate than the five below. Loungers, The Restaurant Group and
# Bakkavor would all have been candidates but are no longer separately listed;
# no delisting dates are stated here because none was sourced.

PEERS: list[Peer] = [
    Peer(
        name="SSP Group",
        # ---- market data ----
        share_price_pence=212.40,
        shares=762.24,
        market_cap=1618.998,         # 2.1240 x 762.24 = 1,618.998
        # ---- FY2025, year ended 30 September 2025 ----
        # Reported net debt of £1,816.9m is the IFRS figure and INCLUDES the
        # £1,242.7m lease liability; SSP's own headline leverage uses a
        # pre-IFRS 16 net debt of £574.2m, which is NOT used here.
        net_debt_incl_leases=1816.9,
        lease_liabilities=1242.7,
        minority_interests=186.8,    # balance sheet NCI; SSP consolidates JV concessions
        ev=3622.698,                 # 1,618.998 + 1,816.9 + 186.8
        # Underlying operating profit on the IFRS (post-IFRS 16) basis, £269.1m,
        # plus underlying D&A: PP&E 130.8 + right-of-use 276.8 + intangibles 10.5.
        #   269.1 + 418.1 = 687.2
        # Cross-check against SSP's own pre-IFRS 16 measure: pre-IFRS 16
        # underlying operating profit 222.8 + 130.8 + 10.5 = 364.1, which is
        # exactly the £364.1m SSP prints, so the D&A split is right. Going the
        # other way, 687.2 - 321.8 of fixed rents = 365.4, £1.3m above the
        # printed 364.1; SSP's stated IFRS 16 effect on underlying operating
        # profit is -46.3 while 276.8 - 321.8 is -45.0, the same £1.3m. It is
        # 0.19% of EBITDA, it is left unreconciled, and it is flagged rather
        # than silently absorbed.
        ebitda=687.2,
        ebit=269.1,
        # Statutory, and a LOSS: £183.0m of non-underlying charges sit between
        # £269.1m underlying and £86.1m statutory operating profit. Excluded
        # from the P/E statistics by multiples().
        net_income=-74.4,
        source=(
            "SSP Group plc, '2025 Full Year Results Announcement' RNS, 4 December 2025, "
            "year ended 30 September 2025; prices per PRICE_OBSERVATION_DATE"
        ),
    ),
    Peer(
        name="Domino's Pizza Group",
        share_price_pence=218.00,
        shares=381.16,
        market_cap=830.929,          # 2.1800 x 381.16 = 830.929
        # ---- FY2025, 52 weeks ended 28 December 2025 ----
        # DPG's £284.6m "net debt" EXCLUDES leases and ties to borrowings of
        # £309.2m less cash of £24.6m. Leases of £240.1m (22.9 current +
        # 217.2 non-current) are added here to put it on the model's basis:
        #   284.6 + 240.1 = 524.7
        net_debt_incl_leases=524.7,
        lease_liabilities=240.1,
        minority_interests=-0.6,     # net liability position at 28 December 2025
        ev=1355.029,                 # 830.929 + 524.7 - 0.6
        # Underlying EBITDA as DPG states it, £133.9m, and it IS post-IFRS 16:
        # the £28.6m added back to statutory PBIT of £101.1m is PP&E 7.9 +
        # right-of-use 6.6 + intangible amortisation 14.1. EBIT is the same
        # measure before that D&A: 133.9 - 28.6 = 105.3.
        ebitda=133.9,
        ebit=105.3,
        net_income=58.6,             # attributable to equity holders; £59.0m group total
        source=(
            "Domino's Pizza Group plc, 'Full year results for the 52 weeks ended 28.12.25' "
            "RNS, 10 March 2026; prices per PRICE_OBSERVATION_DATE"
        ),
    ),
    Peer(
        name="J D Wetherspoon",
        share_price_pence=814.00,
        shares=102.79,
        market_cap=836.711,          # 8.1400 x 102.79 = 836.711
        # ---- FY2025, 52 weeks ended 27 July 2025 ----
        # The company's own "net debt after derivatives and lease liabilities",
        # £1,129.1m. Its headline "net debt excluding IFRS-16 lease debt" of
        # £724.3m plus leases of £407.2m is £1,131.5m; the £2.4m difference is
        # the derivative position, and the company's lease-inclusive figure is
        # taken as stated rather than rebuilt.
        net_debt_incl_leases=1129.1,
        lease_liabilities=407.2,     # 52.0 current + 355.2 non-current
        minority_interests=0.0,
        ev=1965.811,                 # 836.711 + 1,129.1
        # Operating profit before separately disclosed items, £146.409m, plus
        # D&A of £114.365m: PP&E 72.205 + intangibles 2.003 + investment
        # property 0.218 + right-of-use 39.939. Total 260.774, shown as 260.8.
        # NOT the £203.3m Wetherspoon quotes in its net-book-value commentary,
        # which is pre-IFRS 16 — the £57.5m difference is the fixed rent the
        # post-IFRS 16 measure adds back, and mixing the two is precisely the
        # error this sheet is built to avoid.
        ebitda=260.8,
        ebit=146.4,
        net_income=68.0,             # profit for the period; no minority interest
        source=(
            "J D Wetherspoon plc, 'Preliminary Results' RNS, 3 October 2025, "
            "52 weeks ended 27 July 2025; prices per PRICE_OBSERVATION_DATE"
        ),
    ),
    Peer(
        name="Mitchells & Butlers",
        share_price_pence=284.50,
        shares=593.93,
        market_cap=1689.731,         # 2.8450 x 593.93 = 1,689.731
        # ---- FY2025, 52 weeks ended 27 September 2025 ----
        # Net debt of £1,277m as the company states it, = £843m non-lease
        # + £434m lease liabilities.
        net_debt_incl_leases=1277.0,
        lease_liabilities=434.0,
        minority_interests=0.0,
        ev=2966.731,                 # 1,689.731 + 1,277.0
        # "EBITDA before movements in the valuation of the property portfolio",
        # £460m, reconciled by the company from statutory operating profit of
        # £322m plus £138m of "depreciation, amortisation and movements in the
        # valuation of the property portfolio". Post-IFRS 16: right-of-use
        # depreciation of £36m is inside the add-back, and M&B quotes its own
        # leverage as 2.7x EBITDA INCLUDING lease liabilities against this
        # same figure. EBIT nets off the £135m of pure D&A (PP&E 96 +
        # intangibles 3 + right-of-use 36), leaving the £3m property valuation
        # movement in EBITDA and in EBIT alike: 460 - 135 = 325.
        ebitda=460.0,
        ebit=325.0,
        net_income=177.0,            # profit for the period
        source=(
            "Mitchells & Butlers plc, 'Full Year Results' RNS, 28 November 2025, "
            "52 weeks ended 27 September 2025; prices per PRICE_OBSERVATION_DATE"
        ),
    ),
    Peer(
        name="Whitbread",
        share_price_pence=2493.00,
        shares=167.14,
        market_cap=4166.800,         # 24.9300 x 167.14 = 4,166.800
        # ---- FY2026, 52 weeks ended 26 February 2026 ----
        # The company's own "Net debt and lease liabilities", £5,232m. Its
        # components are net debt of £709m and lease liabilities of £4,523.1m
        # (175.6 current + 4,347.5 non-current), which sum to £5,232.1m; the
        # £0.1m is the rounding on the £709m and the company's stated total is
        # used. Whitbread is the most lease-heavy name in the set by a wide
        # margin, which is the reason it is here.
        net_debt_incl_leases=5232.0,
        lease_liabilities=4523.1,
        minority_interests=0.0,
        ev=9398.800,                 # 4,166.800 + 5,232.0
        # Adjusted operating profit £649m plus the two income-statement D&A
        # lines: right-of-use asset depreciation £209m and other depreciation
        # and amortisation £218m. 649 + 427 = 1,076.
        # Whitbread's own stated "Adjusted EBITDAR" is £1,074m, £2m below this
        # build-up. The difference is not identified in the announcement and is
        # 0.2% of EBITDA; the build-up is used because it is the one that is
        # definitionally post-IFRS 16 EBITDA, and the discrepancy is flagged
        # rather than assumed away.
        ebitda=1076.0,
        ebit=649.0,
        net_income=212.9,            # statutory profit for the year
        source=(
            "Whitbread PLC, 'Preliminary Results Announcement' RNS, 30 April 2026, "
            "52 weeks ended 26 February 2026; prices per PRICE_OBSERVATION_DATE"
        ),
    ),
]


# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------

def _stats(values: list[float]) -> dict[str, float]:
    ordered = sorted(values)
    return {
        "min": ordered[0],
        "median": float(_median(ordered)),
        "max": ordered[-1],
        "count": float(len(ordered)),
    }


def multiples(peers: list[Peer]) -> dict[str, dict[str, float]]:
    """Min / median / max of the peer set, on three multiples.

    ``ev_ebitda`` and ``ev_ebit`` use every peer. ``pe`` uses only those with
    POSITIVE net income: a negative P/E is not a small multiple, it is not a
    multiple, and including SSP's would produce a median that means nothing.
    Each entry carries a ``count`` so a reader can see which statistic dropped
    a name.

    ``ev_ebit`` is not in the Task 10 brief's signature. It is here because it
    is what the peer set actually turns on — see the module docstring — and it
    is additive: the two keys the brief specifies are unchanged.
    """
    if not peers:
        raise ValueError("multiples() needs at least one peer")
    earners = [p for p in peers if p.net_income > 0.0]
    if not earners:
        raise ValueError(
            "no peer has positive net income, so no P/E statistic can be formed"
        )
    return {
        "ev_ebitda": _stats([p.ev / p.ebitda for p in peers]),
        "ev_ebit": _stats([p.ev / p.ebit for p in peers]),
        "pe": _stats([p.market_cap / p.net_income for p in earners]),
    }


def intensity_matched_multiple(da_over_ebitda: float, peers: list[Peer]) -> float:
    """Peer EV/EBITDA interpolated at a given D&A/EBITDA, post-IFRS 16.

    The peer set's EV/EBITDA spans 5.27x to 10.12x while its D&A/EBITDA spans
    21.4% to 60.8%, and the two move together far more than the sector label
    would suggest. Comparing Greggs' terminal EBITDA multiple to the raw median
    therefore compares two different capital intensities. This reads the peer
    curve at the intensity actually in question.

    Linear interpolation between the two BRACKETING peers, sorted on
    D&A/EBITDA. Deliberately local rather than fitted, because the relationship
    is NOT monotonic across the whole set — Mitchells & Butlers at 29.3% trades
    at 6.45x while Whitbread at 39.7% trades at 8.73x, the wrong way round — so
    a single fitted line through five points would smooth over a genuine
    inversion and give false precision. A local interpolation claims only what
    the two nearest observations support.

    Raises outside the peer range rather than extrapolating. That is a live
    case, not a defensive flourish: the BEAR terminal year's D&A/EBITDA is
    62.26%, above SSP's 60.84%, so no peer brackets it.
    """
    if not peers:
        raise ValueError("intensity_matched_multiple() needs at least one peer")
    points = sorted(
        ((p.ebitda - p.ebit) / p.ebitda, p.ev / p.ebitda) for p in peers
    )
    if not points[0][0] <= da_over_ebitda <= points[-1][0]:
        raise ValueError(
            f"D&A/EBITDA of {da_over_ebitda:.4f} is outside the peer range "
            f"[{points[0][0]:.4f}, {points[-1][0]:.4f}]; no peer brackets it and "
            "extrapolating a five-point curve would be inventing a comparable"
        )
    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        if x0 <= da_over_ebitda <= x1:
            if x1 == x0:
                return (y0 + y1) / 2.0
            return y0 + (y1 - y0) * (da_over_ebitda - x0) / (x1 - x0)
    raise AssertionError("unreachable: the range check above guarantees a bracket")


def implied_value_from_comps(
    ebitda: float, median_multiple: float, net_debt: float, leases: float, shares: float
) -> float:
    """Comps-implied share price in pence.

        (EBITDA x multiple - net debt - lease liabilities) / shares

    ``net_debt`` is the financial net debt EXCLUDING leases and ``leases`` the
    lease liability, deducted separately so the caller cannot pass a
    lease-inclusive net debt and a lease-inclusive multiple and deduct the
    leases twice. Both are opening (FY2025) balances, matching
    ``valuation.equity_bridge()``.

    At the peer median of 7.5376x on FY2025 EBITDA of £351.2m this gives
    2,188.9p, against the peer minimum 1,412.3p and maximum 3,073.7p, and
    against a traded 1,964.0p.
    """
    if shares <= 0.0:
        raise ValueError(f"share count must be positive, got {shares}")
    equity_value = ebitda * median_multiple - net_debt - leases
    return equity_value / shares * PENCE_PER_POUND


# ---------------------------------------------------------------------------
# The basis conversion
# ---------------------------------------------------------------------------

def post_ifrs16_multiple(
    pre_ifrs16_multiple: float,
    ebitda_post: float,
    lease_liabilities: float,
    fixed_lease_payments: float,
) -> float:
    """Restate an EV/EBITDA multiple struck pre-IFRS 16 onto the post-IFRS 16 basis.

        EV_post   = EV_pre + L
        EBITDA_post = EBITDA_pre + R

    so, writing ``m`` for the multiple,

        m_post = (m_pre x (EBITDA_post - R) + L) / EBITDA_post
               = m_pre - (m_pre x R - L) / EBITDA_post
               = m_pre - (R / EBITDA_post) x (m_pre - L / R)

    ``R`` is the FIXED cash lease cost — principal repaid plus lease interest —
    because that is the charge IFRS 16 removed from the P&L, and ``L`` is the
    lease liability that replaced it in the balance sheet.

    The third form is the one to read. The conversion is not a haircut on the
    denominator: it is the gap between the multiple the business trades on and
    the multiple at which its own leases are capitalised, scaled by how big
    rent is relative to EBITDA. It is exactly NEUTRAL at ``L / R == m_pre`` and
    it would RAISE the multiple if leases capitalised above it.
    """
    if ebitda_post <= 0.0:
        raise ValueError(f"post-IFRS 16 EBITDA must be positive, got {ebitda_post}")
    if fixed_lease_payments <= 0.0:
        raise ValueError(
            f"fixed lease payments must be positive, got {fixed_lease_payments}"
        )
    return pre_ifrs16_multiple - (
        pre_ifrs16_multiple * fixed_lease_payments - lease_liabilities
    ) / ebitda_post


# ---------------------------------------------------------------------------
# Greggs on its own comps table
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class GreggsTradingMultiples:
    """Greggs at the observed market price, on the same basis as ``PEERS``."""

    share_price_pence: float
    market_cap: float
    net_debt_incl_leases: float
    ev: float
    ebitda: float
    ebit: float
    net_income: float
    ev_ebitda: float
    ev_ebit: float
    pe: float


def greggs_trading_multiples(historicals: list[HistoricalYear]) -> GreggsTradingMultiples:
    """Greggs' own traded multiples on the last reported year.

    EBITDA is built the same way the model builds it — revenue less cost of
    sales less ``operating_costs``, which ``inputs/greggs.py`` defines as the
    residual net of D&A and impairment — so this is the same £351.2m the
    forecast starts from, and it carries the same £6.9m impairment add-back the
    peers' underlying measures carry. Net debt is the opening balance the
    equity bridge uses: £25.0m borrowings less £70.8m cash plus £449.8m leases
    = £404.0m.

    The price is a 5 August 2026 observation against a 27 December 2025 balance
    sheet. That seven-month mismatch is the ordinary convention for a comps
    page — every peer here has it too — but it is a mismatch, and the EV is
    that much rougher for it.
    """
    last = historicals[-1]
    ebitda = last.revenue.value - last.cost_of_sales.value - last.operating_costs.value
    da = (
        last.depreciation_ppe.value
        + last.depreciation_rou.value
        + last.amortisation.value
    )
    ebit = ebitda - da
    net_debt = last.borrowings.value - last.cash.value + last.lease_liabilities.value
    market_cap = (
        GREGGS_SHARE_PRICE.value / PENCE_PER_POUND * GREGGS_SHARES_OUTSTANDING.value
    )
    ev = market_cap + net_debt
    net_income = HIST_NET_INCOME[-1]
    return GreggsTradingMultiples(
        share_price_pence=GREGGS_SHARE_PRICE.value,
        market_cap=market_cap,
        net_debt_incl_leases=net_debt,
        ev=ev,
        ebitda=ebitda,
        ebit=ebit,
        net_income=net_income,
        ev_ebitda=ev / ebitda,
        ev_ebit=ev / ebit,
        pe=market_cap / net_income,
    )
