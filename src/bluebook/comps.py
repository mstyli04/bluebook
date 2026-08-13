"""Trading comparables: five UK-listed food and hospitality names, post-IFRS 16.

This is the first module in the model that brings evidence from OUTSIDE Greggs'
own filings. Everything before it was internally consistent but self-referential:
the terminal value, the WACC and the exit multiple were all calibrated against
each other. The peer set exists to settle one question the model could not settle
on its own — what multiple of EBITDA a business like this actually changes hands
at.

**It now SETS ``drivers.exit_ev_ebitda`` rather than merely arguing with it.**
Owner ruling, fix round 1: the three scenario multiples are derived from this
peer set by ``exit_multiple_from_peers()`` and are 5.07 / 6.31 / 7.24,
replacing the judgement figures 8.5 / 10.0 / 11.5 that rested on nothing. That
changed no valuation output — the headline price is struck on Gordon — and the
residual disagreement with Gordon is deliberately left standing.

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
PROVENANCE: the peer figures are NOT sourced to the standard Greggs' are
--------------------------------------------------------------------------
Controller ruling, fix round 1: this asymmetry gets stated rather than left for
a reader to infer from a table that presents both at once.

* **Greggs' own figures** (``inputs/greggs.py``) were read line by line from the
  FY2023/24/25 annual report PDFs, with the printed page number recorded beside
  every value, and each year's ``operating_costs`` residual written out so it can
  be re-derived without reopening the filings.
* **The peer figures below were not.** They come from each company's results
  announcement — the correct primary document, and each one is named with its RNS
  date beside the peer — but read through a summarising fetcher rather than from
  the source document line by line. **No page references exist for them**, and
  they should not be treated as carrying the same evidentiary weight as the
  Greggs numbers.

What partially offsets that: **every peer's figures cross-check internally
against five or six independently quoted lines from the same announcement.**
SSP: 364.1 + 276.8 + 46.3 = 687.2 from three printed figures, and the same
687.2 a second way off the post-IFRS 16 lines, 269.1 + 276.8 + 130.8 + 10.5;
269.1 - 222.8 = 46.3 against the reconciliation table's operating-cost impact,
276.8 - 321.8 - 1.3 = -46.3 against the narrative sentence read whole,
269.1 - 86.1 = 183.0 against the printed non-underlying total,
321.9 + 920.8 = 1,242.7, and
118.5 + 797.7 + 1,242.7 - 342.0 = 1,816.9 against the printed net debt.
Domino's:
309.2 - 24.6 = 284.6, 22.9 + 217.2 = 240.1, and 7.9 + 6.6 + 7.6 + 0.6 = 22.7
against the printed D&A-and-impairment line. Wetherspoon:
72.205 + 2.003 + 0.218 + 39.939 = 114.365 against the stated total, and
52.042 + 355.161 = 407.203. M&B: 843 + 434 = 1,277, 96 + 3 + 36 = 135, and
322 + 8 = 330 against the printed adjusted operating profit. Whitbread:
175.6 + 4,347.5 = 4,523.1 and 649 - 185 = 464.

**What those ties do and do not bound — and this paragraph replaces a sentence
that was false.** It previously read: "figures that tie across that many
separately reported lines are very unlikely to be confabulated." That is true of
CONFABULATION and true of TRANSCRIPTION, and it is worthless against the error
that actually got through. Domino's EBIT shipped for one round at £105.3m,
built as 133.9 - 28.6 with 28.6 = 7.9 + 6.6 + 14.1. **Every one of those figures
is real and the arithmetic is exact.** It was wrong because 14.1 is TOTAL
amortisation while 133.9 is an UNDERLYING measure, so the subtraction mixed two
bases — and the company's own printed bridge (133.9 - 22.7 = 111.2) says so.
EV/EBIT was overstated 5.6%.

So, precisely:

* internal ties bound **transcription** error — a digit typed wrong, a component
  omitted from a sum;
* they bound **nothing at all** about whether the right figure was selected.
  A basis-selection error produces an arithmetically perfect table. **Reading a
  figure off the wrong COLUMN belongs here, not in the bullet above** — an
  earlier version of this paragraph listed it as bounded, and fix round 4
  disproved that: had SSP's associates been taken as 8.4 from the pre-IFRS 16
  column instead of 8.2 from the underlying IFRS column, 8.2 + 0.2 = 8.4 would
  still tie and no cross-check in this module would have broken. Multi-column
  APM reconciliations are where this sheet's remaining risk lives, and the only
  defence is naming the column beside the number, which every peer note now does.
* **A third class, and the paragraph enumerated only two until fix round 4:
  quoting a source SHORT OF ITS FULL STOP.** Fix round 3 read SSP's explanatory
  sentence as far as "the recognition of fixed rents of £(321.8)m" and stopped
  before its final clause, "and the gain on derecognition of leases of £(1.3)m".
  That produced a £1.3m "unreconciled residual" which was then explained with
  four false claims and pinned in a test. Neither internal ties nor the remedy
  in the bullet below would have caught it: no figure was mis-selected and no
  arithmetic was wrong — the error was in the NARRATIVE that explains the
  reconciliation. The rule that does catch it is procedural: quote to the full
  stop, or mark the elision explicitly. An em-dash closing a quotation
  mid-sentence hides the truncation from the next reader, including from yourself.
* Neither the comment audit nor the mutation sweep could catch any of the three,
  and neither ever will: the audit re-checks each claim against the value beside
  it, and the value beside it was self-consistent; mutation testing perturbs
  shipped values and asks whether a test notices, which says nothing about
  whether the shipped value was the right line to take, and nothing at all about
  prose.
* The thing that catches a basis-selection or wrong-column error is **reading the
  company's own reconciliation** and preferring its printed subtotal to any
  build-up. Where a peer prints the subtotal, this module now uses it and says
  so; where it does not, the build-up is written out with the basis of every
  component named. Note this remedy is silent on the third class above, which is
  why that class is stated separately rather than folded in.

One residual defence, and it is weak: the old comment was **self-refuting on its
own face** — it said the £28.6m was added back to a statutory PBIT of £101.1m,
and 101.1 + 28.6 = 129.7, not the 133.9 on the line above. A reader checking the
comment against itself, rather than each figure against its source, would have
found it. That is now the standard applied to every peer comment here.

--------------------------------------------------------------------------
PRINTED versus CONSTRUCTED: which figure rests on what
--------------------------------------------------------------------------
Because two of the five peers turned out to carry basis errors, a reader needs
to see which figures are the company's own printed subtotals and which this
module built. **All five EBITs are printed. Two of five EBITDAs rest on printed
figures; three are constructed**, and no peer prints a post-IFRS 16 UNDERLYING
EBITDA except Domino's. The word "underlying" is load-bearing and an earlier
version of this sentence omitted it, which made it false: M&B prints an
"EBITDA before movements in the valuation of the property portfolio" of £460m
and Whitbread an "Adjusted EBITDAR" of £1,074m, both post-IFRS 16. Neither is
on the underlying basis this module needs — see the two cells below.

    peer          EBITDA                              EBIT
    ----------------------------------------------------------------------
    Domino's      PRINTED "Underlying EBITDA1 133.9"  PRINTED "Underlying
                                                       EBIT1 111.2"
    SSP           PRINTED subtotal + PRINTED           PRINTED "Underlying
                  reconciliation line: 364.1 +         operating profit 269.1"
                  276.8 + 46.3 = 687.2. No
                  post-IFRS 16 EBITDA is printed.
    Wetherspoon   CONSTRUCTED 146.409 + 114.365.       PRINTED "Operating
                  The printed £203.3m is PRE-IFRS       profit 146.4" before
                  16 and is not used.                   separately disclosed items
    M&B           CONSTRUCTED 330 + 135 = 465. M&B      PRINTED "Adjusted
                  DOES print an EBITDA — "EBITDA        operating profit £330m"
                  before movements in the valuation
                  of the property portfolio" £460m —
                  but it is struck off STATUTORY
                  operating profit and carries £5m of
                  separately disclosed items, so it is
                  not on the underlying basis and is
                  NOT used. 465 - 460 = 5 ties.
    Whitbread     CONSTRUCTED 649 + 209 + 218 =        PRINTED "Adjusted
                  1,076. The printed "Adjusted          operating profit £649m"
                  EBITDAR" £1,074m differs by £2m
                  and is NOT used.

**Why that pattern is reassuring where it matters.** The derived exit multiple
depends only on the peer **median EV/EBIT** — and every one of the five EBIT
figures is a printed operating-profit line. The load-bearing statistic in this
whole module therefore rests entirely on printed subtotals. The constructed
EBITDAs feed the EV/EBITDA range, the comps-implied value bar and the
capital-intensity cross-check, all of which are presentational or corroborative
rather than inputs to ``drivers``.

Line-by-line verification status, so nobody re-does settled work or trusts
unsettled work: Wetherspoon and Whitbread were verified line by line at review;
Domino's and M&B in fix round 2, each against a printed subtotal that corrected
a shipped figure; SSP in fix round 3, against printed subtotals with no figure
changing.

**One residual is left standing rather than absorbed**, flagged again at the
figure itself: **Whitbread £2m** (0.2% — the gap between the derived post-IFRS 16
EBITDA of £1,076m and the company's stated "Adjusted EBITDAR" of £1,074m, which
the announcement does not explain). **The SSP £1.3m was never a residual at
all** — see the note beside SSP. It is a printed line item, the gain on
derecognition of leases, and it went missing because SSP's narrative sentence
was quoted before its third clause. Read whole, the sentence ties to the
reconciliation table exactly: 276.8 - 321.8 - 1.3 = -46.3. Prose and table
agree; what was incomplete was the reading. So the only unexplained gap left
standing in this module is Whitbread's £2m.

Practical consequence: the peer set is strong enough to rule out a 10x exit
multiple and to set one at ~6.3x, which is what it is used for. It is not strong
enough to carry a valuation on its own, and the headline share price does not
depend on it — that is struck on Gordon.

--------------------------------------------------------------------------
How comparable each name actually is — read this before the median
--------------------------------------------------------------------------
Greggs is **leased-estate food-to-go retail**: a shop estate that is
overwhelmingly leasehold (the £449.8m lease liability against £832.1m of owned
PP&E is the only measure of that in this repo, and no shop count is recorded
anywhere in it, so none is asserted here), vertically integrated manufacturing
and distribution, very high transaction volume at a very low ticket. **Not one of
the five is a close structural match to that**, and the honest thing is to say
where each one breaks rather than let "UK food and hospitality" do the work.

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
  freehold estate carried at valuation, so its 6.38x is partly a property
  multiple rather than a trading one, and the format is sit-down dining. It is
  also the one peer whose EV/EBIT (8.99x) is far off the other four, which is
  consistent with property value sitting in EV without a matching earnings
  stream.
* **Domino's Pizza Group — weight DOWN hardest.** An asset-light FRANCHISOR:
  revenue is royalties and supply-chain sales to franchisees, and the
  franchisees hold the shop leases, which is why its D&A/EBITDA is 17.0%
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
    Mitchells & Butlers   6.38x                    29.0%
    J D Wetherspoon       7.54x  <- median         43.9%
    Whitbread             8.73x                    39.7%
    Domino's Pizza Group 10.12x                    17.0%

That is a 1.92x spread between the cheapest and dearest name in one sector, and
the third column is a large part of the explanation. **Post-IFRS 16 EV/EBITDA in
this sector is substantially a reading of capital intensity, not of rating.** The
same five names on EV/EBIT run 8.99x (M&B) to 14.48x (Whitbread), a **1.61x**
spread, with a median of 13.43x. ``test_ev_ebit_is_a_somewhat_tighter_spread_
than_ev_ebitda`` pins the comparison.

**1.61x against 1.92x is SOMEWHAT tighter, not much tighter, and an earlier
version of this docstring overstated it.** It claimed 1.59x, which depended on
Mitchells & Butlers being carried on its own statutory-based EBITDA measure while
the other four were on underlying — the basis inconsistency this round corrected.
Putting M&B on underlying moved its EV/EBIT from 9.13x to 8.99x and widened the
spread. Correcting Domino's EBIT (see below) moved its EV/EBIT from 12.87x to
12.19x, widening it again. The motivating observation survives — capital
intensity explains a real part of the EV/EBITDA dispersion — but it is weaker
than first stated, and the test now asserts the weaker truth.

Greggs itself, at 1,964.0p, is 6.85x EV/EBITDA and 13.10x EV/EBIT on FY2025.
Against the medians that is 9.1% cheap on EBITDA and 2.4% cheap on EBIT.
**But the 2.4% is not a like-for-like comparison — see the impairment
asymmetry immediately below, which puts the honest figure at 6.0% cheap.** On
P/E Greggs is 16.39x against a peer median of 13.24x, i.e. at a PREMIUM, which
is the same fact seen from the other side: Greggs carries net CASH excluding
leases, so its equity is less geared than the peers' and capitalises the same
enterprise more dearly.

--------------------------------------------------------------------------
IMPAIRMENT ASYMMETRY on EBIT — a known bias, and it flatters the model
--------------------------------------------------------------------------
``inputs/greggs.py`` folds net impairment into ``depreciation_ppe`` and
``depreciation_rou``, a Task 3 convention adopted so the FCF bridge does not
double-count non-cash write-downs against capex. On **EBITDA** that is harmless
and already noted above: the add-back puts Greggs on the same pre-impairment
footing as the peers' underlying measures. **On EBIT it runs the other way and
was not flagged.** Greggs' EBIT is struck AFTER £6.9m of FY2025 impairment;
every peer's underlying EBIT is struck BEFORE its impairments. The two are not
comparable, and the direction is not neutral:

    Greggs EBIT as the model carries it      £183.7m  ->  EV/EBIT 13.10x, 2.4% cheap
    Greggs EBIT on the peers' basis (+£6.9m) £190.6m  ->  EV/EBIT 12.63x, 6.0% cheap

The same bias runs through the derived exit multiple, because Task 9's
``ppe_depreciation_rate`` (14.23%) and ``rou_depreciation_rate`` (17.61%) were
anchored on FY2025 depreciation figures that INCLUDE impairment, so the terminal
D&A share is overstated too:

                     terminal D&A/EBITDA    shipped multiple   residual vs Gordon
    Bear   as built        62.26%                5.07x              +34.67%
           peers' basis    59.74%                5.41x              +43.70%
    Base   as built        52.98%                6.31x              +21.65%
           peers' basis    50.84%                6.60x              +27.24%
    Bull   as built        46.12%                7.24x              +16.05%
           peers' basis    44.25%                7.49x              +20.06%

**Direction, stated plainly because it cuts against the model: the bias
UNDERSTATES the derived exit multiple by 3.46% (Bull) to 6.67% (Bear), and
therefore UNDERSTATES the residual disagreement with Gordon.** On Base the honest
residual is +27.24%, not the +21.65% the shipped figures report. The bias
flatters the model's internal coherence, which is exactly the kind of bias that
has to be named by whoever finds it rather than left for a reader to discover.

**Not adjusted for**, deliberately. The root cause is the Task 3 inputs
convention carried through Task 9's depreciation rates; correcting it means
splitting impairment out of the depreciation fields, which changes the fixed-asset
schedule, the FCF bridge and the terminal anchors. That is a change to earlier
tasks' interfaces and is out of scope here. It is disclosed with its magnitude
and its sign, and ``greggs_trading_multiples()`` returns the peers-consistent
EBIT alongside the as-reported one so the gap is computable rather than
prose-only.

--------------------------------------------------------------------------
The basis conversion, and why the handover's estimate was wrong
--------------------------------------------------------------------------
**Everything in this section and the next concerns the SUPERSEDED driver
values of 8.5 / 10.0 / 11.5.** They are kept because they are the evidence
that forced the recalibration, and because the conversion arithmetic is a
finding in its own right. The shipped driver is 5.07 / 6.31 / 7.24 and
is already post-IFRS 16 — do NOT put it through ``post_ifrs16_multiple()``.

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
7.54x, converted superseded driver 9.03x. **The peers do not vindicate
Gordon.** A terminal
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

   **And the shipped rule does not apply that fade — a concession that cuts
   against the derivation.** ``exit_multiple_from_peers()`` takes the peers'
   TRAILING EV/EBIT and applies it to the TERMINAL year with no deceleration
   adjustment at all. So the argument in this paragraph, which is used to defend
   Gordon sitting below the peers, applies with equal force against the derived
   exit multiple: some part of the 6.31x is growth the terminal year does not
   have. That means **part of the residual gap attributed below to
   reinvestment-intensity opinion is really this omission**, and the split
   between the two is not quantified here — fading the peer multiple properly
   would need a growth rate and a duration for each peer, none of which is
   sourced. The residual is therefore an upper bound on the reinvestment
   disagreement, not a measurement of it.

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

A. the SUPERSEDED driver against Gordon, 10.00x -> 5.19x, 4.81 turns, ADDITIVE:

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

* ``exit_ev_ebitda`` at 8.5 / 10.0 / 11.5 was not supportable on this evidence
  in any basis. Converted to post-IFRS 16 it was 7.70x / 9.03x / 10.40x, against
  a capital-intensity-matched peer read of 6.32x for Base.
  **Owner ruling, fix round 1: it is now derived.** See
  ``exit_multiple_from_peers()`` and the derivation beside each scenario in
  ``assumptions.py``. The shipped multiples are **5.07 / 6.31 / 7.24**,
  each being the peer median EV/EBIT of 13.4277x read at that scenario's own
  terminal D&A/EBITDA (62.26% / 52.98% / 46.12%). The old +/-1.5 offsets were
  NOT carried forward — they were attached to a number resting on nothing — so
  the spread narrowed from 3.0 turns to 2.17, and the Bull > Base > Bear
  ordering now falls out of the derivation instead of being imposed.
  **This changed no valuation output.** The headline implied price is struck on
  Gordon and is 624.7p / 1,506.5p / 2,560.7p before and after; what moved is the
  reported exit-multiple terminal value (Base £4,882.4m -> £3,082.5m) and the
  disagreement with Gordon, from 1.84x-2.26x down to 1.16x-1.35x.
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
WHAT THE "EXIT MULTIPLE" BAR NOW CONTAINS — read this before Tasks 14 and 16
--------------------------------------------------------------------------
Because ``EV/EBITDA == EV/EBIT x (1 - D&A/EBITDA)`` is an identity, and because
the derived driver IS ``peer median EV/EBIT x (1 - terminal D&A/EBITDA)``,

    terminal_value_exit_multiple  ==  peer median EV/EBIT  x  terminal EBIT

exactly, in all three scenarios. The EBITDA in the calculation cancels. **The
exit-multiple terminal value is no longer an EBITDA method at all — it is one
peer's EV/EBIT multiple applied to the model's own terminal EBIT.** With the
shipped two-decimal literals the identity holds to within ±0.07% (the rounding);
``test_the_exit_multiple_tv_is_identically_peer_ev_ebit_times_terminal_ebit``
pins it.

Three consequences for anyone presenting this:

* **The football field's two DCF bars are less independent than they look.** One
  is labelled "DCF (Gordon)" and one "DCF (exit multiple)", but the second now
  contains no information beyond J D Wetherspoon's EV/EBIT of 13.4277x and the
  model's own terminal EBIT. Labelling it "exit multiple" without saying so
  invites a reader to treat it as a second opinion when it is one observation.
* **It is a single-peer number.** The median of five is the third observation,
  and dropping any of the three highest names moves it -4.6% (SSP or
  Whitbread) or -4.5% (JDW, the median itself) (see
  ``test_the_peer_median_ev_ebit_is_robust_to_dropping_one_peer``). That is the
  honest error bar on the whole exit-multiple bar.
* **Bear's derived multiple of 5.07x sits BELOW every peer's EV/EBITDA**, the
  lowest of which is SSP at 5.27x. That is not a contradiction — it is the
  correct output of applying a peer EV/EBIT to a business more capital-intensive
  than any peer in the set — but it does mean the Bear bar is an extrapolation
  beyond the observed EV/EBITDA range in both directions: its input intensity
  (62.26%) is above every peer's and its output multiple is below every peer's.
  ``test_bears_derived_multiple_sits_below_every_peer_ev_ebitda`` records it.

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

# FY2025 net impairment, as recorded in the comments beside `depreciation_ppe`
# and `depreciation_rou` in inputs/greggs.py. Named here rather than inlined
# because the impairment asymmetry disclosure in the module docstring turns on
# them, and because inputs/greggs.py carries them only in prose - there is no
# impairment field on HistoricalYear to read them from, which is itself part of
# why the asymmetry exists.
FY2025_NET_IMPAIRMENT_PPE = 3.9    # FY2025 AR p.148 (Note 3); 5.5 charge less 1.6 release
FY2025_NET_IMPAIRMENT_ROU = 3.0    # FY2025 AR p.148 (Note 3); 4.9 charge less 1.9 release

# Tolerance on the internal arithmetic of a Peer, £m. The literals below are
# quoted to two decimals against inputs carried to more, so a tie can be out by
# a few thousandths of a million and still be a correct transcription.
_TIE_TOLERANCE = 0.01


# ---------------------------------------------------------------------------
# Market observations — one snapshot, one date
# ---------------------------------------------------------------------------

PRICE_OBSERVATION_DATE = "5 August 2026, 11:45-11:59 GMT"

#: The individual quote times inside that window, recorded per peer in each
#: ``source`` string. The window is 14 minutes wide, so the six quotes are not
#: strictly simultaneous; on a normal trading day that is immaterial next to
#: the seven-month gap between these prices and the balance sheets they are
#: divided into, but it is recorded rather than smoothed.
PRICE_OBSERVATION_WINDOW_MINUTES = 14

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
        # VERIFIED LINE BY LINE against the announcement, fix round 3. SSP was
        # the last peer resting on neither a printed subtotal nor a line-by-line
        # check, and it is the most load-bearing name in the set. No figure
        # changed; what changed is that the EBITDA no longer rests on a
        # four-component build-up. The £1.3m that two earlier rounds carried as
        # an "unreconciled residual" turned out to be a printed line item — the
        # gain on derecognition of leases — omitted by quoting SSP's sentence
        # one clause short. See the note at ``ebitda`` below.
        #
        # Reported net debt of £1,816.9m is the IFRS figure and INCLUDES the
        # £1,242.7m lease liability. It ties to the face of the balance sheet
        # exactly:
        #     short-term borrowings      118.5
        #   + long-term borrowings       797.7
        #   + lease liabilities        1,242.7   (321.9 current + 920.8 non-current)
        #   - cash and equivalents       342.0
        #   = 1,816.9
        # SSP's own headline leverage uses a pre-IFRS 16 net debt of £574.2m,
        # which is NOT used here.
        net_debt_incl_leases=1816.9,
        lease_liabilities=1242.7,    # 321.9 current + 920.8 non-current, per the balance sheet
        minority_interests=186.8,    # balance sheet NCI; SSP consolidates JV concessions
        ev=3622.698,                 # 1,618.998 + 1,816.9 + 186.8
        #
        # EBITDA. **SSP prints NO post-IFRS 16 underlying EBITDA** — the only
        # EBITDA on the page is "Pre-IFRS 16 underlying EBITDA 364.1". So this
        # figure must be constructed, but it is now constructed from three
        # PRINTED figures rather than from a four-component D&A build-up:
        #
        #     pre-IFRS 16 underlying EBITDA                     364.1   (printed)
        #   + depreciation of right-of-use assets               276.8   (printed)
        #   + IFRS 16 impact on underlying operating costs        46.3   (printed,
        #                                     pre-IFRS 16 reconciliation table)
        #   = 687.2
        #
        # That form is EXACT and, importantly, INDEPENDENT OF THE AMORTISATION
        # FIGURE. Pre-IFRS 16 EBITDA already contains PP&E depreciation and
        # amortisation; going to the post-IFRS 16 basis only adds back ROU
        # depreciation and reverses the rent, and the reconciliation table states
        # the net operating-cost effect directly.
        #
        # **There is no £1.3m residual. The £1.3m is a NAMED PRINTED LINE, and
        # the earlier "residual" was an artefact of quoting SSP's sentence
        # one clause short.** The sentence, quoted in full this time:
        #
        #     "Underlying operating profit is £46.3m lower on a pre-IFRS 16
        #      basis, as adding back the depreciation of the right-of-use assets
        #      of £276.8m does not fully offset the recognition of fixed rents
        #      of £(321.8)m AND THE GAIN ON DERECOGNITION OF LEASES OF £(1.3)m."
        #
        # Three components, and they close exactly:
        #     +276.8  depreciation of right-of-use assets, added back
        #     -321.8  recognition of fixed rents
        #     -  1.3  gain on derecognition of leases, reversed out
        #     = -46.3  the printed pre-IFRS 16 operating-profit effect
        #
        # So the narrative and the reconciliation table AGREE PERFECTLY. The
        # rent reversed is £321.8m, exactly as printed — an earlier version of
        # this comment asserted it was really 323.1 (= 276.8 + 46.3) and that
        # the narrative named only "the two largest components". Both claims
        # were false, and so was the framing that "prose lost to the table":
        # nothing lost except an incomplete reading of the prose. The third
        # clause was simply not read. The lesson is about quoting a source to
        # its full stop, and it is SSP's own lesson — it has no connection to
        # the basis-selection error found at Domino's.
        #
        # The £1.3m is already inside the printed 46.3, so it is already inside
        # the 687.2 above; nothing about the EBITDA changes.
        #
        # Amortisation, SETTLED and (still) not load-bearing: the pre-IFRS 16
        # underlying EBITDA reconciliation prints "Amortisation of intangible
        # assets (10.5)" for 2025 (against (8.6) for 2024), and that is
        # consistent with the printed subtotals, 364.1 - 222.8 - 130.8 = 10.5.
        # An earlier version of this comment recorded 10.4-versus-10.5 as an
        # ambiguity the source "cannot settle"; the source does settle it, at
        # 10.5, and independent retrievals of the announcement return that row
        # identically. A figure of (10.4) was also seen somewhere in the same
        # announcement but was never located, and no candidate location is
        # offered here, because naming one would invite the next reader to treat
        # it as probable. What is settled is the row this build-up would use, and
        # that is the whole of what matters. The build-up above needs
        # no amortisation figure at all, so the settlement moves nothing — but
        # it does give a second exact route to the same EBITDA, off the printed
        # post-IFRS 16 lines rather than the pre-IFRS 16 ones:
        #     269.1 + 276.8 + 130.8 + 10.5 = 687.2.
        ebitda=687.2,
        #
        # EBIT is SSP's PRINTED line, "Underlying operating profit 269.1" on the
        # IFRS basis. Two basis checks, which are the ones C1 and I1 turned on:
        #   * the D&A added back above is the UNDERLYING amount. Impairments are
        #     presented SEPARATELY as non-underlying items (goodwill 32.3, PP&E
        #     50.7, right-of-use 33.8, total non-underlying operating items
        #     183.0), so there is no C1-style mixing of an underlying subtotal
        #     with total D&A. 269.1 - 86.1 = 183.0 ties.
        #   * 269.1 EXCLUDES share of profit from associates, which the
        #     "Reconciliation of key underlying profit measures" table shows on
        #     its own line below operating profit. **That row is printed across
        #     three columns and 8.2 is the right one of them**, because this
        #     module is on the IFRS (post-IFRS 16) basis throughout:
        #         Share of profit from associates   8.2   0.2   8.4
        #         (underlying IFRS | impact of IFRS 16 | underlying pre-IFRS 16)
        #     The prior-year row is printed the same way, 5.4 / 0.2 / 5.6. So
        #     8.4 is a real printed figure and is NOT a correction to 8.2 — it is
        #     the pre-IFRS 16 column, the basis this module does not use, and
        #     reading across to it would be the same column-picking error the
        #     Wetherspoon £203.3m and Whitbread "EBITDAR" notes guard against.
        #     EBITDA and EBIT are therefore wholly-consolidated measures.
        #     Strictly, EV should then also deduct the carrying value of those
        #     associates; the announcement does not give it, so it is not
        #     deducted and this note is the disclosure. £8.2m is 3.05% of
        #     underlying EBIT (8.2 / 269.1), so the omission overstates SSP's
        #     EV/EBIT by roughly that order. The same point applies to Domino's,
        #     which also carries associates.
        ebit=269.1,
        # Statutory, and a LOSS: £183.0m of non-underlying charges sit between
        # £269.1m underlying and £86.1m statutory operating profit. Excluded
        # from the P/E statistics by multiples(). Note SSP's UNDERLYING IFRS
        # attributable profit is +88.4 — the sign flip is entirely
        # non-underlying, and the mixed basis (underlying EBITDA/EBIT against
        # statutory net income) is the module-wide convention, not an SSP
        # special case.
        net_income=-74.4,
        source=(
            "SSP Group plc, '2025 Full Year Results Announcement' RNS, 4 December 2025, "
            "year ended 30 September 2025; price stockanalysis.com LON:SSPG "
            "5 August 2026 11:45 GMT"
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
        # Underlying EBITDA as DPG states it, £133.9m, and it IS post-IFRS 16.
        # EBIT is DPG's OWN PRINTED LINE, not a build-up. The income statement
        # bridges:
        #     "Underlying EBITDA 133.9"
        #     "Depreciation, amortisation and impairment (22.7)"
        #     "Underlying EBIT 111.2"
        # and the £22.7m is PP&E depreciation 7.9 + right-of-use depreciation
        # 6.6 + underlying amortisation 7.6 + underlying impairment 0.6 = 22.7
        # exactly.
        #
        # **This corrected a CRITICAL error, and the shape of it is worth
        # keeping.** An earlier version built EBIT as 133.9 - 28.6 = 105.3,
        # where 28.6 = 7.9 + 6.6 + 14.1. Every one of those three figures is
        # real and they sum correctly, but 14.1 is TOTAL amortisation:
        # 7.6 underlying + 6.5 of reacquired-rights amortisation, which is
        # non-underlying. So the build-up mixed an underlying operating measure
        # with total D&A components, understating EBIT and overstating EV/EBIT
        # by 5.6%. The old comment was self-refuting on its own face - it said
        # the 28.6 was added back to statutory PBIT of 101.1, and 101.1 + 28.6
        # is 129.7, not the 133.9 on the line above it. Nothing in the test
        # suite or the internal cross-ties could catch it, because it was a
        # BASIS-SELECTION error and not a transcription error. See the
        # PROVENANCE section for what that means for the rest of this table.
        #
        # Non-underlying items excluded from the £111.2m, per the announcement:
        # reacquired rights amortisation 6.5 and the Shorecal impairment 10.4.
        ebitda=133.9,
        ebit=111.2,
        net_income=58.6,             # attributable to equity holders; £59.0m group total
        source=(
            "Domino's Pizza Group plc, 'Full year results for the 52 weeks ended 28.12.25' "
            "RNS, 10 March 2026; price stockanalysis.com LON:DOM "
            "5 August 2026 11:59 GMT"
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
            "52 weeks ended 27 July 2025; price stockanalysis.com LON:JDW "
            "5 August 2026 11:54 GMT"
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
        # UNDERLYING basis, to match the other four. EBIT is the company's
        # printed "Adjusted operating profit of £330m"; EBITDA adds the £135m of
        # D&A (PP&E 96 + intangibles 3 + right-of-use 36): 330 + 135 = 465.
        #
        # **This corrected a basis inconsistency.** An earlier version used
        # M&B's own "EBITDA before movements in the valuation of the property
        # portfolio" of £460m and an EBIT of 325. That figure is struck off
        # STATUTORY operating profit of £322m (322 + 138 = 460, where the £138m
        # is "depreciation, amortisation and movements in the valuation of the
        # property portfolio", i.e. the £135m of D&A plus the £3m net adverse
        # property revaluation). It therefore still carried £5m of separately
        # disclosed items that the other four peers' underlying measures
        # exclude, so the set was NOT on the identical basis the module claimed.
        #
        # The £8m of separately disclosed items reconciles 322 to 330, and
        # splits: the four impairment/revaluation lines (freehold reversal +11,
        # short leasehold -5, right-of-use -8, goodwill -1) net to the -3
        # property movement already outside the £460m, leaving -3 contingent
        # consideration, -3 pension past-service and +1 property disposals = -5
        # inside it. 465 - 460 = 5 ties.
        #
        # Post-IFRS 16 either way: right-of-use depreciation of £36m is in the
        # add-back, and M&B quotes its own leverage as 2.7x EBITDA INCLUDING
        # lease liabilities.
        ebitda=465.0,
        ebit=330.0,
        net_income=177.0,            # profit for the period
        source=(
            "Mitchells & Butlers plc, 'Full Year Results' RNS, 28 November 2025, "
            "52 weeks ended 27 September 2025; price stockanalysis.com LON:MAB "
            "5 August 2026 11:52 GMT"
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
            "52 weeks ended 26 February 2026; price stockanalysis.com LON:WTB "
            "5 August 2026 11:58 GMT"
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


def exit_multiple_from_peers(terminal_da_over_ebitda: float, peers: list[Peer]) -> float:
    """The post-IFRS 16 EV/EBITDA exit multiple the peer set implies.

        exit multiple = peer median EV/EBIT x (1 - terminal D&A / EBITDA)

    **This is the function that sets ``drivers.exit_ev_ebitda``.** The driver
    carries the literal — ``assumptions.py`` cannot import this module without
    closing a cycle, since this module imports ``HIST_NET_INCOME`` from it — and
    ``test_the_shipped_exit_multiples_are_the_peer_derived_ones`` ties the three
    literals back to this function so neither can drift.

    **Why the peer statistic is EV/EBIT and not EV/EBITDA.** EV/EBITDA across
    the five spans 5.27x-10.12x (1.92x) while D&A/EBITDA spans 17.0%-60.8%: the
    EBITDA multiple is substantially reporting capital intensity. On EV/EBIT the
    same five span 8.99x-14.48x (1.61x) and the median is unchanged by dropping
    Mitchells & Butlers, the one peer whose multiple is part property valuation,
    moves it +0.13%.

    **Why it is applied to the TERMINAL intensity.** The multiple values FY2030
    EBITDA of a business the model deliberately makes more capital-intensive
    than today's: Base terminal D&A/EBITDA is 52.98% against FY2025's 47.69%.

    **Why not ``intensity_matched_multiple()``, which answers almost the same
    question.** That function interpolates peer EV/EBITDA directly and agrees to
    within 0.12% at Base and 0.02% at Bull — because the bracketing peers trade
    within 0.26% of each other on EV/EBIT, so the two are the same observation.
    But it REFUSES Bear, whose terminal 62.26% is above every peer. This form
    extends where the interpolation cannot, so all three scenarios come off one
    rule rather than two. The interpolation is kept as the cross-check.
    """
    if not 0.0 <= terminal_da_over_ebitda < 1.0:
        raise ValueError(
            "terminal D&A/EBITDA must be a fraction in [0, 1), got "
            f"{terminal_da_over_ebitda}"
        )
    return multiples(peers)["ev_ebit"]["median"] * (1.0 - terminal_da_over_ebitda)


def intensity_matched_multiple(da_over_ebitda: float, peers: list[Peer]) -> float:
    """Peer EV/EBITDA interpolated at a given D&A/EBITDA, post-IFRS 16.

    The peer set's EV/EBITDA spans 5.27x to 10.12x while its D&A/EBITDA spans
    17.0% to 60.8%, and the two move together far more than the sector label
    would suggest. Comparing Greggs' terminal EBITDA multiple to the raw median
    therefore compares two different capital intensities. This reads the peer
    curve at the intensity actually in question.

    Linear interpolation between the two BRACKETING peers, sorted on
    D&A/EBITDA. Deliberately local rather than fitted, because the relationship
    is NOT monotonic across the whole set — Mitchells & Butlers at 29.0% trades
    at 6.38x while Whitbread at 39.7% trades at 8.73x, the wrong way round — so
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
    # The impairment asymmetry, made computable rather than prose-only. Greggs'
    # EBIT is struck after impairment because inputs/greggs.py folds it into the
    # depreciation fields; every peer's underlying EBIT is struck before. These
    # three fields expose the gap so a caller can compare like with like.
    impairment: float               # £m, FY2025 net impairment inside D&A
    ebit_pre_impairment: float      # £m, the peers-consistent EBIT
    ev_ebit_pre_impairment: float   # the peers-consistent EV/EBIT


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
    # FY2025 net impairment, taken from the amounts inputs/greggs.py records
    # beside depreciation_ppe (3.9) and depreciation_rou (3.0). It is inside
    # `da` above, and therefore deducted from `ebit`, which is what makes `ebit`
    # incomparable with the peers' pre-impairment underlying EBIT.
    impairment = FY2025_NET_IMPAIRMENT_PPE + FY2025_NET_IMPAIRMENT_ROU
    ebit_pre_impairment = ebit + impairment
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
        impairment=impairment,
        ebit_pre_impairment=ebit_pre_impairment,
        ev_ebit_pre_impairment=ev / ebit_pre_impairment,
    )
