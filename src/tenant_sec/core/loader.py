"""YAML loading, JSON Schema validation, and parsing into typed models."""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import Any, Optional

import jsonschema
import yaml

from .models import (
    AssessmentClaim,
    AssessmentStatus,
    CertificationRecord,
    Control,
    CriteriaResult,
    EvidenceApplicability,
    EvidenceItem,
    LeafControlScore,
    MixedControlScore,
    MustHaveEntry,
    ProviderOffering,
    ProviderProfile,
    Reference,
    ScoringProfile,
    ServiceInScope,
    ServiceScore,
)
from .registry import ControlRegistry, ServiceCatalog
from .certifications import CertificationCatalog

# Schema file names
SCHEMA_NAMES = {
    "control": "control.schema.json",
    "provider": "provider.schema.json",
    "scoring-profile": "scoring-profile.schema.json",
    "maturity": "maturity.schema.json",
    "certification-catalog": "certification-catalog.schema.json",
}


class ValidationError(Exception):
    """Raised when a YAML file fails schema validation."""

    def __init__(self, message: str, path: Optional[Path] = None) -> None:
        self.file_path = path
        prefix = f"{path}: " if path else ""
        super().__init__(f"{prefix}{message}")


def _load_schema(schema_dir: Path, schema_type: str) -> dict:
    schema_file = schema_dir / SCHEMA_NAMES[schema_type]
    if not schema_file.exists():
        raise FileNotFoundError(f"Schema not found: {schema_file}")
    with open(schema_file) as f:
        return json.load(f)


def _validate_yaml(data: dict, schema: dict, path: Optional[Path] = None) -> None:
    validator = jsonschema.Draft202012Validator(
        schema,
        format_checker=jsonschema.FormatChecker(),
    )
    errors = list(validator.iter_errors(data))
    if errors:
        # Report the first / most specific error
        error = jsonschema.exceptions.best_match(errors)
        field = " -> ".join(str(p) for p in error.absolute_path) or "root"
        raise ValidationError(
            f"Validation error at '{field}': {error.message}",
            path=path,
        )


