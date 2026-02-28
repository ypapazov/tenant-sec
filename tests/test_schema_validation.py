"""JSON Schema validation tests for all example files."""

from __future__ import annotations

from pathlib import Path

import pytest

from tenant_sec.core.loader import validate_file, load_yaml_file, _load_schema, _validate_yaml


REPO_ROOT = Path(__file__).parent.parent
SCHEMA_DIR = REPO_ROOT / "schema"
CONTROLS_DIR = REPO_ROOT / "controls"
PROVIDERS_DIR = REPO_ROOT / "providers"
PROFILES_DIR = REPO_ROOT / "profiles"
CATALOG_PATH = SCHEMA_DIR / "service-catalog.yaml"


# ── Schema files themselves must exist ───────────────────────────────────────

def test_schema_files_exist():
    for name in ["control.schema.json", "provider.schema.json",
                 "scoring-profile.schema.json", "maturity.schema.json"]:
        assert (SCHEMA_DIR / name).exists(), f"Schema file missing: {name}"


def test_service_catalog_exists():
    assert CATALOG_PATH.exists()


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
