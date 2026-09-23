"""Coverage fractions and display bands (METHODOLOGY.md §5)."""

from __future__ import annotations

from datetime import date

from tenant_sec.core.models import (
    AssessmentStatus,
    LeafControlScore,
    MixedControlScore,
    ProviderProfile,
    ServiceInScope,
    ServiceScore,
)
from tenant_sec.scoring.coverage import (
    catalog_coverage,
    coverage_band,
    service_coverage,
)


def test_coverage_bands():
    assert coverage_band(0.0) == "none"
    assert coverage_band(0.39) == "low"
    assert coverage_band(0.40) == "medium"
    assert coverage_band(0.69) == "medium"
    assert coverage_band(0.70) == "high"
    assert coverage_band(0.89) == "high"
    assert coverage_band(0.90) == "full"
    assert coverage_band(1.0) == "full"
    assert coverage_band(None) is None


def _provider_with_cmk(services: list[str], scores: dict[str, int | None]) -> ProviderProfile:
    in_scope = [
        ServiceInScope(svc, svc.upper(), "storage.object") for svc in services
    ]
    mixed = MixedControlScore(
        services={
            svc: ServiceScore(score=score, evidence="x")
            for svc, score in scores.items()
        }
    )
    return ProviderProfile(
        provider="test",
        display_name="Test",
        assessed_by="self",
        assessed_at=date(2026, 1, 1),
        methodology_version="2.0",
        revision=1,
        services_in_scope=in_scope,
        controls={"enc.cmk": mixed},
    )


def test_service_coverage_medium_example():
    """4 of 8 applicable services at L2+ → 0.50, band medium."""
    services = [f"s{i}" for i in range(8)]
    scores = {
        "s0": 2,
        "s1": 3,
        "s2": 2,
        "s3": 2,
        "s4": 1,
        "s5": 0,
        "s6": 1,
        "s7": 0,
    }
    provider = _provider_with_cmk(services, scores)
    cov = service_coverage(provider, "enc.cmk", threshold=2)
    assert cov is not None
    assert cov.assessed == 4
    assert cov.applicable == 8
    assert cov.fraction == 0.5
    assert cov.band == "medium"


def test_service_coverage_excludes_not_applicable():
    services = ["s3", "rds", "ai"]
    scores = {"s3": 2, "rds": None, "ai": 0}
    provider = _provider_with_cmk(services, scores)
    cov = service_coverage(provider, "enc.cmk", threshold=2)
    assert cov is not None
    assert cov.applicable == 2  # rds excluded
    assert cov.assessed == 1
    assert cov.band == "medium"
    assert cov.state_counts["not_applicable"] == 1


def test_missing_mixed_services_stay_in_denominator():
    """In-scope services not listed in the mixed map are unknown, still applicable."""
    services = ["s3", "rds", "lambda", "ec2"]
    scores = {"s3": 3, "rds": 2}
    provider = _provider_with_cmk(services, scores)
    cov = service_coverage(provider, "enc.cmk", threshold=2)
    assert cov is not None
    assert cov.applicable == 4
    assert cov.assessed == 2
    assert cov.band == "medium"


def test_leaf_control_has_no_service_coverage():
    provider = ProviderProfile(
        provider="test",
        display_name="Test",
        assessed_by="self",
        assessed_at=date(2026, 1, 1),
        methodology_version="2.0",
        revision=1,
        services_in_scope=[ServiceInScope("s3", "S3", "storage.object")],
        controls={"iam.mfa-enforcement": LeafControlScore(score=3, evidence="x")},
    )
    assert service_coverage(provider, "iam.mfa-enforcement") is None


def test_catalog_coverage_keeps_missing_in_denominator(control_registry):
    provider = ProviderProfile(
        provider="test",
        display_name="Test",
        assessed_by="self",
        assessed_at=date(2026, 1, 1),
        methodology_version="2.0",
        revision=1,
        services_in_scope=[ServiceInScope("s3", "S3", "storage.object")],
        controls={"iam.mfa-enforcement": LeafControlScore(score=3, evidence="x")},
    )
    cov = catalog_coverage(provider, control_registry)
    tenant_count = sum(1 for c in control_registry.all_controls() if c.surface == "tenant")
    assert cov.applicable == tenant_count
    assert cov.assessed == 1
    assert cov.fraction is not None
    assert cov.fraction < 1.0


def test_unknown_null_service_remains_in_denominator():
    provider = _provider_with_cmk(["s3", "rds"], {"s3": 3, "rds": 0})
    provider.controls["enc.cmk"].services["rds"] = ServiceScore(
        score=None,
        evidence="research inconclusive",
        status=AssessmentStatus.UNKNOWN,
    )
    cov = service_coverage(provider, "enc.cmk", threshold=2)
    assert cov is not None
    assert cov.applicable == 2
    assert cov.assessed == 1
    assert cov.assessed_total == 1
    assert cov.completeness == 0.5
    assert cov.state_counts["unknown"] == 1


def test_out_of_scope_service_remains_visible():
    provider = _provider_with_cmk(["s3", "rds"], {"s3": 3, "rds": 0})
    provider.controls["enc.cmk"].services["rds"] = ServiceScore(
        score=None,
        evidence="intentionally omitted",
        status=AssessmentStatus.OUT_OF_SCOPE,
    )
    cov = service_coverage(provider, "enc.cmk", threshold=2)
    assert cov is not None
    assert cov.applicable == 2
    assert cov.state_counts["out_of_scope"] == 1


def test_not_applicable_control_is_excluded_but_out_of_scope_is_not(
    control_registry,
):
    provider = ProviderProfile(
        provider="test",
        display_name="Test",
        assessed_by="self",
        assessed_at=date(2026, 1, 1),
        methodology_version="2.0",
        revision=1,
        services_in_scope=[ServiceInScope("s3", "S3", "storage.object")],
        controls={
            "iam.mfa-enforcement": LeafControlScore(
                score=None,
                evidence="not meaningful",
                status=AssessmentStatus.NOT_APPLICABLE,
            ),
            "iam.session-management": LeafControlScore(
                score=None,
                evidence="not researched",
                status=AssessmentStatus.OUT_OF_SCOPE,
            ),
        },
    )
    cov = catalog_coverage(provider, control_registry)
    tenant_count = sum(
        1 for control in control_registry.all_controls() if control.surface == "tenant"
    )
    assert cov.applicable == tenant_count - 1
    assert cov.state_counts["not_applicable"] == 1
    assert cov.state_counts["out_of_scope"] == 1


def test_all_not_applicable_mixed_control_leaves_denominator(control_registry):
    provider = _provider_with_cmk(["s3", "rds"], {"s3": None, "rds": None})
    for service in provider.controls["enc.cmk"].services.values():
        service.status = AssessmentStatus.NOT_APPLICABLE
    cov = catalog_coverage(provider, control_registry)
    tenant_count = sum(
        1 for control in control_registry.all_controls() if control.surface == "tenant"
    )
    assert cov.applicable == tenant_count - 1
    assert cov.state_counts["not_applicable"] == 1
