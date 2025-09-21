import numpy as np

from app.core.simple_filters import PriceVsMAFilter
from app.models.simple_requests import NumericRange


def _build_sample_data(length: int) -> np.ndarray:
    dtype = [
        ('date', 'datetime64[D]'),
        ('open', 'f8'),
        ('high', 'f8'),
        ('low', 'f8'),
        ('close', 'f8'),
        ('volume', 'f8'),
    ]
    data = np.zeros(length, dtype=dtype)
    start = np.datetime64('2024-01-01')
    data['date'] = start + np.arange(length)

    prices = np.linspace(100.0, 120.0, length)
    data['open'] = prices
    data['close'] = prices
    data['high'] = prices
    data['low'] = prices
    data['volume'] = 1_000_000
    return data


def test_price_vs_ma_filter_uses_available_history_when_insufficient_data():
    data = _build_sample_data(150)
    price_vs_ma = PriceVsMAFilter(period=200, ratio_range=NumericRange(min=0.5, max=2.0))

    result = price_vs_ma.apply(data, 'TEST')

    # All rows except the first should qualify because open == close and ratio == 1
    assert not result.qualifying_mask[0]
    assert np.all(result.qualifying_mask[1:])

    metrics = result.metrics
    assert 'error' not in metrics
    assert metrics['total_days_with_ma'] == len(data) - 1
    assert metrics['ma_effective_window_max'] == len(data) - 1
    assert metrics['ma_effective_window_min'] == 1
