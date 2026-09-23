"""Output structures for the scoring engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .coverage import CoverageFraction


@dataclass
class MustHaveResult:
    """Result of evaluating a single must-have requirement for a provider."""

    control: str
    min_level: int
    actual_level: Optional[float]  # None = unassessed
    passed: bool


@dataclass
class CertificationMustHaveResult:
    """Result of evaluating a required certification for an offering."""

    certification_id: str
    held: bool
    current: bool
    passed: bool
    valid_until: Optional[str] = None
    scope_matches: bool = False
    reason: str = ""


@dataclass
class ScoredProvider:
    """Complete scoring output for a single provider."""

    provider: str
    assessment_id: str
    display_name: str
    overall_score: float  # 0–100 heuristic index
    domain_scores: dict[str, Optional[float]]  # domain slug → 0–100 or None
    must_have_results: list[MustHaveResult]
    must_have_passed: bool
    effective_scores: dict[str, Optional[float]]  # control_id → effective 0–3 or None
    rank: int = 0
    stale: bool = False
    eligible: bool = True
    eligibility_reasons: list[str] = field(default_factory=list)
    publishable: bool = False
    publication_reasons: list[str] = field(default_factory=list)
    certs_passed: bool = True
    cert_results: list[CertificationMustHaveResult] = field(default_factory=list)
    catalog_coverage: Optional[CoverageFraction] = None
    service_coverages: dict[str, dict[int, CoverageFraction]] = field(
        default_factory=dict
    )
    offering_id: Optional[str] = None
    cohort: Optional[str] = None
