"""Main scoring pipeline: loads profiles, resolves scores, aggregates, ranks."""

from __future__ import annotations

from datetime import date
from typing import Optional

from ..core.certifications import (
    CertificationCatalog,
    evaluate_certification,
)
from ..core.models import MixedControlScore, ProviderProfile, ScoringProfile
from ..core.registry import ControlRegistry
from ..core.staleness import is_stale
from .aggregation import get_aggregation_fn
from .coverage import CoverageFraction, catalog_coverage, service_coverage
from .ranking import CertificationMustHaveResult, MustHaveResult, ScoredProvider
from .resolution import effective_maturity


class ScoringEngine:
    """Scores one or more provider profiles against a scoring profile."""

    def __init__(
        self,
        registry: ControlRegistry,
        reference_date: Optional[date] = None,
        certification_catalog: Optional[CertificationCatalog] = None,
    ) -> None:
        self._registry = registry
        self._certification_catalog = certification_catalog
        self._reference_date = reference_date or date.today()

    def score(
        self,
        providers: list[ProviderProfile],
        scoring_profile: ScoringProfile,
    ) -> list[ScoredProvider]:
        """Run the full pipeline and return a ranked list of ScoredProviders.

        Eligible providers are ranked first (heuristic score, then name).
        Ineligible providers are listed below with rank 0.
        """
        tenant_domains = {
            control.domain
            for control in self._registry.all_controls()
            if control.surface == "tenant"
        }
        empty_weighted_domains = [
            domain
            for domain, weight in scoring_profile.weights.items()
            if weight > 0 and domain not in tenant_domains
        ]
        if empty_weighted_domains:
            raise ValueError(
                "Positive profile weights target domains without tenant "
                "controls: " + ", ".join(sorted(empty_weighted_domains))
            )
        agg_fn = get_aggregation_fn(scoring_profile.mixed_aggregation)
        results: list[ScoredProvider] = []

        for provider in providers:
            scored = self._score_provider(provider, scoring_profile, agg_fn)
            results.append(scored)

        eligible = [s for s in results if s.eligible]
        ineligible = [s for s in results if not s.eligible]
        eligible.sort(key=lambda s: (-s.overall_score, s.assessment_id))
        ineligible.sort(key=lambda s: (-s.overall_score, s.assessment_id))
        for i, result in enumerate(eligible, start=1):
            result.rank = i
        for result in ineligible:
            result.rank = 0

        return eligible + ineligible

    def _score_provider(
        self,
        provider: ProviderProfile,
        profile: ScoringProfile,
        agg_fn,
    ) -> ScoredProvider:
        # Step 1: Resolve effective scores for all controls
        effective_scores: dict[str, Optional[float]] = {}

        tenant_controls = [
            control
            for control in self._registry.all_controls()
            if control.surface == "tenant"
        ]
        for control in tenant_controls:
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

        cert_results: list[CertificationMustHaveResult] = []
        for cert_id in profile.must_have_certifications:
            evaluation = evaluate_certification(
                provider,
                cert_id,
                self._reference_date,
                self._certification_catalog,
            )
            cert_results.append(
                CertificationMustHaveResult(
                    certification_id=cert_id,
                    held=evaluation.held,
                    current=evaluation.current,
                    passed=evaluation.passed,
                    valid_until=(
                        evaluation.valid_until.isoformat()
                        if evaluation.valid_until
                        else None
                    ),
                    scope_matches=evaluation.scope_matches,
                    reason=evaluation.reason,
                )
            )
        certs_passed = all(r.passed for r in cert_results)

        coverage = catalog_coverage(provider, self._registry)
        coverage_ok = True
        required_completeness = profile.required_catalog_completeness
        if required_completeness is not None:
            fraction = coverage.completeness
            coverage_ok = (
                fraction is not None and fraction >= required_completeness
            )

        cohort_required = provider.is_v2 and profile.cohort is None
        cohort_ok = (
            not cohort_required
            and (
                profile.cohort is None
                or (
                    provider.offering is not None
                    and provider.offering.cohort == profile.cohort
                )
            )
        )
        eligibility_reasons: list[str] = []
        if not must_have_passed:
            eligibility_reasons.append("one or more control must-haves failed")
        if not certs_passed:
            eligibility_reasons.extend(
                f"{result.certification_id}: {result.reason}"
                for result in cert_results
                if not result.passed
            )
        if not coverage_ok:
            eligibility_reasons.append(
                "catalog completeness is below the profile minimum"
            )
        if cohort_required:
            eligibility_reasons.append(
                "methodology-2 ranking requires an explicit profile cohort"
            )
        elif not cohort_ok:
            eligibility_reasons.append("assessment is outside the profile cohort")

        eligible = not eligibility_reasons

        service_coverages: dict[str, dict[int, CoverageFraction]] = {}
        for control in tenant_controls:
            if not control.service_scoped:
                continue
            for threshold in profile.service_coverage_thresholds:
                result = service_coverage(provider, control.id, threshold)
                if result is not None:
                    service_coverages.setdefault(control.id, {})[threshold] = result

        # Step 3: Compute domain scores
        domain_scores: dict[str, Optional[float]] = {}
        for domain in self._registry.domains():
            controls_in_domain = [
                control
                for control in self._registry.by_domain(domain)
                if control.surface == "tenant"
            ]
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

        # Step 4: Compute overall heuristic index
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
        publication_reasons: list[str] = []
        if not provider.is_v2:
            publication_reasons.append("assessment does not use methodology 2.x")
        if stale:
            publication_reasons.append("assessment is stale")
        if coverage.completeness != 1.0:
            publication_reasons.append("catalog assessment is incomplete")
        non_mixed_service_controls = [
            control.id
            for control in tenant_controls
            if control.service_scoped
            and provider.controls.get(control.id) is not None
            and not isinstance(
                provider.controls.get(control.id), MixedControlScore
            )
            and control.id not in provider.service_scope_exceptions
        ]
        if non_mixed_service_controls:
            publication_reasons.append(
                "service-scoped controls require mixed results or explicit "
                "exceptions: " + ", ".join(non_mixed_service_controls)
            )
        if not eligible:
            publication_reasons.append("assessment is not eligible for this profile")
        publishable = not publication_reasons

        return ScoredProvider(
            provider=provider.provider,
            assessment_id=provider.identity,
            display_name=provider.display_name,
            overall_score=overall_score,
            domain_scores=domain_scores,
            must_have_results=must_have_results,
            must_have_passed=must_have_passed,
            effective_scores=effective_scores,
            stale=stale,
            eligible=eligible,
            eligibility_reasons=eligibility_reasons,
            publishable=publishable,
            publication_reasons=publication_reasons,
            certs_passed=certs_passed,
            cert_results=cert_results,
            catalog_coverage=coverage,
            service_coverages=service_coverages,
            offering_id=provider.offering.id if provider.offering else None,
            cohort=provider.offering.cohort if provider.offering else None,
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
        children = [
            child
            for child in self._registry.children_of(control_id)
            if child.surface == "tenant"
        ]
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
        return effective_maturity(
            provider.controls.get(control_id),
            agg_fn,
            {service.id for service in provider.services_in_scope},
        )


def _aggregate_sub_controls(scores: list[float], method: str) -> float:
    if method == "min" or method == "worst":
        return min(scores)
    if method == "max":
        return max(scores)
    return sum(scores) / len(scores)  # mean (default)
