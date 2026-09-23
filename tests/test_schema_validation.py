"""JSON Schema validation tests for all example files."""

from __future__ import annotations

from pathlib import Path

import pytest

from tenant_sec.core.loader import (
    _load_schema,
    _validate_yaml,
    load_provider,
    load_yaml_file,
    validate_file,
)
from tenant_sec.cli.export import _provider_to_csv, _provider_to_dict


REPO_ROOT = Path(__file__).parent.parent
SCHEMA_DIR = REPO_ROOT / "schema"
CONTROLS_DIR = REPO_ROOT / "controls"
PROVIDERS_DIR = REPO_ROOT / "providers"
PROFILES_DIR = REPO_ROOT / "profiles"
CATALOG_PATH = SCHEMA_DIR / "service-catalog.yaml"
V2_FIXTURE = REPO_ROOT / "tests" / "fixtures" / "provider-v2-minimal.yaml"


# ── Schema files themselves must exist ───────────────────────────────────────

def test_schema_files_exist():
    for name in ["control.schema.json", "provider.schema.json",
                 "scoring-profile.schema.json", "maturity.schema.json",
                 "certification-catalog.schema.json"]:
        assert (SCHEMA_DIR / name).exists(), f"Schema file missing: {name}"


def test_service_catalog_exists():
    assert CATALOG_PATH.exists()


def test_certification_catalog_validates():
    import json
    import yaml

    catalog_path = SCHEMA_DIR / "certification-catalog.yaml"
    schema_path = SCHEMA_DIR / "certification-catalog.schema.json"
    assert catalog_path.exists()
    data = yaml.safe_load(catalog_path.read_text())
    with open(schema_path) as f:
        schema = json.load(f)
    _validate_yaml(data, schema, catalog_path)
    assert "iso-27001" in data["programmes"]
    assert data["programmes"]["bsi-c5-type2"]["kind"] == "attestation"
    assert data["programmes"]["eucs"]["kind"] == "scheme-draft"


# ── Control files ─────────────────────────────────────────────────────────────

def _all_control_files():
    return list(CONTROLS_DIR.rglob("*.yaml"))


@pytest.mark.parametrize("control_path", [
    pytest.param(p, id=p.stem)
    for p in sorted((CONTROLS_DIR).rglob("*.yaml"))
    if p.name != "_index.yaml"
])
def test_control_file_validates(control_path):
    errors = validate_file(
        path=control_path,
        schema_dir=SCHEMA_DIR,
        file_type="control",
    )
    assert errors == [], f"Validation errors in {control_path}:\n" + "\n".join(errors)


def test_controls_index_exists():
    assert (CONTROLS_DIR / "_index.yaml").exists()


def test_controls_index_all_files_present():
    """Every control ID in _index.yaml must have a corresponding YAML file."""
    import yaml
    with open(CONTROLS_DIR / "_index.yaml") as f:
        index = yaml.safe_load(f)

    missing = []
    for domain_slug, domain_info in index.get("domains", {}).items():
        for control_id in domain_info.get("controls", []):
            filename = control_id.split(".", 1)[1] + ".yaml"
            expected_path = CONTROLS_DIR / domain_slug / filename
            if not expected_path.exists():
                missing.append(str(expected_path))

    assert missing == [], f"Missing control files:\n" + "\n".join(missing)


def test_total_control_count():
    """Should have 50-70 controls."""
    control_files = [
        p for p in CONTROLS_DIR.rglob("*.yaml") if p.name != "_index.yaml"
    ]
    count = len(control_files)
    assert 50 <= count <= 80, f"Unexpected control count: {count}"


# ── Provider profiles ─────────────────────────────────────────────────────────

@pytest.mark.parametrize("provider_path", [
    pytest.param(p, id=p.stem)
    for p in sorted(PROVIDERS_DIR.glob("*.yaml"))
])
def test_provider_profile_validates(provider_path):
    errors = validate_file(
        path=provider_path,
        schema_dir=SCHEMA_DIR,
        file_type="provider",
        controls_dir=CONTROLS_DIR,
        catalog_path=CATALOG_PATH,
    )
    assert errors == [], f"Validation errors in {provider_path}:\n" + "\n".join(errors)


# ── Scoring profiles ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("profile_path", [
    pytest.param(p, id=p.stem)
    for p in sorted(PROFILES_DIR.glob("*.yaml"))
])
def test_scoring_profile_validates(profile_path):
    errors = validate_file(
        path=profile_path,
        schema_dir=SCHEMA_DIR,
        file_type="scoring-profile",
        controls_dir=CONTROLS_DIR,
    )
    assert errors == [], f"Validation errors in {profile_path}:\n" + "\n".join(errors)


