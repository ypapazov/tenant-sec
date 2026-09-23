"""Single source of truth for status-aware maturity resolution."""

from __future__ import annotations

from collections.abc import Callable
from typing import Optional

from ..core.models import (
    AssessmentStatus,
    ControlScore,
    LeafControlScore,
    MixedControlScore,
    ServiceScore,
)

AggregationFn = Callable[[list[int | None]], Optional[float]]


def status_value(status: AssessmentStatus | str | None) -> str | None:
    """Return a plain status value for enum and backwards-compatible inputs."""
    if status is None:
        return None
    return str(status)


def is_assessed_result(
    entry: LeafControlScore | MixedControlScore | ServiceScore,
) -> bool:
    """Whether an entry may contribute a maturity value.

    Methodology-1 records omit status; a present numeric score is treated as
    assessed. Methodology-2 non-score states never contribute.
    """
    status = status_value(entry.status)
    if status == AssessmentStatus.ASSESSED:
        return entry.score is not None if hasattr(entry, "score") else True
    if status is not None:
        return False
    if isinstance(entry, MixedControlScore):
        return True
    return entry.score is not None


def effective_maturity(
    entry: ControlScore | None,
    aggregate: AggregationFn,
    service_ids: set[str] | None = None,
) -> Optional[float]:
    """Resolve one direct or mixed result to an effective maturity value."""
    if entry is None or not is_assessed_result(entry):
        return None
    if isinstance(entry, LeafControlScore):
        return float(entry.score) if entry.score is not None else None

    scores = [
        service.score
        for service_id, service in entry.services.items()
        if (service_ids is None or service_id in service_ids)
        if is_assessed_result(service)
    ]
    return aggregate(scores)
