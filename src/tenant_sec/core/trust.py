"""Auditable trust checks for methodology-2 provider assessments.

The normal schema validator remains backwards compatible.  These checks are
opt-in and intentionally stricter: they verify that a published score follows
from supported claims and that those claims have publication-quality evidence.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
from urllib.parse import urlsplit, urlunsplit

from .models import (
    AssessmentClaim,
    AssessmentStatus,
    ControlScore,
    CriteriaResult,
    LeafControlScore,
    MixedControlScore,
    ProviderProfile,
)
from .registry import ControlRegistry


TrustMode = Literal["strict", "publication"]

STRONG_SOURCE_CLASSES = frozenset(
    {"regulator", "binding", "api", "technical"}
)
PROVISIONAL_EXCEPTION_MARKERS = (
    "provisional",
    "unreviewed",
    "ai-assisted",
    "portfolio-level recommendation",
)


@dataclass(frozen=True)
class TrustFinding:
    """One stable, machine-addressable trust verification failure."""

    code: str
    path: str
    message: str

    def format(self) -> str:
        return f"{self.code} at {self.path}: {self.message}"


def _claim_applies_to_service(
    claim: AssessmentClaim, service_id: str | None
) -> bool:
    if service_id is None or not claim.services:
        return True
    return service_id in claim.services


def _claims_for_criterion(
    criterion: CriteriaResult,
    claims_by_id: dict[str, AssessmentClaim],
    *,
    service_id: str | None = None,
) -> list[AssessmentClaim]:
    claims = [
        claims_by_id[claim_id]
        for claim_id in criterion.claim_ids
        if claim_id in claims_by_id
    ]
    return [
        claim
        for claim in claims
        if _claim_applies_to_service(claim, service_id)
    ]


def derive_supported_level(
    criteria_results: list[CriteriaResult],
    claims: list[AssessmentClaim],
    *,
    service_id: str | None = None,
) -> int | None:
    """Return the highest met level backed only by supported applicable claims."""

    claims_by_id = {claim.id: claim for claim in claims}
    supported_levels: list[int] = []
    for criterion in criteria_results:
        if not criterion.met:
            continue
        criterion_claims = _claims_for_criterion(
            criterion, claims_by_id, service_id=service_id
        )
        if criterion_claims and all(
            claim.result == "supported" for claim in criterion_claims
        ):
            supported_levels.append(criterion.level)
    return max(supported_levels) if supported_levels else None


def _normalized_urlish(value: str) -> str:
    raw = value.strip()
    try:
        parts = urlsplit(raw)
    except ValueError:
        return raw.rstrip("/").casefold()
    if not parts.scheme or not parts.netloc:
        return raw.rstrip("/").casefold()
    return urlunsplit(
        (
            parts.scheme.casefold(),
            parts.netloc.casefold(),
            parts.path.rstrip("/"),
            parts.query,
            "",
        )
    )


def _title_is_url(url: str, title: str) -> bool:
    return _normalized_urlish(url) == _normalized_urlish(title)


def _verify_claim_graph(
    control_id: str,
    result: ControlScore,
) -> list[TrustFinding]:
    path = f"controls.{control_id}"
    findings: list[TrustFinding] = []
    claims_by_id = {claim.id: claim for claim in result.claims}
    evidence_by_id = {item.id: item for item in result.evidence_items}

    for criterion in result.criteria_results:
        if not criterion.met:
            continue
        criterion_path = f"{path}.criteria_results.L{criterion.level}"
        if not criterion.claim_ids:
            findings.append(
                TrustFinding(
                    "TRUST_MET_CRITERIA_NO_CLAIMS",
                    criterion_path,
                    "a met criterion must cite at least one claim",
                )
            )
            continue
        for claim_id in criterion.claim_ids:
            claim = claims_by_id.get(claim_id)
            if claim is None:
                # The normal semantic validator reports this more directly.
                continue
            if claim.result != "supported":
                findings.append(
                    TrustFinding(
                        "TRUST_MET_CRITERIA_BAD_CLAIM",
                        criterion_path,
                        f"met criterion cites {claim.result} claim '{claim_id}'",
                    )
                )
                continue
            claim_evidence = [
                evidence_by_id[evidence_id]
                for evidence_id in claim.evidence_item_ids
                if evidence_id in evidence_by_id
            ]
            if not claim_evidence:
                findings.append(
                    TrustFinding(
                        "TRUST_SUPPORTED_CLAIM_NO_EVIDENCE",
                        f"{path}.claims.{claim_id}",
                        "supported claim has no resolvable evidence item",
                    )
                )
            elif not any(
                item.source_class in STRONG_SOURCE_CLASSES
                for item in claim_evidence
            ):
                findings.append(
                    TrustFinding(
                        "TRUST_WEAK_CLAIM_EVIDENCE",
                        f"{path}.claims.{claim_id}",
                        "claim used for a met criterion is supported only by "
                        "support or secondary sources",
                    )
                )

    if isinstance(result, LeafControlScore):
        if result.status == AssessmentStatus.ASSESSED and result.score is not None:
            derived = derive_supported_level(
                result.criteria_results, result.claims
            )
            if derived != result.score:
                findings.append(
                    TrustFinding(
                        "TRUST_SCORE_CRITERIA_MISMATCH",
                        f"{path}.score",
                        f"stored L{result.score} does not match highest "
                        f"supported met level {f'L{derived}' if derived is not None else 'none'}",
                    )
                )
    else:
        for service_id, service in result.services.items():
            if (
                service.status != AssessmentStatus.ASSESSED
                or service.score is None
            ):
                continue
            applicable_supported_claims = [
                claim
                for claim in result.claims
                if claim.result == "supported"
                and _claim_applies_to_service(claim, service_id)
            ]
            if not applicable_supported_claims:
                findings.append(
                    TrustFinding(
                        "TRUST_SERVICE_SCORE_NO_SUPPORTED_CLAIM",
                        f"{path}.services.{service_id}",
                        "assessed service score has no applicable supported "
                        "claim; per-service criterion verdicts are not yet "
                        "represented by the canonical schema",
                    )
                )
    return findings


def _verify_titles(
    control_id: str, result: ControlScore
) -> list[TrustFinding]:
    path = f"controls.{control_id}"
    findings: list[TrustFinding] = []
    for index, reference in enumerate(result.references):
        if _title_is_url(reference.url, reference.title):
            findings.append(
                TrustFinding(
                    "TRUST_URL_AS_TITLE",
                    f"{path}.references.{index}.title",
                    "reference title duplicates its URL",
                )
            )
    for index, item in enumerate(result.evidence_items):
        if _title_is_url(item.url, item.title):
            findings.append(
                TrustFinding(
                    "TRUST_URL_AS_TITLE",
                    f"{path}.evidence_items.{index}.title",
                    "evidence title duplicates its URL",
                )
            )
    if isinstance(result, MixedControlScore):
        for service_id, service in result.services.items():
            for index, reference in enumerate(service.references):
                if _title_is_url(reference.url, reference.title):
                    findings.append(
                        TrustFinding(
                            "TRUST_URL_AS_TITLE",
                            f"{path}.services.{service_id}.references.{index}.title",
                            "service reference title duplicates its URL",
                        )
                    )
    return findings


def verify_provider_trust(
    provider: ProviderProfile,
    registry: ControlRegistry,
    *,
    mode: TrustMode = "strict",
) -> list[TrustFinding]:
    """Verify the evidence-to-score chain for one provider profile."""

    findings: list[TrustFinding] = []
    if not provider.is_v2:
        findings.append(
            TrustFinding(
                "TRUST_METHOD_VERSION",
                "methodology_version",
                "trust verification requires methodology version 2.x",
            )
        )
        return findings

    if mode == "publication" and provider.review_status != "human-reviewed":
        findings.append(
            TrustFinding(
                "TRUST_REVIEW_STATUS",
                "review_status",
                "a current publication row must be human-reviewed",
            )
        )

    for control_id, result in provider.controls.items():
        control = registry.get(control_id)
        if control is None or control.surface != "tenant":
            continue

        if result.status == AssessmentStatus.ASSESSED:
            findings.extend(_verify_claim_graph(control_id, result))
            if mode == "publication":
                findings.extend(_verify_titles(control_id, result))

        if (
            mode == "publication"
            and control.service_scoped
            and isinstance(result, LeafControlScore)
            and result.status == AssessmentStatus.ASSESSED
        ):
            exception = provider.service_scope_exceptions.get(control_id)
            if not exception:
                findings.append(
                    TrustFinding(
                        "TRUST_SERVICE_SCOPE_LEAF",
                        f"controls.{control_id}",
                        "service-scoped assessed control requires a mixed result "
                        "or a reviewed written exception",
                    )
                )
            elif (
                provider.review_status != "human-reviewed"
                or any(
                    marker in exception.casefold()
                    for marker in PROVISIONAL_EXCEPTION_MARKERS
                )
            ):
                findings.append(
                    TrustFinding(
                        "TRUST_PROVISIONAL_SCOPE_EXCEPTION",
                        f"service_scope_exceptions.{control_id}",
                        "provisional or unreviewed exception cannot support a "
                        "current publication row",
                    )
                )

    if mode == "publication":
        for cert_index, certification in enumerate(provider.certifications):
            for ref_index, reference in enumerate(certification.evidence):
                if _title_is_url(reference.url, reference.title):
                    findings.append(
                        TrustFinding(
                            "TRUST_URL_AS_TITLE",
                            f"certifications.{cert_index}.evidence.{ref_index}.title",
                            "certification evidence title duplicates its URL",
                        )
                    )

    return findings
