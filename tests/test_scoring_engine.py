"""Scoring engine unit tests."""

from __future__ import annotations

from datetime import date

import pytest

from tenant_sec.core.models import (
    AssessmentStatus,
    CertificationRecord,
    Control,
    LeafControlScore,
    MixedControlScore,
    MustHaveEntry,
    ProviderProfile,
    ProviderOffering,
    ScoringProfile,
    ServiceInScope,
    ServiceScore,
)
from tenant_sec.scoring.engine import ScoringEngine
from tenant_sec.scoring.aggregation import get_aggregation_fn
from tenant_sec.core.registry import ControlRegistry


# ── Aggregation function tests ────────────────────────────────────────────────

class TestAggregationFunctions:
    def test_min(self):
        fn = get_aggregation_fn("min")
        assert fn([3, 2, 1]) == 1.0
        assert fn([3, 3, 3]) == 3.0

    def test_mean(self):
        fn = get_aggregation_fn("mean")
        assert fn([0, 2, 3]) == pytest.approx(5 / 3)

    def test_median(self):
        fn = get_aggregation_fn("median")
        assert fn([0, 2, 3]) == 2.0
        assert fn([0, 3]) == pytest.approx(1.5)

    def test_p10(self):
        fn = get_aggregation_fn("p10")
        # 10th percentile of [0,1,2,3] should be close to 0.3
        result = fn([0, 1, 2, 3])
        assert 0.0 <= result <= 1.0

    def test_p20(self):
        fn = get_aggregation_fn("p20")
        result = fn([0, 1, 2, 3])
        assert 0.0 <= result <= 1.0

    def test_threshold_pass(self):
        fn = get_aggregation_fn("threshold:L2:0.8")
        # 4/5 = 80% at L2 or above → passes
        assert fn([2, 2, 2, 2, 0]) == 2.0

    def test_threshold_fail(self):
        fn = get_aggregation_fn("threshold:L2:0.8")
        # 3/5 = 60% < 80% → fails, returns L1
        assert fn([2, 2, 2, 0, 0]) == 1.0

    def test_null_excluded(self):
        fn = get_aggregation_fn("min")
        assert fn([3, None, 2]) == 2.0

    def test_all_null(self):
        fn = get_aggregation_fn("mean")
        assert fn([None, None]) is None

    def test_unknown_spec_raises(self):
        with pytest.raises(ValueError):
            get_aggregation_fn("invalid-spec")


# ── Scoring engine integration tests ─────────────────────────────────────────

def _make_provider(slug: str, controls: dict, services=None) -> ProviderProfile:
    services = services or [ServiceInScope("s3", "S3", "storage.object")]
    return ProviderProfile(
        provider=slug,
        display_name=slug.upper(),
        assessed_by="self",
        assessed_at=date(2026, 1, 1),
        methodology_version="1.0",
        revision=1,
        services_in_scope=services,
        controls=controls,
    )


def _make_scoring_profile(
    must_have=None,
    mixed_aggregation="min",
    weights=None,
) -> ScoringProfile:
    if weights is None:
        weights = {"iam": 1.0}
    return ScoringProfile(
        name="test",
        weights=weights,
        mixed_aggregation=mixed_aggregation,
        must_have=must_have or [],
    )


