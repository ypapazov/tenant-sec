"""tenant-sec score command."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

import click
from tabulate import tabulate

from ..core.loader import load_provider, load_scoring_profile, load_control_registry
from ..scoring.engine import ScoringEngine


def _level_symbol(score: Optional[float]) -> str:
    if score is None:
        return "—"
    return f"L{int(round(score))}"


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
    help="Comma-separated provider slugs to include. Defaults to all in providers/.",
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

    # Determine which providers to load
    if providers:
        provider_slugs = [p.strip() for p in providers.split(",")]
        provider_paths = [providers_dir / f"{slug}.yaml" for slug in provider_slugs]
    else:
        provider_paths = sorted(providers_dir.glob("*.yaml"))

    if not provider_paths:
        raise click.ClickException("No provider profiles found.")

    loaded_providers = []
    for p in provider_paths:
        if not p.exists():
            raise click.ClickException(f"Provider profile not found: {p}")
        loaded_providers.append(load_provider(p, schema_dir))

    # Load registry
    registry = load_control_registry(controls_dir)
    engine = ScoringEngine(registry)

    results = engine.score(loaded_providers, scoring_profile)

    # Output
    if output_format == "json":
        output = []
        for r in results:
            output.append(
                {
                    "rank": r.rank,
                    "provider": r.provider,
                    "display_name": r.display_name,
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
                    "stale": r.stale,
                }
            )
        click.echo(json.dumps(output, indent=2))

    elif output_format == "csv":
        import csv
        import io

        buf = io.StringIO()
        domains = sorted(scoring_profile.weights.keys())
        fieldnames = ["rank", "provider", "overall_score", "must_have_passed", "stale"] + [
            f"domain_{d}" for d in domains
        ]
        writer = csv.DictWriter(buf, fieldnames=fieldnames)
        writer.writeheader()
        for r in results:
            row = {
                "rank": r.rank,
                "provider": r.provider,
                "overall_score": r.overall_score,
                "must_have_passed": r.must_have_passed,
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

        headers = ["Rank", "Provider", "Overall"] + [
            domain_abbrev.get(d, d[:4].title()) for d in domains
        ] + ["Must-Haves", "Stale"]

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
            stale_str = click.style("YES", fg="yellow") if r.stale else "no"
            row = [
                r.rank,
                r.display_name,
                f"{r.overall_score:.1f}",
            ]
            for d in domains:
                ds = r.domain_scores.get(d)
                row.append(f"{ds:.1f}" if ds is not None else "—")
            row += [mh_status, stale_str]
            rows.append(row)

        click.echo(f"\nScoring Profile: {scoring_profile.name}")
        click.echo(f"Aggregation: {scoring_profile.mixed_aggregation}\n")
        click.echo(tabulate(rows, headers=headers, tablefmt="simple"))
        click.echo()