def _semantic_errors(data: dict, file_type: str, schema_dir: Path) -> list[str]:
    """Cross-field rules that JSON Schema cannot express cleanly."""
    errors: list[str] = []
    cert_path = schema_dir / "certification-catalog.yaml"
    cert_catalog = (
        CertificationCatalog.from_file(cert_path) if cert_path.exists() else None
    )

    if file_type == "scoring-profile":
        for cert_id in data.get("must_have_certifications") or []:
            programme = cert_catalog.get(cert_id) if cert_catalog else None
            if programme is None:
                errors.append(
                    f"Unknown required certification id '{cert_id}'"
                )
            elif not cert_catalog.is_holdable(cert_id):
                errors.append(
                    f"Required programme '{cert_id}' cannot be held"
                )
        return errors

    if file_type != "provider":
        return errors

    is_v2 = str(data.get("methodology_version", "")).startswith("2.")
    service_ids = [svc.get("id") for svc in data.get("services_in_scope") or []]
    if len(service_ids) != len(set(service_ids)):
        errors.append("services_in_scope IDs must be unique service instances")

    for record in data.get("certifications") or []:
        cert_id = record.get("id", "")
        programme = cert_catalog.get(cert_id) if cert_catalog else None
        if programme is None:
            errors.append(f"Unknown certification id '{cert_id}'")
            continue
        if record.get("kind") and record["kind"] != programme.kind:
            errors.append(
                f"Certification '{cert_id}' kind must be '{programme.kind}'"
            )
        if record.get("status") == "held" and not cert_catalog.is_holdable(cert_id):
            errors.append(f"Programme '{cert_id}' cannot be recorded as held")
        if is_v2:
            required = (
                "status",
                "validity",
                "scope",
                "offering",
                "regions",
                "report_access",
                "evidence",
            )
            missing = [
                field
                for field in required
                if record.get(field) in (None, "", [])
            ]
            if missing:
                errors.append(
                    f"Certification '{cert_id}' is missing v2 fields: "
                    + ", ".join(missing)
                )
            if record.get("validity") == "fixed" and not record.get("valid_until"):
                errors.append(
                    f"Certification '{cert_id}' has fixed validity without valid_until"
                )
            if record.get("status") == "held" and record.get("validity") == "unknown":
                errors.append(
                    f"Held certification '{cert_id}' cannot have unknown validity"
                )
            services = record.get("services") or []
            all_services = bool(record.get("all_services", False))
            if bool(services) == all_services:
                errors.append(
                    f"Certification '{cert_id}' must declare either a non-empty "
                    "services list or all_services: true, but not both"
                )

    if not is_v2:
        return errors

    offering = data.get("offering") or {}
    identity_parts = str(data.get("assessment_id", "")).split("/")
    if (
        not identity_parts
        or identity_parts[0] != data.get("provider")
        or offering.get("id") not in identity_parts[1:]
    ):
        errors.append(
            "assessment_id must start with the provider and include offering.id"
        )
    if (
        len(offering.get("regions") or []) > 1
        and not offering.get("region_equivalence")
    ):
        errors.append(
            "A multi-region v2 assessment requires region_equivalence; "
            "otherwise use separate assessment files"
        )

    for control_id, result in (data.get("controls") or {}).items():
        status = result.get("status")
        if result.get("score") == "mixed":
            extra_services = set(result.get("services") or {}) - set(service_ids)
            if extra_services:
                errors.append(
                    f"Control '{control_id}' contains services outside "
                    f"services_in_scope: {', '.join(sorted(extra_services))}"
                )
            if status != "assessed":
                errors.append(
                    f"Control '{control_id}' must explicitly use status 'assessed'"
                )
            if not result.get("references"):
                errors.append(
                    f"Assessed control '{control_id}' requires references"
                )
            if not result.get("confidence"):
                errors.append(
                    f"Assessed control '{control_id}' requires confidence"
                )
            errors.extend(_validate_claim_bundle(control_id, result))
            for service_id, service in (result.get("services") or {}).items():
                if service.get("score") is not None:
                    if service.get("status") != "assessed":
                        errors.append(
                            f"Control '{control_id}' service '{service_id}' "
                            "must explicitly use status 'assessed'"
                        )
                    if not service.get("references"):
                        errors.append(
                            f"Control '{control_id}' service '{service_id}' "
                            "requires references"
                        )
                elif service.get("status") is None:
                    errors.append(
                        f"Control '{control_id}' service '{service_id}' "
                        "must use an explicit non-score status"
                    )
        elif result.get("score") is not None:
            if status != "assessed":
                errors.append(
                    f"Control '{control_id}' must explicitly use status 'assessed'"
                )
            if not result.get("references"):
                errors.append(
                    f"Assessed control '{control_id}' requires references"
                )
            if not result.get("confidence"):
                errors.append(
                    f"Assessed control '{control_id}' requires confidence"
                )
            errors.extend(_validate_claim_bundle(control_id, result))

    return errors


def _validate_claim_bundle(control_id: str, result: dict) -> list[str]:
    errors: list[str] = []
    evidence = result.get("evidence_items") or []
    claims = result.get("claims") or []
    criteria = result.get("criteria_results") or []
    if not evidence:
        errors.append(
            f"Assessed control '{control_id}' requires evidence_items"
        )
    if not claims:
        errors.append(f"Assessed control '{control_id}' requires claims")
    if {item.get("level") for item in criteria} != {0, 1, 2, 3}:
        errors.append(
            f"Assessed control '{control_id}' requires one criteria result "
            "for each level L0-L3"
        )
    evidence_ids = {item.get("id") for item in evidence}
    claim_ids = {claim.get("id") for claim in claims}
    for claim in claims:
        missing = set(claim.get("evidence_item_ids") or []) - evidence_ids
        if missing:
            errors.append(
                f"Control '{control_id}' claim '{claim.get('id')}' references "
                f"unknown evidence: {', '.join(sorted(missing))}"
            )
    for item in criteria:
        missing = set(item.get("claim_ids") or []) - claim_ids
        if missing:
            errors.append(
                f"Control '{control_id}' L{item.get('level')} references "
                f"unknown claims: {', '.join(sorted(missing))}"
            )
    return errors