def test_scoring_profile_weights_sum_to_one():
    import yaml
    from tenant_sec.core.loader import load_scoring_profile

    for profile_path in PROFILES_DIR.glob("*.yaml"):
        sp = load_scoring_profile(profile_path, SCHEMA_DIR)
        total = sum(sp.weights.values())
        assert abs(total - 1.0) < 1e-9, (
            f"{profile_path.stem}: weights sum to {total:.4f}, not 1.0"
        )


def test_minimal_v2_provider_loads_and_round_trips():
    provider = load_provider(V2_FIXTURE, SCHEMA_DIR)
    exported = _provider_to_dict(provider)
    _validate_yaml(exported, _load_schema(SCHEMA_DIR, "provider"), V2_FIXTURE)
    assert exported["assessment_id"] == "aws/public/eu/standard"
    assert exported["offering"]["id"] == "public"
    assert exported["controls"]["iam.abac"]["confidence"] == "high"
    assert exported["controls"]["iam.abac"]["claims"][0]["id"] == (
        "cl-abac-managed"
    )
    assert exported["controls"]["iam.abac"]["evidence_items"][0][
        "content_hash"
    ].startswith("sha256:")
    assert {
        result["level"]
        for result in exported["controls"]["iam.abac"]["criteria_results"]
    } == {0, 1, 2, 3}
    assert exported["controls"]["enc.cmk"]["services"]["s3"][
        "status"
    ] == "unknown"
    assert exported["certifications"][0]["evidence"][0]["url"].startswith(
        "https://"
    )
    assert exported["certifications"][0]["all_services"] is True
    import csv
    import io

    row = next(csv.DictReader(io.StringIO(_provider_to_csv(provider))))
    assert row["assessment_id"] == "aws/public/eu/standard"
    assert row["offering_id"] == "public"
    assert row["cohort"] == "eu-public"
    assert "iso-27001" in row["certifications_json"]


def test_unknown_result_cannot_carry_score(tmp_path):
    data = load_yaml_file(V2_FIXTURE)
    data["controls"]["iam.abac"]["status"] = "unknown"
    path = tmp_path / "invalid-unknown.yaml"
    import yaml

    path.write_text(yaml.safe_dump(data))
    errors = validate_file(path, SCHEMA_DIR, file_type="provider")
    assert errors


def test_v2_bare_certification_is_rejected(tmp_path):
    data = load_yaml_file(V2_FIXTURE)
    data["certifications"] = [{"id": "iso-27001"}]
    path = tmp_path / "invalid-cert.yaml"
    import yaml

    path.write_text(yaml.safe_dump(data))
    errors = validate_file(path, SCHEMA_DIR, file_type="provider")
    assert any("missing v2 fields" in error for error in errors)


def test_v2_certification_requires_explicit_service_scope(tmp_path):
    data = load_yaml_file(V2_FIXTURE)
    data["certifications"][0].pop("all_services")
    path = tmp_path / "invalid-cert-scope.yaml"
    import yaml

    path.write_text(yaml.safe_dump(data))
    errors = validate_file(path, SCHEMA_DIR, file_type="provider")
    assert any("services list or all_services" in error for error in errors)


def test_v2_rejects_extra_mixed_service_and_missing_service_reference(tmp_path):
    import yaml

    data = load_yaml_file(V2_FIXTURE)
    data["controls"]["enc.cmk"]["services"]["not-in-scope"] = {
        "status": "assessed",
        "score": 3,
        "confidence": "high",
        "evidence": "extra",
        "references": [
            {"url": "https://example.com/extra", "title": "Extra"}
        ],
    }
    path = tmp_path / "extra-service.yaml"
    path.write_text(yaml.safe_dump(data))
    errors = validate_file(path, SCHEMA_DIR, file_type="provider")
    assert any("outside services_in_scope" in error for error in errors)

    data = load_yaml_file(V2_FIXTURE)
    service = data["controls"]["enc.cmk"]["services"]["s3"]
    service.update({"status": "assessed", "score": 2, "confidence": "medium"})
    path = tmp_path / "missing-service-reference.yaml"
    path.write_text(yaml.safe_dump(data))
    errors = validate_file(path, SCHEMA_DIR, file_type="provider")
    assert any("service 's3' requires references" in error for error in errors)


def test_v2_region_set_requires_equivalence_claim(tmp_path):
    data = load_yaml_file(V2_FIXTURE)
    data["offering"]["regions"] = ["eu-1", "eu-2"]
    path = tmp_path / "invalid-regions.yaml"
    import yaml

    path.write_text(yaml.safe_dump(data))
    errors = validate_file(path, SCHEMA_DIR, file_type="provider")
    assert any("region_equivalence" in error for error in errors)


def test_scheme_draft_cannot_be_required(tmp_path):
    import yaml

    path = tmp_path / "invalid-profile.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "name": "invalid",
                "weights": {"iam": 1.0},
                "mixed_aggregation": "min",
                "must_have_certifications": ["eucs"],
            }
        )
    )
    errors = validate_file(path, SCHEMA_DIR, file_type="scoring-profile")
    assert any("cannot be held" in error for error in errors)
