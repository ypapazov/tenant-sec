"""Service catalog and registry tests."""

from __future__ import annotations

import pytest


class TestServiceCatalog:
    def test_catalog_loads(self, service_catalog):
        assert service_catalog is not None

    def test_resolve_known_alias(self, service_catalog):
        assert service_catalog.resolve("aws", "s3") == "storage.object"
        assert service_catalog.resolve("gcp", "cloud-storage") == "storage.object"
        assert service_catalog.resolve("scaleway", "object-storage") == "storage.object"

    def test_resolve_unknown_alias(self, service_catalog):
        assert service_catalog.resolve("aws", "completely-unknown-service") is None

    def test_resolve_unknown_provider(self, service_catalog):
        assert service_catalog.resolve("unknown-provider", "s3") is None

    def test_categories_not_empty(self, service_catalog):
        assert len(service_catalog.canonical_categories()) >= 10

    def test_aliases_for_aws(self, service_catalog):
        aliases = service_catalog.aliases_for_provider("aws")
        assert "s3" in aliases
        assert "ec2" in aliases
        assert "kms" in aliases


class TestControlRegistry:
    def test_registry_loads(self, control_registry):
        assert control_registry is not None

    def test_all_controls_present(self, control_registry):
        controls = control_registry.all_controls()
        assert len(controls) >= 50

    def test_get_existing_control(self, control_registry):
        c = control_registry.get("iam.abac")
        assert c is not None
        assert c.domain == "iam"
        assert c.name  # non-empty

    def test_get_nonexistent_control(self, control_registry):
        assert control_registry.get("iam.nonexistent") is None

    def test_by_domain(self, control_registry):
        iam_controls = control_registry.by_domain("iam")
        assert len(iam_controls) >= 5
        for c in iam_controls:
            assert c.domain == "iam"

    def test_all_domains_present(self, control_registry):
        expected_domains = {
            "iam", "governance", "encryption", "network",
            "logging", "data", "compute", "incident", "supply-chain"
        }
        actual_domains = set(control_registry.domains())
        assert expected_domains.issubset(actual_domains)

    def test_control_has_criteria(self, control_registry):
        c = control_registry.get("gov.preventive-policy")
        assert c is not None
        for level in ["L0", "L1", "L2", "L3"]:
            assert level in c.criteria
            assert len(c.criteria[level]) > 0

    def test_control_has_framework_mappings(self, control_registry):
        c = control_registry.get("iam.external-idp-federation")
        assert c is not None
        assert "ccm" in c.framework_mappings
        assert "nist_800_53_r5" in c.framework_mappings
