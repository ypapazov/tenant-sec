"""tenant-sec detail command."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import click
from tabulate import tabulate

from ..core.loader import load_control_registry
from ..core.models import LeafControlScore, MixedControlScore
from ..core.staleness import staleness_info
from ._providers import load_all_assessments, select_one_assessment


LEVEL_COLORS = {0: "red", 1: "yellow", 2: "cyan", 3: "green"}


def _colored_level(score: int) -> str:
    label = f"L{score}"
    color = LEVEL_COLORS.get(score, "white")
    return click.style(label, fg=color)


@click.command()
@click.option(
    "--provider",
    "provider_slug",
    required=True,
    help="Provider slug, profile filename stem, or assessment ID.",
)
@click.option(
    "--domain",
    default=None,
    help="Filter to a specific domain (e.g. iam, encryption).",
)
@click.option("--verbose", "-v", is_flag=True, help="Show full evidence text.")
@click.pass_context
def detail(
    ctx: click.Context,
    provider_slug: str,
    domain: Optional[str],
    verbose: bool,
) -> None:
    """Show per-control detail for a single provider.

    Example:

      tenant-sec detail --provider aws --domain encryption
    """
    from .main import get_data_dir

    data_dir = get_data_dir(ctx)
    schema_dir = data_dir / "schema"
    providers_dir = data_dir / "providers"
    controls_dir = data_dir / "controls"

    provider = select_one_assessment(
        load_all_assessments(providers_dir, schema_dir),
        provider_slug,
    )
    registry = load_control_registry(controls_dir)

    staleness = staleness_info(provider.assessed_at, provider.assessed_by)
    stale_warn = ""
    if staleness["stale"]:
        stale_warn = click.style(" [STALE]", fg="yellow", bold=True)

    click.echo(
        f"\n{click.style(provider.display_name, bold=True)}{stale_warn} — "
        f"{provider.identity} — "
        f"assessed {provider.assessed_at} by {provider.assessed_by} "
        f"(rev {provider.revision})\n"
    )

    domains_to_show = [domain] if domain else registry.domains()

    for dom in domains_to_show:
        controls = [
            control
            for control in registry.by_domain(dom)
            if control.surface == "tenant"
        ]
        if not controls:
            continue

        click.echo(click.style(f"── {dom.upper()} ", bold=True, fg="blue") + "─" * 50)

        for control in controls:
            score_entry = provider.controls.get(control.id)
            if score_entry is None:
                score_str = click.style("—  (unassessed)", fg="white", dim=True)
                click.echo(f"  {control.id:<45} {score_str}")
                continue

            if isinstance(score_entry, LeafControlScore):
                if score_entry.score is None:
                    level_str = click.style(
                        str(score_entry.status or "not_assessed").upper(),
                        fg="yellow",
                    )
                else:
                    level_str = _colored_level(score_entry.score)
                click.echo(f"  {control.id:<45} {level_str}  {control.name}")
                if verbose:
                    evidence = score_entry.evidence.strip().replace("\n", " ")
                    click.echo(f"       {click.style('Evidence:', dim=True)} {evidence}")
                    if score_entry.compensating_controls:
                        cc = score_entry.compensating_controls.strip().replace("\n", " ")
                        click.echo(f"       {click.style('Compensating:', dim=True)} {cc}")

            elif isinstance(score_entry, MixedControlScore):
                click.echo(
                    f"  {control.id:<45} {click.style('MIXED', fg='blue')}  {control.name}"
                )
                if score_entry.summary:
                    click.echo(f"       {click.style(score_entry.summary, dim=True)}")

                # Per-service breakdown
                svc_rows = []
                for svc_id, svc_score in score_entry.services.items():
                    if svc_score.score is None:
                        score_disp = click.style(
                            str(svc_score.status or "not_applicable").upper(),
                            dim=True,
                        )
                    else:
                        score_disp = _colored_level(svc_score.score)
                    evidence = svc_score.evidence.strip()[:60] + "…" if not verbose else svc_score.evidence.strip()
                    svc_rows.append([f"    {svc_id}", score_disp, evidence])

                click.echo(tabulate(svc_rows, tablefmt="plain"))

        click.echo()
