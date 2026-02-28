"""Aggregation functions for mixed composite scores."""

from __future__ import annotations

import re
import statistics
from typing import Callable


def _non_null(scores: list[int | None]) -> list[int]:
    """Filter out None (not-applicable) values before aggregation."""
    return [s for s in scores if s is not None]


def _agg_min(scores: list[int | None]) -> float | None:
    values = _non_null(scores)
    return float(min(values)) if values else None


def _agg_mean(scores: list[int | None]) -> float | None:
    values = _non_null(scores)
    return statistics.mean(values) if values else None


def _agg_median(scores: list[int | None]) -> float | None:
    values = _non_null(scores)
    return float(statistics.median(values)) if values else None


def _agg_percentile(p: float) -> Callable[[list[int | None]], float | None]:
    """Return a percentile aggregation function for the given percentile (0-100)."""

    def _agg(scores: list[int | None]) -> float | None:
        values = sorted(_non_null(scores))
        if not values:
            return None
        # Linear interpolation
        n = len(values)
        pos = (p / 100) * (n - 1)
        lo = int(pos)
        hi = min(lo + 1, n - 1)
        frac = pos - lo
        return values[lo] * (1 - frac) + values[hi] * frac

    return _agg


def _agg_threshold(level: int, pct: float) -> Callable[[list[int | None]], float | None]:
    """Return L{level} if >= pct fraction of non-null scores are >= level, else L{level-1}."""

    def _agg(scores: list[int | None]) -> float | None:
        values = _non_null(scores)
        if not values:
            return None
        at_or_above = sum(1 for v in values if v >= level)
        fraction = at_or_above / len(values)
        return float(level) if fraction >= pct else float(max(level - 1, 0))

    return _agg


_THRESHOLD_RE = re.compile(r"^threshold:L([0-3]):([0-9]+(?:\.[0-9]+)?)$")

_BUILTIN: dict[str, Callable[[list[int | None]], float | None]] = {
    "min": _agg_min,
    "mean": _agg_mean,
    "median": _agg_median,
    "p10": _agg_percentile(10),
    "p20": _agg_percentile(20),
}


def get_aggregation_fn(
    spec: str,
) -> Callable[[list[int | None]], float | None]:
    """Parse an aggregation spec string and return the corresponding function.

    Supported formats:
      min, mean, median, p10, p20
      threshold:L{n}:{pct}   e.g. threshold:L2:0.8

    Raises ValueError for unknown specs.
    """
    if spec in _BUILTIN:
        return _BUILTIN[spec]

    m = _THRESHOLD_RE.match(spec)
    if m:
        level = int(m.group(1))
        pct = float(m.group(2))
        return _agg_threshold(level, pct)

    raise ValueError(
        f"Unknown aggregation spec '{spec}'. "
        "Valid options: min, mean, median, p10, p20, threshold:L{{n}}:{{pct}}"
    )
