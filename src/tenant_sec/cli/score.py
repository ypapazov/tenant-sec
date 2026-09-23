"""tenant-sec score command."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import click
from tabulate import tabulate

from ..core.loader import (
    load_certification_catalog,
    load_control_registry,
    load_scoring_profile,
)
from ..scoring.engine import ScoringEngine
from ._providers import load_all_assessments, select_assessments


def _level_symbol(score: Optional[float]) -> str:
    if score is None:
        return "—"
    return f"L{int(round(score))}"


def _coverage_to_dict(coverage) -> dict | None:
    if coverage is None:
        return None
    return {
        "meeting_threshold": coverage.assessed,
        "assessed_total": coverage.assessed_total,
        "applicable": coverage.applicable,
        "fraction": coverage.fraction,
        "completeness": coverage.completeness,
        "band": coverage.band,
        "threshold": coverage.threshold,
        "state_counts": coverage.state_counts,
    }


@click.command()
@click.option(
    "--profile",
    "profile_path",
    required=True,
    type=click.Path(exists=True, path_type=Path),
    help="Path to a scoring profile YAML file.",
)
@click.option(
    "--providers",
    default=None,
    help="Comma-separated slugs, profile stems, or assessment IDs. Defaults to all.",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["table", "json", "csv"]),
    default="table",
    help="Output format.",
)
@click.pass_context
def score(
    ctx: click.Context,
    profile_path: Path,
    providers: Optional[str],
    output_format: str,
) -> None:
    """Score and rank cloud providers against a scoring profile.

    Example:

      tenant-sec score --profile profiles/eu-regulated-fintech.yaml
    """
    from .main import get_data_dir

    data_dir = get_data_dir(ctx)
    schema_dir = data_dir / "schema"
    providers_dir = data_dir / "providers"
    controls_dir = data_dir / "controls"

    # Load scoring profile
    scoring_profile = load_scoring_profile(profile_path, schema_dir)

    candidates = load_all_assessments(providers_dir, schema_dir)
    if not candidates:
        raise click.ClickException("No provider profiles found.")
    loaded_providers = (
        select_assessments(
            candidates,
            [provider.strip() for provider in providers.split(",")],
        )
        if providers
        else [profile for _, profile in candidates]
    )

    # Load registry
    registry = load_control_registry(controls_dir)
    certification_catalog = load_certification_catalog(
        schema_dir / "certification-catalog.yaml"
    )
    engine = ScoringEngine(
        registry,
        certification_catalog=certification_catalog,
    )

    results = engine.score(loaded_providers, scoring_profile)

    # Output
    if output_format == "json":
        output = []
        for r in results:
            output.append(
                {
                    "rank": r.rank,
                    "provider": r.provider,
                    "assessment_id": r.assessment_id,
                    "offering_id": r.offering_id,
                    "cohort": r.cohort,
                    "display_name": r.display_name,
                    "score_kind": "heuristic_index",
                    "aggregation": scoring_profile.mixed_aggregation,
                    "overall_score": r.overall_score,
                    "domain_scores": r.domain_scores,
                    "must_have_passed": r.must_have_passed,
                    "must_have_results": [
                        {
                            "control": mh.control,
                            "min_level": mh.min_level,
                            "actual_level": mh.actual_level,
                            "passed": mh.passed,
                        }
                        for mh in r.must_have_results
                    ],
                    "eligible": r.eligible,
                    "eligibility_reasons": r.eligibility_reasons,
                    "publishable": r.publishable,
                    "publication_reasons": r.publication_reasons,
                    "certs_passed": r.certs_passed,
                    "cert_results": [
                        {
                            "certification_id": c.certification_id,
                            "held": c.held,
                            "current": c.current,
                            "passed": c.passed,
                            "valid_until": c.valid_until,
                            "scope_matches": c.scope_matches,
                            "reason": c.reason,
                        }
                        for c in r.cert_results
                    ],
                    "catalog_completeness": _coverage_to_dict(
                        r.catalog_coverage
                    ),
                    "service_coverages": {
                        control_id: {
                            f"L{threshold}": _coverage_to_dict(coverage)
                            for threshold, coverage in thresholds.items()
                        }
                        for control_id, thresholds in r.service_coverages.items()
                    },
                    "stale": r.stale,
                }
            )
        click.echo(json.dumps(output, indent=2))

    elif output_format == "csv":
        import csv
        import io

        buf = io.StringIO()
        domains = sorted(scoring_profile.weights.keys())
        fieldnames = [
            "rank",
            "provider",
            "assessment_id",
            "offering_id",
            "cohort",
            "overall_score",
            "eligible",
            "eligibility_reasons",
            "publishable",
            "must_have_passed",
            "certs_passed",
            "catalog_completeness",
            "service_coverages",
            "stale",
        ] + [
            f"domain_{d}" for d in domains
        ]
        writer = csv.DictWriter(buf, fieldnames=fieldnames)
        writer.writeheader()
        for r in results:
            row = {
                "rank": r.rank if r.rank else "",
                "provider": r.provider,
                "assessment_id": r.assessment_id,
                "offering_id": r.offering_id or "",
                "cohort": r.cohort or "",
                "overall_score": r.overall_score,
                "eligible": r.eligible,
                "eligibility_reasons": "; ".join(r.eligibility_reasons),
                "publishable": r.publishable,
                "must_have_passed": r.must_have_passed,
                "certs_passed": r.certs_passed,
                "catalog_completeness": (
                    ""
                    if r.catalog_coverage is None
                    or r.catalog_coverage.completeness is None
                    else f"{r.catalog_coverage.completeness:.2f}"
                ),
                "service_coverages": json.dumps(
                    {
                        control_id: {
                            f"L{threshold}": _coverage_to_dict(coverage)
                            for threshold, coverage in thresholds.items()
                        }
                        for control_id, thresholds in r.service_coverages.items()
                    },
                    separators=(",", ":"),
                ),
                "stale": r.stale,
            }
            for d in domains:
                row[f"domain_{d}"] = r.domain_scores.get(d, "")
            writer.writerow(row)
        click.echo(buf.getvalue())

    else:  # table
        domains = sorted(scoring_profile.weights.keys())
        # Abbreviated domain names for table columns
        domain_abbrev = {
            "iam": "IAM",
            "governance": "Gov",
            "encryption": "Enc",
            "network": "Net",
            "logging": "Log",
            "data": "Data",
            "compute": "Cmp",
            "incident": "Inc",
            "supply-chain": "SC",
        }

        headers = ["Rank", "Provider", "Assessment", "Index"] + [
            domain_abbrev.get(d, d[:4].title()) for d in domains
        ] + ["Complete", "Must-Haves", "Certs", "Eligible", "Publish", "Stale"]

        rows = []
        for r in results:
            mh_status = (
                click.style("PASS", fg="green")
                if r.must_have_passed
                else click.style(
                    f"FAIL ({sum(1 for m in r.must_have_results if not m.passed)})",
                    fg="red",
                )
            )
            eligible_str = (
                click.style("yes", fg="green")
                if r.eligible
                else click.style("no", fg="red")
            )
            cert_status = (
                click.style("PASS", fg="green")
                if r.certs_passed
                else click.style("FAIL", fg="red")
            )
            publish_status = (
                click.style("yes", fg="green")
                if r.publishable
                else click.style("no", fg="yellow")
            )
            completeness = (
                "—"
                if r.catalog_coverage is None
                or r.catalog_coverage.completeness is None
                else f"{r.catalog_coverage.completeness:.0%}"
            )
            stale_str = click.style("YES", fg="yellow") if r.stale else "no"
            row = [
                r.rank if r.rank else "—",
                r.display_name,
                r.assessment_id,
                str(round(r.overall_score)),
            ]
            for d in domains:
                ds = r.domain_scores.get(d)
                row.append(str(round(ds)) if ds is not None else "—")
            row += [
                completeness,
                mh_status,
                cert_status,
                eligible_str,
                publish_status,
                stale_str,
            ]
            rows.append(row)

        click.echo(f"\nScoring Profile: {scoring_profile.name}")
        click.echo(
            "Index: ordinal maturity heuristic (integer display); "
            f"aggregation: {scoring_profile.mixed_aggregation}\n"
        )
        click.echo(tabulate(rows, headers=headers, tablefmt="simple"))
        for result in results:
            reasons = result.eligibility_reasons or result.publication_reasons
            if reasons:
                click.echo(
                    f"  {result.assessment_id}: " + "; ".join(reasons)
                )
        click.echo()
