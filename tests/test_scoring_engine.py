"""Scoring engine unit tests."""

from __future__ import annotations

from datetime import date

import pytest

from tenant_sec.core.models import (
    LeafControlScore,
    MixedControlScore,
    MustHaveEntry,
    ProviderProfile,
    ScoringProfile,
    ServiceInScope,
    ServiceScore,
)
from tenant_sec.scoring.engine import ScoringEngine
from tenant_sec.scoring.aggregation import get_aggregation_fn


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
