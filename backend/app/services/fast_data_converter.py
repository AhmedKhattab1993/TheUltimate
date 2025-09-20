"""Utilities for converting database rows into NumPy structured arrays."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Iterable, Mapping, Sequence, Any

import numpy as np

_NUMPY_DTYPE = np.dtype([
    ("date", "datetime64[ns]"),
    ("open", "float64"),
    ("high", "float64"),
    ("low", "float64"),
    ("close", "float64"),
    ("volume", "float64"),
])


def _as_mapping(row: Any) -> Mapping[str, Any]:
    """Return a mapping-like view for asyncpg.Record or dict rows."""
    if isinstance(row, Mapping):
        return row
    # asyncpg.Record implements __getitem__ but not Mapping, so wrap it
    return _RecordWrapper(row)


class _RecordWrapper(dict):
    """Lightweight adapter exposing key lookup for record-like objects."""

    def __init__(self, record: Any) -> None:
        self._record = record

    def __getitem__(self, key: str) -> Any:  # type: ignore[override]
        return self._record[key]

    def get(self, key: str, default: Any = None) -> Any:  # type: ignore[override]
        try:
            return self._record[key]
        except (KeyError, IndexError, TypeError):
            return default


def _coerce_float(value: Any) -> float:
    if value is None:
        return float("nan")
    if isinstance(value, Decimal):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return float("nan")


def _coerce_volume(value: Any) -> float:
    if value is None:
        return 0.0
    return _coerce_float(value)


def _coerce_datetime(value: Any) -> np.datetime64:
    if value is None:
        return np.datetime64("NaT")
    if isinstance(value, np.datetime64):
        return value.astype("datetime64[ns]")
    if isinstance(value, datetime):
        return np.datetime64(value)
    if isinstance(value, date):
        return np.datetime64(datetime.combine(value, datetime.min.time()))
    try:
        return np.datetime64(value)
    except (TypeError, ValueError):
        return np.datetime64("NaT")


def rows_to_numpy(rows: Sequence[Any] | Iterable[Any]) -> np.ndarray:
    """Convert an iterable of database rows into a NumPy structured array."""
    if not rows:
        return np.array([], dtype=_NUMPY_DTYPE)

    if isinstance(rows, Sequence):
        source = rows
    else:
        source = list(rows)

    result = np.empty(len(source), dtype=_NUMPY_DTYPE)

    for idx, raw_row in enumerate(source):
        row = _as_mapping(raw_row)
        date_value = row.get("date") or row.get("time")
        result["date"][idx] = _coerce_datetime(date_value)
        result["open"][idx] = _coerce_float(row.get("open"))
        result["high"][idx] = _coerce_float(row.get("high"))
        result["low"][idx] = _coerce_float(row.get("low"))
        result["close"][idx] = _coerce_float(row.get("close"))
        result["volume"][idx] = _coerce_volume(row.get("volume"))

    # Ensure chronological order in case upstream data is unsorted
    order = np.argsort(result["date"], kind="mergesort")
    return result[order]
