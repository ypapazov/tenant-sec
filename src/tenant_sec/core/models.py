"""Typed dataclasses for all tenant-sec entities."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import IntEnum, StrEnum
from typing import Optional


class MaturityLevel(IntEnum):
    IMPOSSIBLE = 0
    REQUIRES_OWN_LOOP = 1
    MANAGED_LIMITED = 2
    MANAGED_CUSTOMIZABLE = 3

    @classmethod
    def label(cls, value: int) -> str:
        labels = {
            0: "L0: Impossible from tenant space",
            1: "L1: Requires own processing loop",
            2: "L2: Available managed, limited",
            3: "L3: Available managed, customizable",
        }
        return labels.get(value, f"L{value}")


class AssessmentStatus(StrEnum):
    ASSESSED = "assessed"
    UNKNOWN = "unknown"
    CONFLICTING = "conflicting"
    NOT_ASSESSED = "not_assessed"
    NOT_APPLICABLE = "not_applicable"
    OUT_OF_SCOPE = "out_of_scope"


@dataclass(frozen=True)
class Reference:
    """A source cited by an assessment or assurance record."""

    url: str
    title: str


@dataclass(frozen=True)
class EvidenceApplicability:
    """Assessment scope to which an evidence item applies."""

    offering: str
    regions: list[str]
    services: list[str]
    edition: str


@dataclass(frozen=True)
class EvidenceItem:
    """Immutable source excerpt used by one or more atomic claims."""

    id: str
    url: str
    title: str
    source_class: str
    retrieved_at: datetime
    content_hash: str
    quote: str
    applicability: EvidenceApplicability
    updated_at: Optional[date] = None


@dataclass(frozen=True)
class AssessmentClaim:
    """Atomic supported, unsupported, or contradicted assertion."""

    id: str
    assertion: str
    result: str
    evidence_item_ids: list[str]
    services: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class CriteriaResult:
    """Evaluation of one L0-L3 criterion against atomic claims."""

    level: int
    met: bool
    reasoning: str
    claim_ids: list[str] = field(default_factory=list)


@dataclass
class Control:
    """A single control definition from controls/{domain}/*.yaml."""

    id: str
    domain: str
    name: str
    description: str
    criteria: dict[str, str]  # keys: L0, L1, L2, L3
    framework_mappings: dict[str, list[str]]
    service_scoped: bool = False
    parent: Optional[str] = None
    sub_control_aggregation: Optional[str] = None  # min, max, mean, worst
    surface: str = "tenant"  # tenant | vignette


@dataclass
class ServiceScore:
    """An individual service score within a mixed composite."""

    score: Optional[int]
    evidence: str
    status: Optional[AssessmentStatus] = None
    confidence: Optional[str] = None
    references: list[Reference] = field(default_factory=list)


@dataclass
class LeafControlScore:
    """A direct maturity result or explicit non-score state for a control."""

    score: Optional[int]
    evidence: str
    compensating_controls: Optional[str] = None
    verified_at: Optional[date] = None
    status: Optional[AssessmentStatus] = None
    confidence: Optional[str] = None
    references: list[Reference] = field(default_factory=list)
    evidence_items: list[EvidenceItem] = field(default_factory=list)
    claims: list[AssessmentClaim] = field(default_factory=list)
    criteria_results: list[CriteriaResult] = field(default_factory=list)


@dataclass
class MixedControlScore:
    """A per-service breakdown score for a control."""

    services: dict[str, ServiceScore]  # service_id → ServiceScore
    summary: Optional[str] = None
    verified_at: Optional[date] = None
    status: Optional[AssessmentStatus] = None
    confidence: Optional[str] = None
    references: list[Reference] = field(default_factory=list)
    evidence_items: list[EvidenceItem] = field(default_factory=list)
    claims: list[AssessmentClaim] = field(default_factory=list)
    criteria_results: list[CriteriaResult] = field(default_factory=list)


# Union type for a control score entry in a provider profile
ControlScore = LeafControlScore | MixedControlScore


@dataclass
class ServiceInScope:
    """A service instance listed in a provider's assessment scope."""

    id: str  # Provider-local alias
    name: str
    category: str  # Canonical category from service catalog
    aliases: list[str] = field(default_factory=list)
    regions: list[str] = field(default_factory=list)
    edition: Optional[str] = None


@dataclass
class CertificationRecord:
    """A held (or expired) programme on an offering. Inventory, not a score."""

    id: str
    kind: Optional[str] = None
    status: Optional[str] = None
    valid_from: Optional[date] = None
    valid_until: Optional[date] = None
    validity: Optional[str] = None
    scope: Optional[str] = None
    offering: Optional[str] = None
    regions: list[str] = field(default_factory=list)
    services: list[str] = field(default_factory=list)
    all_services: bool = False
    report_access: Optional[str] = None
    evidence: list[Reference] = field(default_factory=list)


@dataclass
class ProviderOffering:
    """Named commercial offering this file assesses."""

    id: Optional[str] = None
    name: Optional[str] = None
    partition: Optional[str] = None
    regions: list[str] = field(default_factory=list)
    region_equivalence: Optional[str] = None
    edition: Optional[str] = None
    cohort: Optional[str] = None


@dataclass
class ProviderProfile:
    """A provider assessment profile from providers/*.yaml."""

    provider: str
    display_name: str
    assessed_by: str
    assessed_at: date
    methodology_version: str
    revision: int
    services_in_scope: list[ServiceInScope]
    controls: dict[str, ControlScore]  # control_id → score
    assessment_id: Optional[str] = None
    offering: Optional[ProviderOffering] = None
    review_status: Optional[str] = None
    review_note: Optional[str] = None
    vignette: dict[str, dict] = field(default_factory=dict)
    certifications: list[CertificationRecord] = field(default_factory=list)
    service_scope_exceptions: dict[str, str] = field(default_factory=dict)

    @property
    def identity(self) -> str:
        """Stable row identity; v1 falls back to the provider slug."""
        return self.assessment_id or self.provider

    @property
    def is_v2(self) -> bool:
        return self.methodology_version.startswith("2.")


@dataclass
class MustHaveEntry:
    """A must-have requirement in a scoring profile."""

    control: str
    min_level: int


@dataclass
class ScoringProfile:
    """A scoring profile from profiles/*.yaml."""

    name: str
    weights: dict[str, float]  # domain → weight (must sum to 1.0)
    mixed_aggregation: str
    description: Optional[str] = None
    methodology_version: Optional[str] = None
    must_have: list[MustHaveEntry] = field(default_factory=list)
    must_have_certifications: list[str] = field(default_factory=list)
    min_catalog_coverage: Optional[float] = None
    min_catalog_completeness: Optional[float] = None
    cohort: Optional[str] = None
    service_coverage_thresholds: tuple[int, ...] = (2, 3)

    @property
    def required_catalog_completeness(self) -> Optional[float]:
        if self.min_catalog_completeness is not None:
            return self.min_catalog_completeness
        return self.min_catalog_coverage
