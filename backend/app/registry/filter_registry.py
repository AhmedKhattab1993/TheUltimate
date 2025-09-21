"""Filter registry that powers both API and Lean orchestration."""

from __future__ import annotations

from functools import lru_cache
from typing import Dict, Iterable, List, Optional

from pydantic import ValidationError

from ..models.simple_requests import (
    GapParams,
    NumericRange,
    PreviousDayDollarVolumeParams,
    PriceVsMAParams,
    RSIParams,
    RelativeVolumeParams,
    SimpleFilters,
    SimplePriceRangeParams,
)
from .schemas import FilterControl, FilterDefinition, FilterOption


def _maybe_float(value: object) -> float | None:
    """Convert user-provided control values to floats when possible."""

    if value in (None, "", "null"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid numeric value: {value}") from exc


class FilterRegistry:
    """Provides metadata and helpers to hydrate backend filter models."""

    def __init__(self, definitions: Iterable[FilterDefinition]):
        self._definitions: Dict[str, FilterDefinition] = {
            definition.id: definition for definition in definitions
        }
        self._by_backend_key: Dict[str, FilterDefinition] = {
            definition.backend_key: definition for definition in definitions
        }

        self._param_builders = {
            "price_range": self._build_price_range,
            "price_vs_ma": self._build_price_vs_ma,
            "rsi": self._build_rsi,
            "gap": self._build_gap,
            "prev_day_dollar_volume": self._build_prev_day_dollar_volume,
            "relative_volume": self._build_relative_volume,
        }

    def list(self) -> List[FilterDefinition]:
        """Return filters sorted by `sort_order`."""

        return sorted(self._definitions.values(), key=lambda item: item.sort_order)

    def get(self, filter_id: str) -> Optional[FilterDefinition]:
        """Fetch a filter definition by identifier."""

        return self._definitions.get(filter_id)

    def to_serialisable(self) -> List[dict]:
        """Return metadata in JSON-friendly form."""

        return [definition.model_dump() for definition in self.list()]

    # ------------------------------------------------------------------
    # Backend helpers
    # ------------------------------------------------------------------
    def build_simple_filters(self, payload: Dict[str, dict]) -> SimpleFilters:
        """Construct `SimpleFilters` from a registry-backed payload.

        Args:
            payload: map of filter_id -> {"enabled": bool, "values": {...}}
        """

        params: Dict[str, object] = {}
        errors: Dict[str, str] = {}

        for filter_id, state in payload.items():
            if not state.get("enabled"):
                continue

            definition = self.get(filter_id)
            if not definition:
                errors[filter_id] = "Unknown filter"
                continue

            builder = self._param_builders.get(definition.backend_key)
            if not builder:
                errors[filter_id] = "No backend mapping configured"
                continue

            try:
                params[definition.backend_key] = builder(state.get("values", {}))
            except (ValidationError, ValueError, TypeError) as exc:
                errors[filter_id] = str(exc)

        if errors:
            error_text = "; ".join(f"{key}: {value}" for key, value in errors.items())
            raise ValueError(f"Invalid filter payload -> {error_text}")

        return SimpleFilters(**params)

    # ------------------------------------------------------------------
    # Builders for SimpleFilters
    # ------------------------------------------------------------------
    @staticmethod
    def _build_price_range(values: Dict[str, object]) -> SimplePriceRangeParams:
        min_value = _maybe_float(values.get("min_price"))
        max_value = _maybe_float(values.get("max_price"))
        step_value = _maybe_float(values.get("step"))

        if min_value is None and max_value is None and step_value is None:
            return SimplePriceRangeParams()

        range_kwargs: Dict[str, float] = {}
        if min_value is not None:
            range_kwargs["min"] = min_value
        if max_value is not None:
            range_kwargs["max"] = max_value
        if step_value is not None:
            range_kwargs["step"] = step_value

        return SimplePriceRangeParams(open_price=NumericRange(**range_kwargs))

    @staticmethod
    def _build_price_vs_ma(values: Dict[str, object]) -> PriceVsMAParams:
        period = int(values.get("ma_period", 50))
        min_ratio = _maybe_float(values.get("min_ratio"))
        max_ratio = _maybe_float(values.get("max_ratio"))
        step_ratio = _maybe_float(values.get("step_ratio"))

        range_kwargs: Dict[str, float] = {}
        if min_ratio is not None:
            range_kwargs["min"] = min_ratio
        if max_ratio is not None:
            range_kwargs["max"] = max_ratio
        if step_ratio is not None:
            range_kwargs["step"] = step_ratio

        ratio_range = NumericRange(**range_kwargs) if range_kwargs else NumericRange(min=1.0)
        return PriceVsMAParams(ma_period=period, open_over_ma=ratio_range)

    @staticmethod
    def _build_rsi(values: Dict[str, object]) -> RSIParams:
        period = int(values.get("rsi_period", 14))
        min_value = _maybe_float(values.get("min_value"))
        max_value = _maybe_float(values.get("max_value"))
        step_value = _maybe_float(values.get("step_value"))

        range_kwargs: Dict[str, float] = {}
        if min_value is not None:
            range_kwargs["min"] = min_value
        if max_value is not None:
            range_kwargs["max"] = max_value
        if step_value is not None:
            range_kwargs["step"] = step_value

        rsi_range = NumericRange(**range_kwargs) if range_kwargs else NumericRange(max=30.0)
        return RSIParams(rsi_period=period, rsi_value=rsi_range)

    @staticmethod
    def _build_gap(values: Dict[str, object]) -> GapParams:
        min_gap = _maybe_float(values.get("min_gap_percent"))
        max_gap = _maybe_float(values.get("max_gap_percent"))
        step_gap = _maybe_float(values.get("step_gap_percent"))
        direction = str(values.get("direction", "both"))

        range_kwargs: Dict[str, float] = {}
        if min_gap is not None:
            range_kwargs["min"] = min_gap
        if max_gap is not None:
            range_kwargs["max"] = max_gap
        if step_gap is not None:
            range_kwargs["step"] = step_gap

        gap_range = NumericRange(**range_kwargs) if range_kwargs else NumericRange(min=2.0)
        return GapParams(gap_percent=gap_range, direction=direction)

    @staticmethod
    def _build_prev_day_dollar_volume(
        values: Dict[str, object]
    ) -> PreviousDayDollarVolumeParams:
        min_value = _maybe_float(values.get("min_dollar_volume"))
        max_value = _maybe_float(values.get("max_dollar_volume"))
        step_value = _maybe_float(values.get("step_dollar_volume"))

        if min_value is None and max_value is None and step_value is None:
            return PreviousDayDollarVolumeParams()

        range_kwargs: Dict[str, float] = {}
        if min_value is not None:
            range_kwargs["min"] = min_value
        if max_value is not None:
            range_kwargs["max"] = max_value
        if step_value is not None:
            range_kwargs["step"] = step_value

        return PreviousDayDollarVolumeParams(dollar_volume=NumericRange(**range_kwargs))

    @staticmethod
    def _build_relative_volume(values: Dict[str, object]) -> RelativeVolumeParams:
        min_ratio = _maybe_float(values.get("min_ratio"))
        max_ratio = _maybe_float(values.get("max_ratio"))
        step_ratio = _maybe_float(values.get("step_ratio"))

        range_kwargs: Dict[str, float] = {}
        if min_ratio is not None:
            range_kwargs["min"] = min_ratio
        if max_ratio is not None:
            range_kwargs["max"] = max_ratio
        if step_ratio is not None:
            range_kwargs["step"] = step_ratio

        ratio_range = NumericRange(**range_kwargs) if range_kwargs else NumericRange(min=1.5)
        return RelativeVolumeParams(
            recent_days=int(values.get("recent_days", 2)),
            lookback_days=int(values.get("lookback_days", 20)),
            ratio=ratio_range,
        )


@lru_cache(maxsize=1)
def _default_definitions() -> List[FilterDefinition]:
    """Create the default filter registry definitions."""

    return [
        FilterDefinition(
            id="priceRange",
            backend_key="price_range",
            label="Price Range",
            category="price",
            description="Keep symbols whose open price stays within a configurable range.",
            default_enabled=True,
            controls=[
                FilterControl(
                    control_type="number",
                    field="min_price",
                    label="Minimum Price",
                    description="Lower bound for the opening price",
                    default=1.0,
                    min_value=0.0,
                    step=0.5,
                    unit="$",
                    required=True,
                ),
                FilterControl(
                    control_type="number",
                    field="max_price",
                    label="Maximum Price",
                    description="Upper bound for the opening price",
                    default=100.0,
                    min_value=0.0,
                    step=0.5,
                    unit="$",
                    required=True,
                ),
            ],
            tags=["core", "price"],
            sort_order=10,
        ),
        FilterDefinition(
            id="priceVsMA",
            backend_key="price_vs_ma",
            label="Price vs. Moving Average",
            category="momentum",
            description="Find symbols whose open price is above or below a moving average.",
            default_enabled=False,
            controls=[
                FilterControl(
                    control_type="select",
                    field="ma_period",
                    label="Moving Average Period",
                    default=50,
                    options=[
                        FilterOption(label="20 day", value=20),
                        FilterOption(label="50 day", value=50),
                        FilterOption(label="200 day", value=200),
                    ],
                    required=True,
                ),
                FilterControl(
                    control_type="number",
                    field="min_ratio",
                    label="Min Open/MA Ratio",
                    description="Keep symbols whose open is at least this multiple of the moving average",
                    default=1.0,
                    min_value=0.0,
                    step=0.05,
                ),
                FilterControl(
                    control_type="number",
                    field="max_ratio",
                    label="Max Open/MA Ratio",
                    description="Optional upper bound for the open/MA ratio",
                    min_value=0.0,
                    step=0.05,
                ),
            ],
            tags=["momentum"],
            sort_order=20,
        ),
        FilterDefinition(
            id="rsi",
            backend_key="rsi",
            label="Relative Strength Index",
            category="momentum",
            description="Screen by RSI levels for overbought or oversold conditions.",
            controls=[
                FilterControl(
                    control_type="number",
                    field="rsi_period",
                    label="RSI Period",
                    default=14,
                    min_value=2,
                    max_value=50,
                    step=1,
                    required=True,
                ),
                FilterControl(
                    control_type="number",
                    field="min_value",
                    label="Minimum RSI",
                    description="Optional lower bound for RSI",
                    min_value=0,
                    max_value=100,
                    step=1,
                ),
                FilterControl(
                    control_type="number",
                    field="max_value",
                    label="Maximum RSI",
                    description="Optional upper bound for RSI",
                    default=30.0,
                    min_value=0,
                    max_value=100,
                    step=1,
                ),
            ],
            tags=["momentum"],
            sort_order=30,
        ),
        FilterDefinition(
            id="gap",
            backend_key="gap",
            label="Gap %",
            category="volatility",
            description="Identify opening gaps relative to previous close.",
            controls=[
                FilterControl(
                    control_type="number",
                    field="min_gap_percent",
                    label="Min Gap %",
                    description="Minimum absolute gap percentage",
                    default=2.0,
                    min_value=0.0,
                    max_value=50.0,
                    step=0.5,
                    unit="%",
                ),
                FilterControl(
                    control_type="number",
                    field="max_gap_percent",
                    label="Max Gap %",
                    description="Optional cap on the absolute gap",
                    min_value=0.0,
                    max_value=50.0,
                    step=0.5,
                    unit="%",
                ),
                FilterControl(
                    control_type="select",
                    field="direction",
                    label="Direction",
                    default="both",
                    options=[
                        FilterOption(label="Up", value="up"),
                        FilterOption(label="Down", value="down"),
                        FilterOption(label="Both", value="both"),
                    ],
                    required=True,
                ),
            ],
            tags=["volatility"],
            sort_order=40,
        ),
        FilterDefinition(
            id="prevDayDollarVolume",
            backend_key="prev_day_dollar_volume",
            label="Previous Day Dollar Volume",
            category="liquidity",
            description="Ensure yesterday's dollar volume clears a liquidity floor.",
            controls=[
                FilterControl(
                    control_type="number",
                    field="min_dollar_volume",
                    label="Min Dollar Volume",
                    default=10_000_000,
                    min_value=0,
                    step=1_000_000,
                    unit="$",
                ),
                FilterControl(
                    control_type="number",
                    field="max_dollar_volume",
                    label="Max Dollar Volume",
                    description="Optional cap for yesterday's dollar volume",
                    min_value=0,
                    step=1_000_000,
                    unit="$",
                ),
            ],
            tags=["liquidity"],
            sort_order=50,
        ),
        FilterDefinition(
            id="relativeVolume",
            backend_key="relative_volume",
            label="Relative Volume",
            category="volume",
            description="Compare recent average volume to a longer lookback window.",
            controls=[
                FilterControl(
                    control_type="number",
                    field="recent_days",
                    label="Recent Days",
                    default=2,
                    min_value=1,
                    max_value=10,
                    step=1,
                    required=True,
                ),
                FilterControl(
                    control_type="number",
                    field="lookback_days",
                    label="Lookback Days",
                    default=20,
                    min_value=5,
                    max_value=200,
                    step=1,
                    required=True,
                ),
                FilterControl(
                    control_type="number",
                    field="min_ratio",
                    label="Minimum Ratio",
                    default=1.5,
                    min_value=0.1,
                    max_value=10,
                    step=0.1,
                    required=True,
                ),
                FilterControl(
                    control_type="number",
                    field="max_ratio",
                    label="Maximum Ratio",
                    description="Optional upper bound for the recent/historical volume ratio",
                    min_value=0.1,
                    max_value=10,
                    step=0.1,
                ),
            ],
            tags=["volume"],
            sort_order=60,
        ),
    ]


filter_registry = FilterRegistry(_default_definitions())