def detect_file_type(data: dict) -> Optional[str]:
    """Heuristic: detect which schema type a YAML file matches."""
    if "criteria" in data:
        return "control"
    if "controls" in data and "provider" in data:
        return "provider"
    if "weights" in data and "mixed_aggregation" in data:
        return "scoring-profile"
    if "programmes" in data and "version" in data:
        return "certification-catalog"
    return None


def load_yaml_file(path: Path) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def load_control(path: Path, schema_dir: Optional[Path] = None) -> Control:
    data = load_yaml_file(path)
    if schema_dir:
        schema = _load_schema(schema_dir, "control")
        _validate_yaml(data, schema, path)
    return _parse_control(data)


def load_provider(path: Path, schema_dir: Optional[Path] = None) -> ProviderProfile:
    data = load_yaml_file(path)
    if schema_dir:
        schema = _load_schema(schema_dir, "provider")
        _validate_yaml(data, schema, path)
        semantic_errors = _semantic_errors(data, "provider", schema_dir)
        if semantic_errors:
            raise ValidationError(semantic_errors[0], path)
    return _parse_provider(data)


def load_scoring_profile(
    path: Path, schema_dir: Optional[Path] = None
) -> ScoringProfile:
    data = load_yaml_file(path)
    if schema_dir:
        schema = _load_schema(schema_dir, "scoring-profile")
        _validate_yaml(data, schema, path)
        semantic_errors = _semantic_errors(data, "scoring-profile", schema_dir)
        if semantic_errors:
            raise ValidationError(semantic_errors[0], path)
    return _parse_scoring_profile(data)


def load_control_registry(controls_dir: Path) -> ControlRegistry:
    return ControlRegistry.from_directory(controls_dir)


def load_service_catalog(catalog_path: Path) -> ServiceCatalog:
    return ServiceCatalog.from_file(catalog_path)


def load_certification_catalog(catalog_path: Path) -> CertificationCatalog:
    return CertificationCatalog.from_file(catalog_path)


# ── Parsing helpers ────────────────────────────────────────────────────────────


def _parse_control(data: dict) -> Control:
    return Control(
        id=data["id"],
        domain=data["domain"],
        name=data["name"],
        description=data.get("description", ""),
        criteria=data.get("criteria", {}),
        framework_mappings=data.get("framework_mappings", {}),
        service_scoped=data.get("service_scoped", False),
        parent=data.get("parent"),
        sub_control_aggregation=data.get("sub_control_aggregation"),
        surface=data.get("surface", "tenant"),
    )


def _parse_date(value: Any) -> Optional[date]:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def _parse_status(value: Any) -> Optional[AssessmentStatus]:
    if value is None:
        return None
    return AssessmentStatus(str(value))


def _parse_references(values: Any) -> list[Reference]:
    return [
        Reference(url=str(ref["url"]), title=str(ref["title"]))
        for ref in (values or [])
    ]


def _parse_evidence_items(values: Any) -> list[EvidenceItem]:
    items: list[EvidenceItem] = []
    for raw in values or []:
        scope = raw["applicability"]
        retrieved = str(raw["retrieved_at"]).replace("Z", "+00:00")
        items.append(
            EvidenceItem(
                id=str(raw["id"]),
                url=str(raw["url"]),
                title=str(raw["title"]),
                source_class=str(raw["source_class"]),
                retrieved_at=datetime.fromisoformat(retrieved),
                updated_at=_parse_date(raw.get("updated_at")),
                content_hash=str(raw["content_hash"]),
                quote=str(raw["quote"]),
                applicability=EvidenceApplicability(
                    offering=str(scope["offering"]),
                    regions=[str(v) for v in scope.get("regions") or []],
                    services=[str(v) for v in scope.get("services") or []],
                    edition=str(scope["edition"]),
                ),
            )
        )
    return items


def _parse_claims(values: Any) -> list[AssessmentClaim]:
    return [
        AssessmentClaim(
            id=str(raw["id"]),
            assertion=str(raw["assertion"]),
            result=str(raw["result"]),
            evidence_item_ids=[
                str(value) for value in raw.get("evidence_item_ids") or []
            ],
            services=[str(value) for value in raw.get("services") or []],
        )
        for raw in values or []
    ]


