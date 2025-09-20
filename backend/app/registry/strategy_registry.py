"""Strategy registry provides metadata for Lean algorithms."""

from __future__ import annotations

from functools import lru_cache
from typing import Dict, Iterable, List, Optional

from ..models.backtest import BacktestRequest
from .schemas import (
    FilterOption,
    StrategyCapabilities,
    StrategyDefinition,
    StrategyParameter,
)


class StrategyRegistry:
    """Central catalogue of Lean strategies."""

    def __init__(self, definitions: Iterable[StrategyDefinition]):
        self._definitions: Dict[str, StrategyDefinition] = {
            definition.id: definition for definition in definitions
        }

    def list(self) -> List[StrategyDefinition]:
        return sorted(self._definitions.values(), key=lambda item: item.label)

    def get(self, strategy_id: str) -> Optional[StrategyDefinition]:
        return self._definitions.get(strategy_id)

    def require(self, strategy_id: str) -> StrategyDefinition:
        definition = self.get(strategy_id)
        if not definition:
            raise ValueError(f"Unknown strategy '{strategy_id}'")
        return definition

    def to_serialisable(self) -> List[dict]:
        return [definition.model_dump() for definition in self.list()]

    def merge_request_with_defaults(
        self, request: BacktestRequest
    ) -> BacktestRequest:
        """Populate missing parameters using registry defaults."""

        definition = self.require(request.strategy_name)
        merged_params = {**definition.defaults, **(request.parameters or {})}
        request.parameters = merged_params
        return request


@lru_cache(maxsize=1)
def _default_definitions() -> List[StrategyDefinition]:
    return [
        StrategyDefinition(
            id="MarketStructure",
            label="Market Structure",
            description="Breakout strategy that scans for structural shifts along multiple timeframes.",
            project_path="MarketStructure",
            parameters=[
                StrategyParameter(
                    name="pivot_bars",
                    label="Pivot Bars",
                    description="Number of bars to use for pivot detection",
                    control_type="number",
                    default=5,
                    min_value=1,
                    max_value=20,
                    step=1,
                    required=True,
                ),
                StrategyParameter(
                    name="lower_timeframe",
                    label="Lower Timeframe",
                    description="Secondary timeframe used by the algorithm",
                    control_type="select",
                    default="5min",
                    options=[
                        FilterOption(label="1 minute", value="1min"),
                        FilterOption(label="5 minute", value="5min"),
                        FilterOption(label="15 minute", value="15min"),
                        FilterOption(label="30 minute", value="30min"),
                        FilterOption(label="1 hour", value="1hour"),
                    ],
                    required=True,
                ),
                StrategyParameter(
                    name="resolution",
                    label="Resolution",
                    description="Lean data resolution",
                    control_type="select",
                    default="Minute",
                    options=[
                        FilterOption(label="Minute", value="Minute"),
                        FilterOption(label="Hour", value="Hour"),
                        FilterOption(label="Daily", value="Daily"),
                    ],
                    required=True,
                ),
                StrategyParameter(
                    name="screener_session_id",
                    label="Screener Session",
                    description="Optional screener session to hydrate symbols from.",
                    control_type="text",
                    default="",
                    required=False,
                ),
            ],
            defaults={
                "pivot_bars": 5,
                "lower_timeframe": "5min",
                "resolution": "Minute",
            },
            capabilities=StrategyCapabilities(
                supports=["backtest", "grid", "optimize"],
                default_job_type="backtest",
                parallelism=4,
            ),
            notes="Uses Lean CLI backtest/optimize entrypoints through the shared job service.",
        ),
    ]


strategy_registry = StrategyRegistry(_default_definitions())
