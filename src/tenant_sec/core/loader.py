"""YAML loading, JSON Schema validation, and parsing into typed models."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any, Optional

import jsonschema
import yaml

from .models import (
    Control,
    LeafControlScore,
    MixedControlScore,
    MustHaveEntry,
    ProviderProfile,
    ScoringProfile,
    ServiceInScope,
    ServiceScore,
)
from .registry import ControlRegistry, ServiceCatalog

# Schema file names
SCHEMA_NAMES = {
    "control": "control.schema.json",
    "provider": "provider.schema.json",
    "scoring-profile": "scoring-profile.schema.json",
    "maturity": "maturity.schema.json",
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
    validator = jsonschema.Draft202012Validator(schema)
    errors = list(validator.iter_errors(data))
    if errors:
        # Report the first / most specific error
        error = jsonschema.exceptions.best_match(errors)
        field = " -> ".join(str(p) for p in error.absolute_path) or "root"
        raise ValidationError(
            f"Validation error at '{field}': {error.message}",
            path=path,
        )


def detect_file_type(data: dict) -> Optional[str]:
    """Heuristic: detect which schema type a YAML file matches."""
    if "criteria" in data:
        return "control"
    if "controls" in data and "provider" in data:
        return "provider"
    if "weights" in data and "mixed_aggregation" in data:
        return "scoring-profile"
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
    return _parse_provider(data)


def load_scoring_profile(
    path: Path, schema_dir: Optional[Path] = None
) -> ScoringProfile:
    data = load_yaml_file(path)
    if schema_dir:
        schema = _load_schema(schema_dir, "scoring-profile")
        _validate_yaml(data, schema, path)
    return _parse_scoring_profile(data)


def load_control_registry(controls_dir: Path) -> ControlRegistry:
    return ControlRegistry.from_directory(controls_dir)


def load_service_catalog(catalog_path: Path) -> ServiceCatalog:
    return ServiceCatalog.from_file(catalog_path)


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
    )


def _parse_date(value: Any) -> Optional[date]:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def _parse_control_score(data: dict) -> LeafControlScore | MixedControlScore:
    if data.get("score") == "mixed":
        services: dict[str, ServiceScore] = {}
        for svc_id, svc_data in data.get("services", {}).items():
            services[svc_id] = ServiceScore(
                score=svc_data["score"],
                evidence=svc_data["evidence"],
            )
        return MixedControlScore(
            services=services,
            summary=data.get("summary"),
            verified_at=_parse_date(data.get("verified_at")),
        )
    else:
        return LeafControlScore(
            score=int(data["score"]),
            evidence=data["evidence"],
            compensating_controls=data.get("compensating_controls"),
            verified_at=_parse_date(data.get("verified_at")),
        )


def _parse_provider(data: dict) -> ProviderProfile:
    services = [
        ServiceInScope(
            id=svc["id"],
            name=svc["name"],
            category=svc["category"],
            aliases=svc.get("aliases", []),
        )
        for svc in data.get("services_in_scope", [])
    ]

    controls = {
        control_id: _parse_control_score(score_data)
        for control_id, score_data in data.get("controls", {}).items()
    }

    return ProviderProfile(
        provider=data["provider"],
        display_name=data["display_name"],
        assessed_by=data["assessed_by"],
        assessed_at=date.fromisoformat(str(data["assessed_at"])),
        methodology_version=data["methodology_version"],
        revision=data["revision"],
        services_in_scope=services,
        controls=controls,
    )


def _parse_scoring_profile(data: dict) -> ScoringProfile:
    must_have = [
        MustHaveEntry(control=mh["control"], min_level=mh["min_level"])
        for mh in data.get("must_have", [])
    ]
    return ScoringProfile(
        name=data["name"],
        description=data.get("description"),
        must_have=must_have,
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

    # Cross-reference checks for provider profiles
    if detected_type == "provider" and controls_dir and catalog_path:
        registry = load_control_registry(controls_dir)
        catalog = load_service_catalog(catalog_path)

        for control_id in data.get("controls", {}).keys():
            if registry.get(control_id) is None:
                errors.append(
                    f"Unknown control ID '{control_id}' — not found in controls/_index.yaml"
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

    return errors
