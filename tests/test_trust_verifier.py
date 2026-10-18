"""Strict methodology-2 evidence-to-score verification tests."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import yaml

from tenant_sec.core.loader import load_yaml_file, validate_file


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "schema"
CONTROLS = ROOT / "controls"
CATALOG = SCHEMA / "service-catalog.yaml"
FIXTURE = ROOT / "tests" / "fixtures" / "provider-v2-minimal.yaml"


def _validate(data: dict, tmp_path: Path, mode: str = "strict") -> list[str]:
    path = tmp_path / "provider.yaml"
    path.write_text(yaml.safe_dump(data, sort_keys=False))
    return validate_file(
        path,
        SCHEMA,
        file_type="provider",
        controls_dir=CONTROLS,
        catalog_path=CATALOG,
        trust_mode=mode,
    )


def test_minimal_v2_fixture_passes_strict_trust(tmp_path):
    assert _validate(load_yaml_file(FIXTURE), tmp_path) == []


def test_strict_trust_rejects_score_criteria_mismatch(tmp_path):
    data = load_yaml_file(FIXTURE)
    data["controls"]["iam.abac"]["score"] = 3

    errors = _validate(data, tmp_path)

    assert any("TRUST_SCORE_CRITERIA_MISMATCH" in error for error in errors)


def test_strict_trust_rejects_bad_claim_on_met_criterion(tmp_path):
    data = load_yaml_file(FIXTURE)
    data["controls"]["iam.abac"]["claims"][0]["result"] = "contradicted"

    errors = _validate(data, tmp_path)

    assert any("TRUST_MET_CRITERIA_BAD_CLAIM" in error for error in errors)


def test_strict_trust_rejects_met_criterion_without_claims(tmp_path):
    data = load_yaml_file(FIXTURE)
    criteria = data["controls"]["iam.abac"]["criteria_results"]
    next(item for item in criteria if item["level"] == 2)["claim_ids"] = []

    errors = _validate(data, tmp_path)

    assert any("TRUST_MET_CRITERIA_NO_CLAIMS" in error for error in errors)


def test_strict_trust_rejects_weak_only_evidence(tmp_path):
    data = load_yaml_file(FIXTURE)
    data["controls"]["iam.abac"]["evidence_items"][0][
        "source_class"
    ] = "secondary"

    errors = _validate(data, tmp_path)

    assert any("TRUST_WEAK_CLAIM_EVIDENCE" in error for error in errors)


def test_strict_trust_requires_supported_claim_for_assessed_service(tmp_path):
    data = load_yaml_file(FIXTURE)
    cmk = data["controls"]["enc.cmk"]
    next(
        item for item in cmk["criteria_results"] if item["level"] == 2
    )["met"] = True
    cmk["services"]["s3"] = {
        "status": "assessed",
        "score": 2,
        "confidence": "medium",
        "evidence": "Managed CMK support is established with limitations.",
        "references": deepcopy(cmk["references"]),
    }
    assert _validate(data, tmp_path) == []

    cmk["claims"][0]["services"] = ["different-service"]
    errors = _validate(data, tmp_path)
    assert any(
        "TRUST_SERVICE_SCORE_NO_SUPPORTED_CLAIM" in error for error in errors
    )


def test_url_as_title_is_a_publication_failure_only(tmp_path):
    data = load_yaml_file(FIXTURE)
    reference = data["controls"]["iam.abac"]["references"][0]
    reference["title"] = reference["url"]

    assert _validate(data, tmp_path, "strict") == []
    errors = _validate(data, tmp_path, "publication")

    assert any("TRUST_URL_AS_TITLE" in error for error in errors)


def test_publication_rejects_provisional_service_scope_exception(tmp_path):
    data = load_yaml_file(FIXTURE)
    data["review_status"] = "unreviewed"
    data["controls"]["enc.cmk"] = deepcopy(data["controls"]["iam.abac"])
    data["service_scope_exceptions"] = {
        "enc.cmk": "Provisional portfolio-level recommendation."
    }

    errors = _validate(data, tmp_path, "publication")

    assert any("TRUST_REVIEW_STATUS" in error for error in errors)
    assert any(
        "TRUST_PROVISIONAL_SCOPE_EXCEPTION" in error for error in errors
    )
