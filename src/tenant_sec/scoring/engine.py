"""Main scoring pipeline: loads profiles, resolves scores, aggregates, ranks."""

from __future__ import annotations

import statistics
from datetime import date
from typing import Optional

from ..core.models import (
    LeafControlScore,
    MixedControlScore,
    ProviderProfile,
    ScoringProfile,
)
from ..core.registry import ControlRegistry
from ..core.staleness import is_stale
from .aggregation import get_aggregation_fn
from .ranking import MustHaveResult, ScoredProvider


class ScoringEngine:
    """Scores one or more provider profiles against a scoring profile."""

    def __init__(
        self,
        registry: ControlRegistry,
        reference_date: Optional[date] = None,
    ) -> None:
        self._registry = registry
        self._reference_date = reference_date or date.today()

    def score(
        self,
        providers: list[ProviderProfile],
        scoring_profile: ScoringProfile,
    ) -> list[ScoredProvider]:
        """Run the full pipeline and return a ranked list of ScoredProviders."""
        agg_fn = get_aggregation_fn(scoring_profile.mixed_aggregation)
        results: list[ScoredProvider] = []

        for provider in providers:
            scored = self._score_provider(provider, scoring_profile, agg_fn)
            results.append(scored)

        # Rank by overall_score descending; ties broken alphabetically
        results.sort(key=lambda s: (-s.overall_score, s.provider))
        for i, result in enumerate(results, start=1):
            result.rank = i

        return results

    def _score_provider(
        self,
        provider: ProviderProfile,
        profile: ScoringProfile,
        agg_fn,
    ) -> ScoredProvider:
        # Step 1: Resolve effective scores for all controls
        effective_scores: dict[str, Optional[float]] = {}

        for control in self._registry.all_controls():
            effective = self._resolve_effective_score(
                provider, control.id, control, agg_fn
            )
            effective_scores[control.id] = effective

        # Step 2: Evaluate must-haves
        must_have_results: list[MustHaveResult] = []
        for mh in profile.must_have:
            actual = effective_scores.get(mh.control)
            passed = actual is not None and actual >= mh.min_level
            must_have_results.append(
                MustHaveResult(
                    control=mh.control,
                    min_level=mh.min_level,
                    actual_level=actual,
                    passed=passed,
                )
            )
        must_have_passed = all(r.passed for r in must_have_results)

        # Step 3: Compute domain scores
        domain_scores: dict[str, Optional[float]] = {}
        for domain in self._registry.domains():
            controls_in_domain = self._registry.by_domain(domain)
            assessed = [
                effective_scores[c.id]
                for c in controls_in_domain
                if effective_scores.get(c.id) is not None
            ]
            if assessed:
                # Normalize 0-3 → 0-100
                domain_scores[domain] = (sum(assessed) / len(assessed)) * 100 / 3
            else:
                domain_scores[domain] = None

        # Step 4: Compute overall score
        weights = profile.weights
        weighted_sum = 0.0
        total_weight = 0.0
        for domain, weight in weights.items():
            dscore = domain_scores.get(domain)
            if dscore is not None:
                weighted_sum += dscore * weight
                total_weight += weight

        if total_weight > 0:
            overall_score = weighted_sum / total_weight
        else:
            overall_score = 0.0

        # Step 5: Staleness
        stale = is_stale(
            provider.assessed_at,
            provider.assessed_by,
            self._reference_date,
        )

        return ScoredProvider(
            provider=provider.provider,
            display_name=provider.display_name,
            overall_score=round(overall_score, 1),
            domain_scores={
                k: round(v, 1) if v is not None else None
                for k, v in domain_scores.items()
            },
            must_have_results=must_have_results,
            must_have_passed=must_have_passed,
            effective_scores=effective_scores,
            stale=stale,
        )

    def _resolve_effective_score(
        self,
        provider: ProviderProfile,
        control_id: str,
        control,
        agg_fn,
    ) -> Optional[float]:
        """Resolve effective score for a single control on a provider."""
        # Sub-controls: if this control has children, aggregate from children
        children = self._registry.children_of(control_id)
        if children:
            child_scores = [
                self._resolve_effective_score(provider, c.id, c, agg_fn)
                for c in children
            ]
            non_null = [s for s in child_scores if s is not None]
            if not non_null:
                return None
            agg_method = control.sub_control_aggregation or "mean"
            return _aggregate_sub_controls(non_null, agg_method)

        # Leaf: look up in provider profile
        score_entry = provider.controls.get(control_id)
        if score_entry is None:
            return None

        if isinstance(score_entry, LeafControlScore):
            return float(score_entry.score)

        if isinstance(score_entry, MixedControlScore):
            service_scores = [svc.score for svc in score_entry.services.values()]
            result = agg_fn(service_scores)
            return result

        return None


def _aggregate_sub_controls(scores: list[float], method: str) -> float:
    if method == "min" or method == "worst":
        return min(scores)
    if method == "max":
        return max(scores)
    return sum(scores) / len(scores)  # mean (default)
