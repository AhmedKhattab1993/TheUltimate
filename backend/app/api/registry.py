"""Expose shared registries for the frontend."""

from fastapi import APIRouter

from ..registry import filter_registry, strategy_registry

router = APIRouter(prefix="/api/v2/registry", tags=["registry"])


@router.get("/filters")
def list_filters() -> dict:
    return {"filters": filter_registry.to_serialisable()}


@router.get("/strategies")
def list_strategies() -> dict:
    return {"strategies": strategy_registry.to_serialisable()}


@router.get("/all")
def list_all() -> dict:
    return {
        "filters": filter_registry.to_serialisable(),
        "strategies": strategy_registry.to_serialisable(),
    }