def _parse_criteria_results(values: Any) -> list[CriteriaResult]:
    return [
        CriteriaResult(
            level=int(raw["level"]),
            met=bool(raw["met"]),
            reasoning=str(raw["reasoning"]),
            claim_ids=[str(value) for value in raw.get("claim_ids") or []],
        )
        for raw in values or []
    ]


def _parse_control_score(data: dict) -> LeafControlScore | MixedControlScore:
    if data.get("score") == "mixed":
        services: dict[str, ServiceScore] = {}
        for svc_id, svc_data in data.get("services", {}).items():
            services[svc_id] = ServiceScore(
                score=svc_data.get("score"),
                evidence=svc_data["evidence"],
                status=_parse_status(svc_data.get("status")),
                confidence=svc_data.get("confidence"),
                references=_parse_references(svc_data.get("references")),
            )
        return MixedControlScore(
            services=services,
            summary=data.get("summary"),
            verified_at=_parse_date(data.get("verified_at")),
            status=_parse_status(data.get("status")),
            confidence=data.get("confidence"),
            references=_parse_references(data.get("references")),
            evidence_items=_parse_evidence_items(data.get("evidence_items")),
            claims=_parse_claims(data.get("claims")),
            criteria_results=_parse_criteria_results(
                data.get("criteria_results")
            ),
        )
    else:
        return LeafControlScore(
            score=int(data["score"]) if data.get("score") is not None else None,
            evidence=data["evidence"],
            compensating_controls=data.get("compensating_controls"),
            verified_at=_parse_date(data.get("verified_at")),
            status=_parse_status(data.get("status")),
            confidence=data.get("confidence"),
            references=_parse_references(data.get("references")),
            evidence_items=_parse_evidence_items(data.get("evidence_items")),
            claims=_parse_claims(data.get("claims")),
            criteria_results=_parse_criteria_results(
                data.get("criteria_results")
            ),
        )


def _parse_provider(data: dict) -> ProviderProfile:
    services = [
        ServiceInScope(
            id=svc["id"],
            name=svc["name"],
            category=svc["category"],
            aliases=svc.get("aliases", []),
            regions=svc.get("regions", []),
            edition=svc.get("edition"),
        )
        for svc in data.get("services_in_scope", [])
    ]

    controls = {
        control_id: _parse_control_score(score_data)
        for control_id, score_data in data.get("controls", {}).items()
    }

    offering_data = data.get("offering") or {}
    offering = None
    if offering_data:
        offering = ProviderOffering(
            id=offering_data.get("id"),
            name=offering_data.get("name"),
            partition=offering_data.get("partition"),
            regions=offering_data.get("regions") or [],
            region_equivalence=offering_data.get("region_equivalence"),
            edition=offering_data.get("edition"),
            cohort=offering_data.get("cohort"),
        )

    certifications = [
        CertificationRecord(
            id=rec["id"],
            kind=rec.get("kind"),
            status=rec.get("status", "held"),
            valid_from=_parse_date(rec.get("valid_from")),
            valid_until=_parse_date(rec.get("valid_until")),
            validity=rec.get("validity"),
            scope=rec.get("scope"),
            offering=rec.get("offering"),
            regions=rec.get("regions") or [],
            services=rec.get("services") or [],
            all_services=bool(rec.get("all_services", False)),
            report_access=rec.get("report_access"),
            evidence=_parse_references(rec.get("evidence")),
        )
        for rec in data.get("certifications") or []
    ]

    return ProviderProfile(
        provider=data["provider"],
        display_name=data["display_name"],
        assessed_by=data["assessed_by"],
        assessed_at=date.fromisoformat(str(data["assessed_at"])),
        methodology_version=data["methodology_version"],
        revision=data["revision"],
        services_in_scope=services,
        controls=controls,
        assessment_id=data.get("assessment_id"),
        offering=offering,
        vignette=data.get("vignette") or {},
        certifications=certifications,
        service_scope_exceptions=data.get("service_scope_exceptions") or {},
    )


