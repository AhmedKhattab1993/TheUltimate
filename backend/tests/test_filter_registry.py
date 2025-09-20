import sys
from pathlib import Path

import pytest

BACKEND_PATH = Path(__file__).resolve().parents[1]
if str(BACKEND_PATH) not in sys.path:
    sys.path.insert(0, str(BACKEND_PATH))

from app.registry import filter_registry


def test_filter_registry_builds_simple_filters():
    payload = {
        "priceRange": {
            "enabled": True,
            "values": {
                "min_price": 2.5,
                "max_price": 12.0,
            },
        }
    }

    filters = filter_registry.build_simple_filters(payload)

    assert filters.price_range is not None
    assert filters.price_range.min_price == 2.5
    assert filters.price_range.max_price == 12.0


def test_filter_registry_rejects_unknown_filter():
    payload = {"unknownFilter": {"enabled": True, "values": {}}}

    with pytest.raises(ValueError) as exc:
        filter_registry.build_simple_filters(payload)

    assert "Unknown filter" in str(exc.value)
