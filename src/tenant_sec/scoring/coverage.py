"""Catalog and per-control coverage fractions (METHODOLOGY.md §5)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from ..core.models import (
    AssessmentStatus,
    LeafControlScore,
    MixedControlScore,
    ProviderProfile,
)
from ..core.registry import ControlRegistry
from .resolution import is_assessed_result, status_value

COVERAGE_BANDS: tuple[tuple[str, float, float], ...] = (
    ("none", 0.0, 0.0),
    ("low", 0.0, 0.40),
    ("medium", 0.40, 0.70),
    ("high", 0.70, 0.90),
    ("full", 0.90, 1.01),
)


def coverage_band(fraction: Optional[float]) -> Optional[str]:
    """Map a coverage fraction to a display band. None if the fraction is undefined."""
    if fraction is None:
        return None
    if fraction == 0.0:
        return "none"
    for name, lo, hi in COVERAGE_BANDS[1:]:
        if lo <= fraction < hi:
            return name
    return "full"


@dataclass
class CoverageFraction:
    """Capability coverage plus assessment completeness over one denominator."""

    # For threshold coverage this is the count meeting the threshold. For
    # catalogue completeness it is the count of fully assessed controls.
    assessed: int
    applicable: int
    threshold: Optional[int] = None
    assessed_total: Optional[int] = None
    state_counts: dict[str, int] = field(default_factory=dict)

    @property
    def fraction(self) -> Optional[float]:
        if self.applicable == 0:
            return None
        return self.assessed / self.applicable

    @property
    def band(self) -> Optional[str]:
        return coverage_band(self.fraction)

    @property
    def completeness(self) -> Optional[float]:
        if self.applicable == 0:
            return None
        total = self.assessed if self.assessed_total is None else self.assessed_total
        return total / self.applicable


def catalog_coverage(
    provider: ProviderProfile,
    registry: ControlRegistry,
) -> CoverageFraction:
    """Assessed tenant controls / applicable tenant controls in the catalogue.

    Missing YAML entries are not_assessed and stay in the denominator.
    Vignette-surface controls are excluded (they are not scored on the ladder).
    """
    tenant_controls = [c for c in registry.all_controls() if c.surface == "tenant"]
    assessed = 0
    applicable = 0
    state_counts: dict[str, int] = {}
    for control in tenant_controls:
        entry = provider.controls.get(control.id)
        if entry is None:
            applicable += 1
            _increment(state_counts, AssessmentStatus.NOT_ASSESSED)
            continue

        if (
            provider.is_v2
            and control.service_scoped
            and not isinstance(entry, MixedControlScore)
            and control.id not in provider.service_scope_exceptions
        ):
            state = AssessmentStatus.NOT_ASSESSED
        else:
            state = _control_state(provider, entry)
        _increment(state_counts, state)
        if state == AssessmentStatus.NOT_APPLICABLE:
            continue
        applicable += 1
        if state == AssessmentStatus.ASSESSED:
            assessed += 1
    return CoverageFraction(
        assessed=assessed,
        applicable=applicable,
        assessed_total=assessed,
        state_counts=state_counts,
    )


def service_coverage(
    provider: ProviderProfile,
    control_id: str,
    threshold: int = 2,
) -> Optional[CoverageFraction]:
    """coverage(threshold) for a mixed, service-scoped control.

    applicable = in-scope services minus not_applicable only.
    Services listed in the mixed composite with score=null are not applicable.
    In-scope services missing from the mixed map are unknown and stay applicable.
    """
    entry = provider.controls.get(control_id)
    if not isinstance(entry, MixedControlScore):
        return None

    in_scope = {svc.id for svc in provider.services_in_scope}
    if not in_scope:
        in_scope = set(entry.services.keys())

    excluded: set[str] = set()
    state_counts: dict[str, int] = {}
    for svc_id, svc in entry.services.items():
        if _service_state(provider, svc) == AssessmentStatus.NOT_APPLICABLE:
            excluded.add(svc_id)
            if svc_id in in_scope:
                _increment(state_counts, AssessmentStatus.NOT_APPLICABLE)

    applicable = in_scope - excluded
    meeting = 0
    assessed_total = 0
    for svc_id in applicable:
        svc = entry.services.get(svc_id)
        if svc is None:
            _increment(state_counts, AssessmentStatus.NOT_ASSESSED)
            continue
        state = _service_state(provider, svc)
        _increment(state_counts, state)
        if state != AssessmentStatus.ASSESSED or svc.score is None:
            continue
        assessed_total += 1
        if svc.score >= threshold:
            meeting += 1

    return CoverageFraction(
        assessed=meeting,
        applicable=len(applicable),
        threshold=threshold,
        assessed_total=assessed_total,
        state_counts=state_counts,
    )


def _control_state(
    provider: ProviderProfile,
    entry: LeafControlScore | MixedControlScore,
) -> AssessmentStatus:
    explicit = status_value(entry.status)
    if explicit:
        state = AssessmentStatus(explicit)
        if state != AssessmentStatus.ASSESSED:
            return state
    if isinstance(entry, LeafControlScore):
        return (
            AssessmentStatus.ASSESSED
            if is_assessed_result(entry)
            else AssessmentStatus.NOT_ASSESSED
        )

    in_scope = {service.id for service in provider.services_in_scope}
    states: list[AssessmentStatus] = []
    for service_id in in_scope:
        service = entry.services.get(service_id)
        if service is None:
            return AssessmentStatus.NOT_ASSESSED
        state = _service_state(provider, service)
        states.append(state)
        if state not in (
            AssessmentStatus.ASSESSED,
            AssessmentStatus.NOT_APPLICABLE,
        ):
            return state
    if states and all(state == AssessmentStatus.NOT_APPLICABLE for state in states):
        return AssessmentStatus.NOT_APPLICABLE
    return AssessmentStatus.ASSESSED


def _service_state(provider: ProviderProfile, service) -> AssessmentStatus:
    explicit = status_value(service.status)
    if explicit:
        return AssessmentStatus(explicit)
    if service.score is None:
        # Legacy null meant not applicable. V2 semantic validation requires an
        # explicit status, so this fallback cannot mask a v2 gap.
        return AssessmentStatus.NOT_APPLICABLE
    return AssessmentStatus.ASSESSED


def _increment(counts: dict[str, int], status: AssessmentStatus) -> None:
    counts[str(status)] = counts.get(str(status), 0) + 1
