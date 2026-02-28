"""tenant-sec compare command."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import click
from tabulate import tabulate

from ..core.loader import load_provider, load_control_registry
from ..core.models import LeafControlScore, MixedControlScore


LEVEL_COLORS = {0: "red", 1: "yellow", 2: "cyan", 3: "green"}


def _cell(score_entry, mixed_agg_val: Optional[float] = None) -> str:
    if score_entry is None:
        return "—"
    if isinstance(score_entry, LeafControlScore):
        level = score_entry.score
        label = f"L{level}"
        color = LEVEL_COLORS.get(level, "white")
        return click.style(label, fg=color)
    if isinstance(score_entry, MixedControlScore):
        # Show distribution summary: e.g. "MIX(2L3,1L2,1L0)"
        counts: dict[Optional[int], int] = {}
        for svc in score_entry.services.values():
            counts[svc.score] = counts.get(svc.score, 0) + 1
        parts = []
        for lvl in [3, 2, 1, 0]:
            if counts.get(lvl, 0) > 0:
                c = LEVEL_COLORS.get(lvl, "white")
                parts.append(click.style(f"{counts[lvl]}×L{lvl}", fg=c))
        if counts.get(None, 0) > 0:
            parts.append(click.style(f"{counts[None]}×N/A", dim=True))
        return "/".join(parts) if parts else "MIX"
    return "?"


@click.command()
@click.option(
    "--providers",
    required=True,
    help="Comma-separated provider slugs to compare (e.g. aws,gcp,scaleway).",
)
@click.option(
    "--controls",
    "control_ids",
    default=None,
    help="Comma-separated control IDs to show. Defaults to all.",
)
@click.option(
    "--domain",
    default=None,
    help="Filter to a specific domain.",
)
@click.pass_context
def compare(
    ctx: click.Context,
    providers: str,
    control_ids: Optional[str],
    domain: Optional[str],
) -> None:
    """Side-by-side comparison of providers across controls.

    Example:

      tenant-sec compare --providers aws,gcp,scaleway --domain iam
    """
    from .main import get_data_dir

    data_dir = get_data_dir(ctx)
    schema_dir = data_dir / "schema"
    providers_dir = data_dir / "providers"
    controls_dir = data_dir / "controls"

    provider_slugs = [p.strip() for p in providers.split(",")]
    loaded_providers = {}
    for slug in provider_slugs:
        p_path = providers_dir / f"{slug}.yaml"
        if not p_path.exists():
            raise click.ClickException(f"Provider profile not found: {p_path}")
        loaded_providers[slug] = load_provider(p_path, schema_dir)

    registry = load_control_registry(controls_dir)

    # Determine controls to show
    if control_ids:
        ids = [c.strip() for c in control_ids.split(",")]
        controls_to_show = [c for c in registry.all_controls() if c.id in ids]
    elif domain:
        controls_to_show = registry.by_domain(domain)
    else:
        controls_to_show = registry.all_controls()

    if not controls_to_show:
        raise click.ClickException("No controls to show.")

    # Group by domain
    domains_seen: dict[str, list] = {}
    for control in controls_to_show:
        domains_seen.setdefault(control.domain, []).append(control)

    provider_display = [loaded_providers[s].display_name for s in provider_slugs]
    headers = ["Control", "Name"] + provider_display

    for dom, dom_controls in domains_seen.items():
        click.echo(click.style(f"\n── {dom.upper()} ", bold=True, fg="blue") + "─" * 40)
        rows = []
        for control in dom_controls:
            row = [control.id, control.name[:35]]
            for slug in provider_slugs:
                provider = loaded_providers[slug]
                entry = provider.controls.get(control.id)
                row.append(_cell(entry))
            rows.append(row)
        click.echo(tabulate(rows, headers=headers, tablefmt="simple"))

    click.echo()