def _parse_scoring_profile(data: dict) -> ScoringProfile:
    must_have = [
        MustHaveEntry(control=mh["control"], min_level=mh["min_level"])
        for mh in data.get("must_have", [])
    ]
    return ScoringProfile(
        name=data["name"],
        description=data.get("description"),
        methodology_version=data.get("methodology_version"),
        must_have=must_have,
        must_have_certifications=list(data.get("must_have_certifications") or []),
        min_catalog_coverage=data.get("min_catalog_coverage"),
        min_catalog_completeness=data.get("min_catalog_completeness"),
        cohort=data.get("cohort"),
        service_coverage_thresholds=tuple(
            data.get("service_coverage_thresholds") or (2, 3)
        ),
        weights=data["weights"],
        mixed_aggregation=data["mixed_aggregation"],
    )


def validate_file(
    path: Path,
    schema_dir: Path,
    file_type: Optional[str] = None,
    controls_dir: Optional[Path] = None,
    catalog_path: Optional[Path] = None,
) -> list[str]:
    """Validate a YAML file. Returns list of error messages (empty = valid)."""
    errors: list[str] = []

    try:
        data = load_yaml_file(path)
    except Exception as exc:
        return [f"Cannot load YAML: {exc}"]

    # Detect type if not specified
    detected_type = file_type or detect_file_type(data)
    if detected_type is None:
        return ["Cannot determine file type (use --type to specify)"]

    # Schema validation
    try:
        schema = _load_schema(schema_dir, detected_type)
        _validate_yaml(data, schema, path)
    except ValidationError as exc:
        errors.append(str(exc))
        return errors  # Can't proceed with cross-ref checks if schema is invalid
    except Exception as exc:
        errors.append(f"Schema validation error: {exc}")
        return errors

    errors.extend(_semantic_errors(data, detected_type, schema_dir))
    if errors:
        return errors

    if detected_type == "scoring-profile" and controls_dir:
        registry = load_control_registry(controls_dir)
        for requirement in data.get("must_have") or []:
            control_id = requirement.get("control", "")
            control = registry.get(control_id)
            if control is None:
                errors.append(f"Unknown must-have control ID '{control_id}'")
            elif control.surface != "tenant":
                errors.append(
                    f"Must-have control '{control_id}' is not tenant-scored"
                )
        tenant_domains = {
            control.domain
            for control in registry.all_controls()
            if control.surface == "tenant"
        }
        for domain, weight in (data.get("weights") or {}).items():
            if float(weight) > 0 and domain not in tenant_domains:
                errors.append(
                    f"Domain '{domain}' has positive weight but no tenant controls"
                )

    # Cross-reference checks for provider profiles
    if detected_type == "provider" and controls_dir and catalog_path:
        registry = load_control_registry(controls_dir)
        catalog = load_service_catalog(catalog_path)

        for control_id in data.get("controls", {}).keys():
            control = registry.get(control_id)
            if control is None:
                errors.append(
                    f"Unknown control ID '{control_id}' — not found in controls/_index.yaml"
                )

        for control_id in (data.get("service_scope_exceptions") or {}):
            control = registry.get(control_id)
            if control is None or not control.service_scoped:
                errors.append(
                    f"Invalid service_scope_exceptions control '{control_id}'"
                )

        # Check service IDs in mixed composites resolve through catalog
        provider_slug = data.get("provider", "")
        for control_id, score_data in data.get("controls", {}).items():
            if score_data.get("score") == "mixed":
                for svc_id in score_data.get("services", {}).keys():
                    resolved = catalog.resolve(provider_slug, svc_id)
                    if resolved is None:
                        errors.append(
                            f"Control '{control_id}': service alias '{svc_id}' "
                            f"not found in service catalog for provider '{provider_slug}'"
                        )

        catalog_path_dir = catalog_path.parent if catalog_path else None
        if catalog_path_dir:
            cert_catalog_file = catalog_path_dir / "certification-catalog.yaml"
            if cert_catalog_file.exists() and data.get("certifications"):
                cert_catalog = CertificationCatalog.from_file(cert_catalog_file)
                for rec in data["certifications"]:
                    cid = rec.get("id")
                    if cid and cert_catalog.get(cid) is None:
                        errors.append(
                            f"Unknown certification id '{cid}' — not in certification-catalog.yaml"
                        )

    return errors
