"""CLI smoke tests — commands run without error against real data."""

from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

from tenant_sec.cli.main import cli


REPO_ROOT = Path(__file__).parent.parent


@pytest.fixture
def runner():
    return CliRunner()


def _invoke(runner, *args):
    result = runner.invoke(cli, ["--data-dir", str(REPO_ROOT)] + list(args))
    return result


class TestValidateCommand:
    def test_validate_scaleway_provider(self, runner):
        result = _invoke(
            runner, "validate", str(REPO_ROOT / "providers" / "scaleway.yaml")
        )
        assert result.exit_code == 0, result.output
        assert "valid" in result.output.lower()

    def test_validate_aws_provider(self, runner):
        result = _invoke(
            runner, "validate", str(REPO_ROOT / "providers" / "aws.yaml")
        )
        assert result.exit_code == 0, result.output

    def test_validate_scoring_profile(self, runner):
        result = _invoke(
            runner,
            "validate",
            str(REPO_ROOT / "profiles" / "eu-regulated-fintech.yaml"),
            "--type",
            "scoring-profile",
        )
        assert result.exit_code == 0, result.output

    def test_validate_control_file(self, runner):
        result = _invoke(
            runner,
            "validate",
            str(REPO_ROOT / "controls" / "iam" / "abac.yaml"),
            "--type",
            "control",
        )
        assert result.exit_code == 0, result.output

    def test_validate_help(self, runner):
        result = _invoke(runner, "validate", "--help")
        assert result.exit_code == 0
        assert "PATH" in result.output


class TestScoreCommand:
    def test_score_table_output(self, runner):
        result = _invoke(
            runner,
            "score",
            "--profile",
            str(REPO_ROOT / "profiles" / "eu-regulated-fintech.yaml"),
            "--providers",
            "aws,gcp,scaleway",
        )
        assert result.exit_code == 0, result.output
        assert "AWS" in result.output or "Amazon" in result.output

    def test_score_json_output(self, runner):
        import json

        result = _invoke(
            runner,
            "score",
            "--profile",
            str(REPO_ROOT / "profiles" / "general-enterprise.yaml"),
            "--providers",
            "aws",
            "--format",
            "json",
        )
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert len(data) == 1
        assert "overall_score" in data[0]
        assert 0 <= data[0]["overall_score"] <= 100
        assert data[0]["score_kind"] == "heuristic_index"
        assert "assessment_id" in data[0]
        assert "catalog_completeness" in data[0]
        assert "service_coverages" in data[0]

    def test_score_csv_output(self, runner):
        result = _invoke(
            runner,
            "score",
            "--profile",
            str(REPO_ROOT / "profiles" / "general-enterprise.yaml"),
            "--providers",
            "scaleway",
            "--format",
            "csv",
        )
        assert result.exit_code == 0, result.output
        assert "overall_score" in result.output
        assert "assessment_id" in result.output
        assert "offering_id" in result.output
        assert "cohort" in result.output

    def test_score_help(self, runner):
        result = _invoke(runner, "score", "--help")
        assert result.exit_code == 0


class TestDetailCommand:
    def test_detail_scaleway(self, runner):
        result = _invoke(runner, "detail", "--provider", "scaleway")
        assert result.exit_code == 0, result.output
        assert "Scaleway" in result.output

    def test_detail_with_domain_filter(self, runner):
        result = _invoke(runner, "detail", "--provider", "aws", "--domain", "iam")
        assert result.exit_code == 0, result.output
        assert "IAM" in result.output

    def test_detail_help(self, runner):
        result = _invoke(runner, "detail", "--help")
        assert result.exit_code == 0


class TestCompareCommand:
    def test_compare_two_providers(self, runner):
        result = _invoke(
            runner, "compare", "--providers", "aws,gcp", "--domain", "iam"
        )
        assert result.exit_code == 0, result.output
        assert "IAM" in result.output

    def test_compare_three_providers(self, runner):
        result = _invoke(
            runner, "compare", "--providers", "aws,gcp,azure"
        )
        assert result.exit_code == 0, result.output

    def test_compare_help(self, runner):
        result = _invoke(runner, "compare", "--help")
        assert result.exit_code == 0


class TestExportCommand:
    def test_export_json(self, runner):
        import json

        result = _invoke(
            runner, "export", "--provider", "scaleway", "--format", "json"
        )
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["provider"] == "scaleway"
        assert "controls" in data

    def test_export_csv(self, runner):
        result = _invoke(
            runner, "export", "--provider", "aws", "--format", "csv"
        )
        assert result.exit_code == 0, result.output
        assert "control_id" in result.output
        assert "assessment_id" in result.output
        assert "offering_id" in result.output
        assert "certifications_json" in result.output
        assert "vignette_json" in result.output

    def test_export_html(self, runner):
        result = _invoke(
            runner, "export", "--provider", "aws", "--format", "html"
        )
        assert result.exit_code == 0, result.output
        assert "<!DOCTYPE html>" in result.output
        assert "Amazon Web Services" in result.output

    def test_export_help(self, runner):
        result = _invoke(runner, "export", "--help")
        assert result.exit_code == 0


class TestRootCommands:
    def test_help(self, runner):
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "tenant-sec" in result.output.lower()

    def test_version(self, runner):
        result = runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert "0.1.0" in result.output
