import pytest

from bluebook.inputs.greggs import GREGGS_HISTORICALS, GREGGS_SHARE_COUNT
from bluebook.inputs.schema import HistoricalYear


def test_three_historical_years_oldest_first():
    assert len(GREGGS_HISTORICALS) == 3
    labels = [y.label for y in GREGGS_HISTORICALS]
    assert labels == sorted(labels)


def test_every_figure_carries_a_source():
    for year in GREGGS_HISTORICALS:
        for name, field in vars(year).items():
            if name == "label":
                continue
            assert field.source.strip(), f"{year.label}.{name} has no source"


@pytest.mark.parametrize("year", GREGGS_HISTORICALS, ids=lambda y: y.label)
def test_balance_sheet_balances(year: HistoricalYear):
    """Transcription check: assets must equal liabilities plus equity."""
    assets = (
        year.ppe.value
        + year.rou_assets.value
        + year.intangibles.value
        + year.inventories.value
        + year.trade_receivables.value
        + year.cash.value
        + year.other_assets.value
    )
    liabilities_and_equity = (
        year.trade_payables.value
        + year.lease_liabilities.value
        + year.borrowings.value
        + year.other_liabilities.value
        + year.equity.value
    )
    assert assets == pytest.approx(liabilities_and_equity, abs=0.5)


def test_share_count_is_positive():
    assert GREGGS_SHARE_COUNT.value > 0
