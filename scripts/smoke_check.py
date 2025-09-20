"""Minimal smoke checks for v2 API endpoints.

Run with:
    python3 scripts/smoke_check.py --base-url http://localhost:8000

Requires the API server to be running. Emits a non-zero exit code on failure.
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

import requests


def _get_json(base_url: str, path: str) -> Any:
    response = requests.get(f"{base_url}{path}", timeout=15)
    response.raise_for_status()
    return response.json()


def run_smoke(base_url: str) -> int:
    print(f"Running smoke checks against {base_url}")

    # Screener registry / filters should load
    registry = _get_json(base_url, "/api/v2/registry/all")
    if not registry.get("filters"):
        print("✗ registry filters missing", file=sys.stderr)
        return 1
    print("✓ registry")

    # Backtest strategies should be available
    strategies = _get_json(base_url, "/api/v2/backtest/strategies")
    if not isinstance(strategies, list) or not strategies:
        print("✗ backtest strategies missing", file=sys.stderr)
        return 1
    print("✓ strategies")

    # Grid results endpoint should respond even if empty
    grid = _get_json(base_url, "/api/v2/grid/results")
    if "results" not in grid:
        print("✗ grid results missing", file=sys.stderr)
        return 1
    print(f"✓ grid results ({len(grid['results'])} rows)")

    # Combined results should respond
    combined = _get_json(base_url, "/api/v2/combined-results/")
    if "results" not in combined:
        print("✗ combined results missing", file=sys.stderr)
        return 1
    print(f"✓ combined results ({len(combined['results'])} rows)")

    print("Smoke checks passed")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="API smoke tests")
    parser.add_argument("--base-url", default="http://localhost:8000", help="API base URL")
    args = parser.parse_args()
    try:
        return run_smoke(args.base_url.rstrip('/'))
    except requests.HTTPError as exc:  # noqa: PERF203 - exit path
        print(f"HTTP error: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # noqa: BLE001
        print(f"Unexpected error: {exc}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
