"""Assessment identity selection for multi-offering providers."""

from datetime import date
from pathlib import Path

import pytest
from click import ClickException

from tenant_sec.cli._providers import select_assessments, select_one_assessment
from tenant_sec.core.models import ProviderProfile


def _profile(assessment_id: str) -> ProviderProfile:
    return ProviderProfile(
        provider="aws",
        display_name=assessment_id,
        assessed_by="self",
        assessed_at=date(2026, 9, 16),
        methodology_version="2.0",
        revision=1,
        services_in_scope=[],
        controls={},
        assessment_id=assessment_id,
    )


def test_slug_selects_all_offerings_without_collapsing():
    candidates = [
        (Path("aws.yaml"), _profile("aws/commercial/eu/standard")),
        (Path("aws-esc.yaml"), _profile("aws/esc/eu/standard")),
    ]
    selected = select_assessments(candidates, ["aws"])
    assert [profile.identity for profile in selected] == [
        "aws/commercial/eu/standard",
        "aws/esc/eu/standard",
    ]


def test_singular_commands_reject_ambiguous_slug():
    candidates = [
        (Path("aws.yaml"), _profile("aws/commercial/eu/standard")),
        (Path("aws-esc.yaml"), _profile("aws/esc/eu/standard")),
    ]
    with pytest.raises(ClickException, match="ambiguous"):
        select_one_assessment(candidates, "aws")
    assert (
        select_one_assessment(candidates, "aws/esc/eu/standard").identity
        == "aws/esc/eu/standard"
    )
