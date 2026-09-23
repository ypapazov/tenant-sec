"""Shared test fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml


# Root of the repository (parent of tests/)
REPO_ROOT = Path(__file__).parent.parent

SCHEMA_DIR = REPO_ROOT / "schema"
CONTROLS_DIR = REPO_ROOT / "controls"
PROVIDERS_DIR = REPO_ROOT / "providers"
PROFILES_DIR = REPO_ROOT / "profiles"
MAPPINGS_DIR = REPO_ROOT / "mappings"
CATALOG_PATH = SCHEMA_DIR / "service-catalog.yaml"
CERTIFICATION_CATALOG_PATH = SCHEMA_DIR / "certification-catalog.yaml"


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture(scope="session")
def schema_dir() -> Path:
    return SCHEMA_DIR


@pytest.fixture(scope="session")
def controls_dir() -> Path:
    return CONTROLS_DIR


@pytest.fixture(scope="session")
def providers_dir() -> Path:
    return PROVIDERS_DIR


@pytest.fixture(scope="session")
def profiles_dir() -> Path:
    return PROFILES_DIR


@pytest.fixture(scope="session")
def catalog_path() -> Path:
    return CATALOG_PATH


@pytest.fixture(scope="session")
def control_registry(controls_dir):
    from tenant_sec.core.registry import ControlRegistry
    return ControlRegistry.from_directory(controls_dir)


@pytest.fixture(scope="session")
def service_catalog(catalog_path):
    from tenant_sec.core.registry import ServiceCatalog
    return ServiceCatalog.from_file(catalog_path)


@pytest.fixture(scope="session")
def certification_catalog():
    from tenant_sec.core.certifications import CertificationCatalog

    return CertificationCatalog.from_file(CERTIFICATION_CATALOG_PATH)


@pytest.fixture(scope="session")
def scaleway_profile(providers_dir, schema_dir):
    from tenant_sec.core.loader import load_provider
    return load_provider(providers_dir / "scaleway.yaml", schema_dir)


@pytest.fixture(scope="session")
def aws_profile(providers_dir, schema_dir):
    from tenant_sec.core.loader import load_provider
    return load_provider(providers_dir / "aws.yaml", schema_dir)


@pytest.fixture(scope="session")
def gcp_profile(providers_dir, schema_dir):
    from tenant_sec.core.loader import load_provider
    return load_provider(providers_dir / "gcp.yaml", schema_dir)


@pytest.fixture(scope="session")
def eu_fintech_scoring(profiles_dir, schema_dir):
    from tenant_sec.core.loader import load_scoring_profile
    return load_scoring_profile(profiles_dir / "eu-regulated-fintech.yaml", schema_dir)


@pytest.fixture(scope="session")
def general_scoring(profiles_dir, schema_dir):
    from tenant_sec.core.loader import load_scoring_profile
    return load_scoring_profile(profiles_dir / "general-enterprise.yaml", schema_dir)
