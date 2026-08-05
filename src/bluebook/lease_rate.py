"""The IFRS 16 lease discount rate — one definition, importable from anywhere.

A leaf module. It imports ``inputs/greggs.py`` and nothing else, and in
particular it does not touch ``Drivers``, so both ``assumptions.py`` and
``schedules/leases.py`` can import it in any order without a cycle.

--------------------------------------------------------------------------
Why this module exists
--------------------------------------------------------------------------
The rate has two consumers with opposite import directions:

* ``schedules/leases.py`` charges lease interest at it, and imports
  ``Drivers`` from ``assumptions.py``;
* ``assumptions.py`` blends it with the RCF rate to build
  ``BLENDED_COST_OF_DEBT``, the WACC's cost of debt.

So ``assumptions`` cannot import ``schedules.leases`` — that closes a cycle.
It is a genuine break, not a stylistic worry: with ``assumptions.py``
importing the rate from the schedule, ``import bluebook.assumptions`` works
while ``import bluebook.schedules.leases`` raises

    ImportError: cannot import name 'LEASE_DISCOUNT_RATE' from partially
    initialized module 'bluebook.schedules.leases' (most likely due to a
    circular import)

because the schedule reaches its ``from bluebook.assumptions import Drivers``
line before it has defined the rate. Fix round 2 avoided that by duplicating
the derivation in both modules with an equality test guarding them. Round 3
replaced the duplication with this module, which is the version that survives
new importers arriving in either order.

--------------------------------------------------------------------------
The rate
--------------------------------------------------------------------------
Lease interest is NOT charged at ``drivers.cost_of_debt``. An IFRS 16 lease
liability is discounted at the rate implicit in the lease (or the incremental
borrowing rate), which for a portfolio of shop leases signed over many years
is a different — and here materially lower — number than any borrowing rate
Greggs faces today. The rate is read off the filings:

    LEASE_DISCOUNT_RATE = FY2025 interest on lease liabilities
                            / FY2025 opening lease liability
                        = 16.7 / 415.1 = 4.0231%

Cross-checked against the one other year that admits a clean read. Greggs
carried nil borrowings at both ends of FY2024 (``borrowings`` = 0.0 in FY2023
and FY2024), so that year's entire finance cost is essentially lease interest:

    FY2024: finance_costs 13.6 / FY2023 closing lease liability 319.6 = 4.26%

which is 4.0231% plus the small non-lease remainder still inside the total —
the right answer from an independent year, in the right direction.

--------------------------------------------------------------------------
SCHEMA GAP
--------------------------------------------------------------------------
``GREGGS_FY2025_LEASE_INTEREST`` is a bare transcribed literal. Every other
figure in this model is derived from ``GREGGS_HISTORICALS`` precisely so a
page citation cannot go stale against the data; this one cannot be, because
``inputs/schema.py`` has no ``lease_interest`` field. ``finance_costs`` is a
single line bundling lease interest with RCF interest and a 0.7 exceptional
(18.1 total in FY2025), so 16.7 cannot be divided out programmatically.

Closing it needs a ``lease_interest`` field on ``HistoricalYear`` — an
``inputs/`` change, out of scope for Task 9. Until then the literal has to be
re-checked against the filing by hand.

**The gap got more important in fix round 2 and this is worth knowing.** This
rate used to set only ``schedules/leases.py``'s lease interest, a below-EBIT
P&L line that unlevered FCF never touches — so an error in it moved the
three-statement model and not the valuation. It now also sets
``BLENDED_COST_OF_DEBT``, hence the WACC, hence the entire DCF. Sensitivity is
about 5p per share per 10bp of error in the rate, so materiality is still low,
but a figure that reaches the headline number deserves a schema field rather
than a hand-checked literal.

The denominator does NOT have that problem: it is read from
``GREGGS_HISTORICALS``. ``GREGGS_FY2024_CLOSING_LEASE_LIABILITY`` below is a
transcription of the same figure kept deliberately as a cross-check, pinned
against the derived value by
``test_lease_rate_denominator_is_the_fy2024_closing_liability``. That pairing
preserves what the round-2 duplication accidentally bought: one literal and
one derived value checked against each other, which guards the figure, the
source and the YEAR of the source at once.
"""

from __future__ import annotations

from bluebook.inputs.greggs import GREGGS_HISTORICALS

# Transcribed: no schema field exists for it. See "SCHEMA GAP" above.
GREGGS_FY2025_LEASE_INTEREST = 16.7  # FY2025 AR p.128 (of 18.1 total finance costs)

# FY2024's closing lease liability is FY2025's opening one. Transcribed here
# purely as a cross-check on the derived value below — the derivation is what
# the rate uses.
GREGGS_FY2024_CLOSING_LEASE_LIABILITY = 415.1  # FY2024 AR p.129

# Derived, so it cannot drift from the transcribed balance sheet.
LEASE_DISCOUNT_RATE = (
    GREGGS_FY2025_LEASE_INTEREST / GREGGS_HISTORICALS[-2].lease_liabilities.value
)  # ~4.02%