class TestScoringEngine:
    def test_leaf_score_passthrough(self, control_registry):
        provider = _make_provider(
            "test",
            {"iam.abac": LeafControlScore(score=3, evidence="full ABAC")},
        )
        profile = _make_scoring_profile(weights={"iam": 1.0})
        engine = ScoringEngine(control_registry)
        results = engine.score([provider], profile)
        assert len(results) == 1
        assert results[0].effective_scores["iam.abac"] == 3.0

    def test_mixed_score_aggregation_min(self, control_registry):
        provider = _make_provider(
            "test",
            {
                "enc.cmk": MixedControlScore(
                    services={
                        "s3": ServiceScore(score=3, evidence="full"),
                        "rds": ServiceScore(score=0, evidence="none"),
                    }
                )
            },
            services=[
                ServiceInScope("s3", "S3", "storage.object"),
                ServiceInScope("rds", "RDS", "database.relational"),
            ],
        )
        profile = _make_scoring_profile(
            mixed_aggregation="min",
            weights={"encryption": 1.0},
        )
        engine = ScoringEngine(control_registry)
        results = engine.score([provider], profile)
        assert results[0].effective_scores["enc.cmk"] == 0.0

    def test_must_have_pass(self, control_registry):
        provider = _make_provider(
            "test",
            {"iam.abac": LeafControlScore(score=3, evidence="full")},
        )
        profile = _make_scoring_profile(
            must_have=[MustHaveEntry(control="iam.abac", min_level=2)],
            weights={"iam": 1.0},
        )
        engine = ScoringEngine(control_registry)
        results = engine.score([provider], profile)
        assert results[0].must_have_passed is True
        assert results[0].must_have_results[0].passed is True

    def test_must_have_fail_unassessed(self, control_registry):
        provider = _make_provider("test", {})
        profile = _make_scoring_profile(
            must_have=[MustHaveEntry(control="iam.abac", min_level=2)],
            weights={"iam": 1.0},
        )
        engine = ScoringEngine(control_registry)
        results = engine.score([provider], profile)
        assert results[0].must_have_passed is False

    def test_must_have_fail_below_threshold(self, control_registry):
        provider = _make_provider(
            "test",
            {"iam.abac": LeafControlScore(score=1, evidence="limited")},
        )
        profile = _make_scoring_profile(
            must_have=[MustHaveEntry(control="iam.abac", min_level=2)],
            weights={"iam": 1.0},
        )
        engine = ScoringEngine(control_registry)
        results = engine.score([provider], profile)
        assert results[0].must_have_passed is False

    def test_ranking_order(self, control_registry):
        high = _make_provider(
            "high",
            {"iam.abac": LeafControlScore(score=3, evidence="x")},
        )
        low = _make_provider(
            "low",
            {"iam.abac": LeafControlScore(score=1, evidence="x")},
        )
        profile = _make_scoring_profile(weights={"iam": 1.0})
        engine = ScoringEngine(control_registry)
        results = engine.score([low, high], profile)
        assert results[0].provider == "high"
        assert results[1].provider == "low"
        assert results[0].rank == 1
        assert results[1].rank == 2

    def test_must_have_failure_is_eligibility_gate(self, control_registry):
        """A higher heuristic score does not outrank a must-have failure."""
        high_but_ineligible = _make_provider(
            "high",
            {"iam.abac": LeafControlScore(score=3, evidence="x")},
        )
        low_but_eligible = _make_provider(
            "low",
            {"iam.abac": LeafControlScore(score=2, evidence="x")},
        )
        profile = _make_scoring_profile(
            must_have=[MustHaveEntry(control="iam.abac", min_level=2)],
            weights={"iam": 0.5, "encryption": 0.5},
        )
        # high has the score but we strip the must-have control to fail eligibility
        high_but_ineligible.controls = {
            "enc.cmk": LeafControlScore(score=3, evidence="unrelated"),
        }
        engine = ScoringEngine(control_registry)
        results = engine.score([high_but_ineligible, low_but_eligible], profile)
        assert results[0].provider == "low"
        assert results[0].eligible is True
        assert results[0].rank == 1
        assert results[1].provider == "high"
        assert results[1].eligible is False
        assert results[1].rank == 0

    def test_required_certification_gates_eligibility(
        self, control_registry, certification_catalog
    ):
        with_cert = _make_provider(
            "held",
            {"iam.abac": LeafControlScore(score=1, evidence="x")},
        )
        with_cert.certifications = [
            CertificationRecord(id="bsi-c5-type2", status="held", valid_until=date(2027, 1, 1)),
        ]
        without_cert = _make_provider(
            "missing",
            {"iam.abac": LeafControlScore(score=3, evidence="x")},
        )
        profile = _make_scoring_profile(weights={"iam": 1.0})
        profile.must_have_certifications = ["bsi-c5-type2"]
        engine = ScoringEngine(
            control_registry,
            reference_date=date(2026, 9, 16),
            certification_catalog=certification_catalog,
        )
        results = engine.score([without_cert, with_cert], profile)
        assert results[0].provider == "held"
        assert results[0].eligible is True
        assert results[0].certs_passed is True
        assert results[1].provider == "missing"
        assert results[1].eligible is False
        assert results[1].certs_passed is False

    def test_expired_certification_fails(
        self, control_registry, certification_catalog
    ):
        expired = _make_provider(
            "expired",
            {"iam.abac": LeafControlScore(score=3, evidence="x")},
        )
        expired.certifications = [
            CertificationRecord(id="iso-27001", status="held", valid_until=date(2025, 1, 1)),
        ]
        profile = _make_scoring_profile(weights={"iam": 1.0})
        profile.must_have_certifications = ["iso-27001"]
        engine = ScoringEngine(
            control_registry,
            reference_date=date(2026, 9, 16),
            certification_catalog=certification_catalog,
        )
        results = engine.score([expired], profile)
        assert results[0].eligible is False
        assert results[0].cert_results[0].held is True
        assert results[0].cert_results[0].current is False

    def test_unknown_numeric_result_never_passes_must_have(self, control_registry):
        provider = _make_provider(
            "unknown",
            {
                "iam.abac": LeafControlScore(
                    score=3,
                    evidence="insufficient evidence",
                    status=AssessmentStatus.UNKNOWN,
                )
            },
        )
        profile = _make_scoring_profile(
            must_have=[MustHaveEntry(control="iam.abac", min_level=3)],
            weights={"iam": 1.0},
        )
        result = ScoringEngine(control_registry).score([provider], profile)[0]
        assert result.effective_scores["iam.abac"] is None
        assert result.must_have_passed is False
        assert result.eligible is False

    def test_scheme_draft_cannot_satisfy_requirement(
        self, control_registry, certification_catalog
    ):
        provider = _make_provider(
            "draft",
            {"iam.abac": LeafControlScore(score=3, evidence="x")},
        )
        provider.certifications = [
            CertificationRecord(
                id="eucs",
                status="held",
                validity="continuous",
            )
        ]
        profile = _make_scoring_profile(weights={"iam": 1.0})
        profile.must_have_certifications = ["eucs"]
        result = ScoringEngine(
            control_registry,
            reference_date=date(2026, 9, 16),
            certification_catalog=certification_catalog,
        ).score([provider], profile)[0]
        assert result.eligible is False
        assert result.cert_results[0].reason == "programme cannot be held"

    @pytest.mark.parametrize(
        ("offering", "valid_from", "expected_reason"),
        [
            ("other-offering", date(2026, 1, 1), "different or unspecified offering"),
            ("public", date(2027, 1, 1), "validity has not started"),
        ],
    )
    def test_certification_scope_and_start_date_fail_closed(
        self,
        control_registry,
        certification_catalog,
        offering,
        valid_from,
        expected_reason,
    ):
        provider = _make_provider(
            "scoped",
            {"iam.abac": LeafControlScore(score=3, evidence="x")},
        )
        provider.methodology_version = "2.0"
        provider.assessment_id = "scoped/public/eu/standard"
        provider.offering = ProviderOffering(
            id="public",
            name="Public",
            partition="commercial",
            regions=["eu-1"],
            edition="standard",
            cohort="eu-public",
        )
        provider.certifications = [
            CertificationRecord(
                id="iso-27001",
                status="held",
                validity="fixed",
                valid_from=valid_from,
                valid_until=date(2028, 1, 1),
                offering=offering,
                regions=["eu-1"],
            )
        ]
        profile = _make_scoring_profile(weights={"iam": 1.0})
        profile.must_have_certifications = ["iso-27001"]
        result = ScoringEngine(
            control_registry,
            reference_date=date(2026, 9, 16),
            certification_catalog=certification_catalog,
        ).score([provider], profile)[0]
        assert result.eligible is False
        assert expected_reason in result.cert_results[0].reason

    def test_v2_certification_requires_explicit_service_scope(
        self, control_registry, certification_catalog
    ):
        provider = _make_provider(
            "scoped",
            {"iam.abac": LeafControlScore(score=3, evidence="x")},
        )
        provider.methodology_version = "2.0"
        provider.assessment_id = "scoped/public/eu/standard"
        provider.offering = ProviderOffering(
            id="public",
            name="Public",
            partition="commercial",
            regions=["eu-1"],
            edition="standard",
            cohort="eu-public",
        )
        record = CertificationRecord(
            id="iso-27001",
            status="held",
            validity="fixed",
            valid_until=date(2028, 1, 1),
            offering="public",
            regions=["eu-1"],
        )
        provider.certifications = [record]
        profile = _make_scoring_profile(weights={"iam": 1.0})
        profile.cohort = "eu-public"
        profile.must_have_certifications = ["iso-27001"]
        engine = ScoringEngine(
            control_registry,
            reference_date=date(2026, 9, 16),
            certification_catalog=certification_catalog,
        )
        result = engine.score([provider], profile)[0]
        assert result.certs_passed is False
        assert "service scope is unspecified" in result.cert_results[0].reason

        record.all_services = True
        result = engine.score([provider], profile)[0]
        assert result.certs_passed is True

    def test_vignette_surface_never_scores(self):
        registry = ControlRegistry(
            [
                Control(
                    id="supply-chain.provider-fact",
                    domain="supply-chain",
                    name="Provider fact",
                    description="Not tenant operable",
                    criteria={},
                    framework_mappings={},
                    surface="vignette",
                ),
                Control(
                    id="iam.abac",
                    domain="iam",
                    name="ABAC",
                    description="Tenant control",
                    criteria={},
                    framework_mappings={},
                ),
            ]
        )
        provider = _make_provider(
            "test",
            {
                "supply-chain.provider-fact": LeafControlScore(
                    score=3, evidence="x"
                ),
                "iam.abac": LeafControlScore(score=0, evidence="x"),
            },
        )
        profile = _make_scoring_profile(
            weights={"iam": 1.0, "supply-chain": 0.0}
        )
        result = ScoringEngine(registry).score([provider], profile)[0]
        assert "supply-chain.provider-fact" not in result.effective_scores
        assert result.domain_scores["supply-chain"] is None
        assert result.overall_score == 0.0

        invalid_profile = _make_scoring_profile(
            weights={"iam": 0.5, "supply-chain": 0.5}
        )
        with pytest.raises(ValueError, match="without tenant controls"):
            ScoringEngine(registry).score([provider], invalid_profile)

    def test_extra_mixed_service_never_affects_maturity(self, control_registry):
        provider = _make_provider(
            "test",
            {
                "enc.cmk": MixedControlScore(
                    services={
                        "s3": ServiceScore(score=0, evidence="in scope"),
                        "not-in-scope": ServiceScore(
                            score=3, evidence="must be ignored"
                        ),
                    }
                )
            },
        )
        profile = _make_scoring_profile(
            mixed_aggregation="mean",
            weights={"encryption": 1.0},
        )
        result = ScoringEngine(control_registry).score([provider], profile)[0]
        assert result.effective_scores["enc.cmk"] == 0.0

    def test_service_scoped_leaf_is_not_publishable_without_exception(
        self, control_registry
    ):
        provider = _make_provider(
            "test",
            {"enc.cmk": LeafControlScore(score=3, evidence="offering-wide")},
        )
        provider.methodology_version = "2.0"
        provider.assessment_id = "test/public/eu/standard"
        provider.offering = ProviderOffering(
            id="public",
            name="Public",
            partition="commercial",
            regions=["eu-1"],
            edition="standard",
            cohort="eu-public",
        )
        profile = _make_scoring_profile(weights={"encryption": 1.0})
        profile.cohort = "eu-public"
        result = ScoringEngine(control_registry).score([provider], profile)[0]
        assert result.publishable is False
        assert any(
            "service-scoped controls require mixed results" in reason
            for reason in result.publication_reasons
        )
        assert result.catalog_coverage.completeness < 1.0
        assessed_without_exception = result.catalog_coverage.assessed

        provider.service_scope_exceptions = {
            "enc.cmk": "The API is offering-wide and identical for all listed services."
        }
        result = ScoringEngine(control_registry).score([provider], profile)[0]
        assert result.catalog_coverage.assessed == assessed_without_exception + 1
        assert not any(
            "service-scoped controls require mixed results" in reason
            for reason in result.publication_reasons
        )

    def test_profile_cohort_is_an_eligibility_gate(self, control_registry):
        provider = _make_provider(
            "test",
            {"iam.abac": LeafControlScore(score=3, evidence="x")},
        )
        provider.offering = ProviderOffering(
            id="public",
            name="Public",
            partition="commercial",
            regions=["eu-1"],
            edition="standard",
            cohort="eu-public",
        )
        profile = _make_scoring_profile(weights={"iam": 1.0})
        profile.cohort = "sovereign"
        result = ScoringEngine(control_registry).score([provider], profile)[0]
        assert result.eligible is False
        assert any(
            "outside the profile cohort" in reason
            for reason in result.eligibility_reasons
        )

    def test_v2_ranking_requires_explicit_profile_cohort(self, control_registry):
        provider = _make_provider(
            "test",
            {"iam.abac": LeafControlScore(score=3, evidence="x")},
        )
        provider.methodology_version = "2.0"
        provider.offering = ProviderOffering(
            id="public",
            name="Public",
            partition="commercial",
            regions=["eu-1"],
            edition="standard",
            cohort="eu-public",
        )
        profile = _make_scoring_profile(weights={"iam": 1.0})
        result = ScoringEngine(control_registry).score([provider], profile)[0]
        assert result.eligible is False
        assert any(
            "requires an explicit profile cohort" in reason
            for reason in result.eligibility_reasons
        )

    def test_min_catalog_coverage_gate(self, control_registry):
        sparse = _make_provider(
            "sparse",
            {"iam.abac": LeafControlScore(score=3, evidence="x")},
        )
        profile = _make_scoring_profile(weights={"iam": 1.0})
        profile.min_catalog_coverage = 0.9
        engine = ScoringEngine(control_registry)
        results = engine.score([sparse], profile)
        assert results[0].eligible is False
        assert results[0].catalog_coverage is not None
        assert results[0].catalog_coverage.fraction < 0.9

    def test_overall_score_normalized_0_100(self, control_registry):
        provider = _make_provider(
            "test",
            {"iam.abac": LeafControlScore(score=3, evidence="x")},
        )
        profile = _make_scoring_profile(weights={"iam": 1.0})
        engine = ScoringEngine(control_registry)
        results = engine.score([provider], profile)
        assert 0 <= results[0].overall_score <= 100

    def test_empty_provider(self, control_registry):
        provider = _make_provider("empty", {})
        profile = _make_scoring_profile(weights={"iam": 1.0})
        engine = ScoringEngine(control_registry)
        results = engine.score([provider], profile)
        assert len(results) == 1
        assert results[0].overall_score == 0.0

    def test_null_services_excluded_from_aggregation(self, control_registry):
        provider = _make_provider(
            "test",
            {
                "enc.cmk": MixedControlScore(
                    services={
                        "s3": ServiceScore(score=3, evidence="full"),
                        "rds": ServiceScore(score=None, evidence="not applicable"),
                    }
                )
            },
        )
        profile = _make_scoring_profile(
            mixed_aggregation="min",
            weights={"encryption": 1.0},
        )
        engine = ScoringEngine(control_registry)
        results = engine.score([provider], profile)
        # Min of [3] (null excluded) = 3
        assert results[0].effective_scores["enc.cmk"] == 3.0


# ── Full pipeline test against real data ─────────────────────────────────────

class TestFullPipeline:
    def test_score_scaleway_vs_aws(
        self,
        control_registry,
        scaleway_profile,
        aws_profile,
        eu_fintech_scoring,
    ):
        engine = ScoringEngine(control_registry)
        results = engine.score(
            [scaleway_profile, aws_profile], eu_fintech_scoring
        )
        assert len(results) == 2
        # AWS should score higher than Scaleway
        assert results[0].overall_score > results[1].overall_score
        # Both should have valid scores
        for r in results:
            assert 0 <= r.overall_score <= 100

    def test_aws_must_haves_pass(
        self,
        control_registry,
        aws_profile,
        eu_fintech_scoring,
    ):
        engine = ScoringEngine(control_registry)
        results = engine.score([aws_profile], eu_fintech_scoring)
        # AWS should pass all EU fintech must-haves
        assert results[0].must_have_passed is True

    def test_domain_scores_present(
        self,
        control_registry,
        aws_profile,
        general_scoring,
    ):
        engine = ScoringEngine(control_registry)
        results = engine.score([aws_profile], general_scoring)
        r = results[0]
        for domain in general_scoring.weights:
            assert domain in r.domain_scores
