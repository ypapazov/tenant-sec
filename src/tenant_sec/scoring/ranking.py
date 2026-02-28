"""Output structures for the scoring engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class MustHaveResult:
    """Result of evaluating a single must-have requirement for a provider."""

    control: str
    min_level: int
    actual_level: Optional[float]  # None = unassessed
    passed: bool


@dataclass
class ScoredProvider:
    """Complete scoring output for a single provider."""

    provider: str
    display_name: str
    overall_score: float  # 0–100
    domain_scores: dict[str, Optional[float]]  # domain slug → 0–100 or None
    must_have_results: list[MustHaveResult]
    must_have_passed: bool
    effective_scores: dict[str, Optional[float]]  # control_id → effective 0–3 or None
    rank: int = 0
    stale: bool = False
