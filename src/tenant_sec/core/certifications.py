"""Certification catalogue loader (inventory, not maturity)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Optional

import yaml

from .models import CertificationRecord, ProviderProfile


@dataclass
class CertificationProgramme:
    id: str
    name: str
    kind: str
    geography: Optional[str] = None
    notes: Optional[str] = None
    holdable: bool = True


@dataclass
class CertificationCatalog:
    version: str
    programmes: dict[str, CertificationProgramme] = field(default_factory=dict)

    def get(self, programme_id: str) -> Optional[CertificationProgramme]:
        return self.programmes.get(programme_id)

    def ids(self) -> set[str]:
        return set(self.programmes.keys())

    def is_holdable(self, programme_id: str) -> bool:
        programme = self.get(programme_id)
        return bool(
            programme
            and programme.holdable
            and programme.kind != "scheme-draft"
        )

    @classmethod
    def from_file(cls, path: Path) -> "CertificationCatalog":
        with open(path) as f:
            data = yaml.safe_load(f) or {}
        programmes = {
            pid: CertificationProgramme(
                id=pid,
                name=entry["name"],
                kind=entry["kind"],
                geography=entry.get("geography"),
                notes=entry.get("notes"),
                holdable=bool(entry.get("holdable", True)),
            )
            for pid, entry in (data.get("programmes") or {}).items()
        }
        return cls(version=str(data.get("version", "")), programmes=programmes)


@dataclass(frozen=True)
class CertificationEvaluation:
    certification_id: str
    passed: bool
    reason: str
    held: bool = False
    current: bool = False
    scope_matches: bool = False
    valid_until: Optional[date] = None


def evaluate_certification(
    provider: ProviderProfile,
    certification_id: str,
    reference_date: date,
    catalog: Optional[CertificationCatalog],
) -> CertificationEvaluation:
    """Evaluate a required programme against this exact assessment scope."""
    if catalog is None:
        return CertificationEvaluation(
            certification_id, False, "certification catalogue unavailable"
        )
    programme = catalog.get(certification_id)
    if programme is None:
        return CertificationEvaluation(
            certification_id, False, "unknown certification catalogue id"
        )
    if not catalog.is_holdable(certification_id):
        return CertificationEvaluation(
            certification_id, False, "programme cannot be held"
        )

    candidates = [r for r in provider.certifications if r.id == certification_id]
    if not candidates:
        return CertificationEvaluation(
            certification_id, False, "required programme is missing"
        )

    failures: list[CertificationEvaluation] = []
    for record in candidates:
        evaluation = _evaluate_record(provider, programme, record, reference_date)
        if evaluation.passed:
            return evaluation
        failures.append(evaluation)
    return failures[0]


def _evaluate_record(
    provider: ProviderProfile,
    programme: CertificationProgramme,
    record: CertificationRecord,
    reference_date: date,
) -> CertificationEvaluation:
    held = record.status == "held"
    if not held:
        return CertificationEvaluation(
            programme.id, False, f"status is {record.status or 'missing'}"
        )
    if record.kind and record.kind != programme.kind:
        return CertificationEvaluation(
            programme.id, False, "record kind does not match catalogue", held=True
        )
    if record.valid_from and record.valid_from > reference_date:
        return CertificationEvaluation(
            programme.id, False, "validity has not started", held=True
        )

    validity = record.validity or ("fixed" if record.valid_until else "unknown")
    if validity == "unknown":
        return CertificationEvaluation(
            programme.id, False, "validity is unknown", held=True
        )
    if validity == "fixed" and record.valid_until is None:
        return CertificationEvaluation(
            programme.id, False, "fixed validity has no end date", held=True
        )
    if record.valid_until and record.valid_until < reference_date:
        return CertificationEvaluation(
            programme.id,
            False,
            "programme is expired",
            held=True,
            valid_until=record.valid_until,
        )

    scope_matches, scope_reason = _scope_matches(provider, record)
    if not scope_matches:
        return CertificationEvaluation(
            programme.id,
            False,
            scope_reason,
            held=True,
            current=True,
            valid_until=record.valid_until,
        )

    return CertificationEvaluation(
        programme.id,
        True,
        "current and in scope",
        held=True,
        current=True,
        scope_matches=True,
        valid_until=record.valid_until,
    )


def _scope_matches(
    provider: ProviderProfile,
    record: CertificationRecord,
) -> tuple[bool, str]:
    offering = provider.offering
    if provider.is_v2 and offering is None:
        return False, "assessment offering is missing"
    if offering is None:
        return True, "legacy provider scope"
    if record.offering != offering.id:
        return False, "programme is for a different or unspecified offering"

    required_regions = set(offering.regions)
    covered_regions = set(record.regions)
    if not required_regions.issubset(covered_regions):
        return False, "programme does not cover all assessment regions"

    required_services = {service.id for service in provider.services_in_scope}
    if provider.is_v2:
        if record.all_services and record.services:
            return False, "programme service scope is ambiguous"
        if not record.all_services and not record.services:
            return False, "programme service scope is unspecified"
    if not record.all_services and not required_services.issubset(
        set(record.services)
    ):
        return False, "programme does not cover all assessment services"
    return True, "scope matches"
