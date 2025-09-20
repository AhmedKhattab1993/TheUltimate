"""Pydantic schemas that describe registry metadata shared across services."""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field, ConfigDict


class FilterOption(BaseModel):
    """Selectable option for a filter control."""

    label: str
    value: Any
    description: Optional[str] = None


class FilterControl(BaseModel):
    """Representation of a UI control that captures filter input."""

    control_type: Literal["range", "number", "select", "toggle"]
    field: str = Field(..., description="Control key within the filter state")
    label: str
    description: Optional[str] = None
    default: Any = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    step: Optional[float] = None
    options: Optional[List[FilterOption]] = None
    unit: Optional[str] = None
    placeholder: Optional[str] = None
    required: bool = False


class FilterDefinition(BaseModel):
    """Metadata for a screener filter used by both frontend and backend."""

    id: str = Field(..., description="Unique identifier used in the frontend state")
    backend_key: str = Field(..., description="Key that maps to backend filter builder")
    label: str
    category: Literal["price", "momentum", "volume", "volatility", "liquidity", "misc"]
    description: str
    default_enabled: bool = False
    controls: List[FilterControl]
    tags: List[str] = Field(default_factory=list)
    sort_order: int = 0
    doc_url: Optional[str] = None
    analytics_key: Optional[str] = Field(
        None,
        description="Metric namespace for downstream analytics",
    )

    model_config = ConfigDict(use_attribute_docstrings=True)


class StrategyParameter(BaseModel):
    """Definition of strategy parameter that can be tuned in the UI."""

    name: str
    label: str
    description: Optional[str] = None
    control_type: Literal["number", "select", "text", "range"] = "number"
    default: Any = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    step: Optional[float] = None
    options: Optional[List[FilterOption]] = None
    required: bool = False


class StrategyCapabilities(BaseModel):
    """Supported job types and integrations for a strategy."""

    supports: List[Literal["backtest", "grid", "optimize"]] = Field(
        default_factory=lambda: ["backtest"]
    )
    default_job_type: Literal["backtest", "grid", "optimize"] = "backtest"
    parallelism: Optional[int] = Field(
        None,
        description="Maximum recommended parallel jobs for this strategy",
    )


class StrategyDefinition(BaseModel):
    """Metadata describing a Lean strategy (algorithm)."""

    id: str = Field(..., description="Unique identifier for registry lookups")
    label: str
    project_path: str = Field(
        ..., description="Path to the Lean project relative to backend/lean"
    )
    description: str
    parameters: List[StrategyParameter] = Field(default_factory=list)
    defaults: Dict[str, Any] = Field(default_factory=dict)
    capabilities: StrategyCapabilities = Field(default_factory=StrategyCapabilities)
    notes: Optional[str] = None
    documentation_url: Optional[str] = None


class RegistryExport(BaseModel):
    """Bundle returned over the API."""

    filters: List[FilterDefinition]
    strategies: List[StrategyDefinition]

