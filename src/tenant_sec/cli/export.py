"""tenant-sec export command."""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path

import click

from ..core.loader import load_provider
from ..core.models import LeafControlScore, MixedControlScore


def _provider_to_dict(provider) -> dict:
    """Convert a ProviderProfile to a JSON-serializable dict."""
    controls = {}
    for control_id, entry in provider.controls.items():
        if isinstance(entry, LeafControlScore):
            c: dict = {
                "score": entry.score,
                "evidence": entry.evidence,
            }
            if entry.compensating_controls:
                c["compensating_controls"] = entry.compensating_controls
            if entry.verified_at:
                c["verified_at"] = entry.verified_at.isoformat()
            controls[control_id] = c
        elif isinstance(entry, MixedControlScore):
            c = {
                "score": "mixed",
                "services": {
                    svc_id: {
                        "score": svc.score,
                        "evidence": svc.evidence,
                    }
                    for svc_id, svc in entry.services.items()
                },
            }
            if entry.summary:
                c["summary"] = entry.summary
            if entry.verified_at:
                c["verified_at"] = entry.verified_at.isoformat()
            controls[control_id] = c

    return {
        "provider": provider.provider,
        "display_name": provider.display_name,
        "assessed_by": provider.assessed_by,
        "assessed_at": provider.assessed_at.isoformat(),
        "methodology_version": provider.methodology_version,
        "revision": provider.revision,
        "services_in_scope": [
            {
                "id": svc.id,
                "name": svc.name,
                "category": svc.category,
            }
            for svc in provider.services_in_scope
        ],
        "controls": controls,
    }


def _provider_to_csv(provider) -> str:
    buf = io.StringIO()
    fieldnames = [
        "control_id",
        "type",
        "service",
        "score",
        "evidence",
        "compensating_controls",
        "verified_at",
    ]
    writer = csv.DictWriter(buf, fieldnames=fieldnames)
    writer.writeheader()

    for control_id, entry in sorted(provider.controls.items()):
        if isinstance(entry, LeafControlScore):
            writer.writerow(
                {
                    "control_id": control_id,
                    "type": "leaf",
                    "service": "",
                    "score": entry.score,
                    "evidence": entry.evidence.strip().replace("\n", " "),
                    "compensating_controls": (
                        entry.compensating_controls.strip().replace("\n", " ")
                        if entry.compensating_controls
                        else ""
                    ),
                    "verified_at": entry.verified_at.isoformat() if entry.verified_at else "",
                }
            )
        elif isinstance(entry, MixedControlScore):
            for svc_id, svc in entry.services.items():
                writer.writerow(
                    {
                        "control_id": control_id,
                        "type": "mixed",
                        "service": svc_id,
                        "score": svc.score if svc.score is not None else "N/A",
                        "evidence": svc.evidence.strip().replace("\n", " "),
                        "compensating_controls": "",
                        "verified_at": (
                            entry.verified_at.isoformat() if entry.verified_at else ""
                        ),
                    }
                )
    return buf.getvalue()


def _provider_to_html(provider) -> str:
    level_colors = {0: "#dc2626", 1: "#d97706", 2: "#0891b2", 3: "#16a34a"}

    def badge(score) -> str:
        if score is None:
            return '<span style="color:#6b7280">N/A</span>'
        color = level_colors.get(score, "#6b7280")
        return f'<span style="color:{color};font-weight:bold">L{score}</span>'

    rows_html = []
    for control_id, entry in sorted(provider.controls.items()):
        if isinstance(entry, LeafControlScore):
            evidence_html = entry.evidence.strip().replace("\n", " ")
            rows_html.append(
                f"<tr>"
                f"<td><code>{control_id}</code></td>"
                f"<td>{badge(entry.score)}</td>"
                f"<td></td>"
                f"<td>{evidence_html}</td>"
                f"</tr>"
            )
        elif isinstance(entry, MixedControlScore):
            for i, (svc_id, svc) in enumerate(entry.services.items()):
                control_cell = (
                    f'<td rowspan="{len(entry.services)}"><code>{control_id}</code>'
                    f'<br><small style="color:#6b7280">{entry.summary or ""}</small></td>'
                    if i == 0
                    else ""
                )
                rows_html.append(
                    f"<tr>"
                    f"{control_cell}"
                    f"<td>{badge(svc.score)}</td>"
                    f"<td><small>{svc_id}</small></td>"
                    f"<td><small>{svc.evidence.strip().replace(chr(10), ' ')}</small></td>"
                    f"</tr>"
                )

    rows = "\n".join(rows_html)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>{provider.display_name} — tenant-sec Assessment</title>
<style>
  body {{ font-family: system-ui, sans-serif; margin: 2rem; color: #111; }}
  h1 {{ color: #1e3a5f; }}
  .meta {{ color: #6b7280; font-size: 0.9em; margin-bottom: 1.5rem; }}
  table {{ border-collapse: collapse; width: 100%; font-size: 0.875rem; }}
  th {{ background: #1e3a5f; color: white; padding: 8px 12px; text-align: left; }}
  td {{ border: 1px solid #e5e7eb; padding: 6px 10px; vertical-align: top; }}
  tr:nth-child(even) {{ background: #f9fafb; }}
  code {{ background: #f3f4f6; padding: 2px 4px; border-radius: 3px; font-size: 0.85em; }}
</style>
</head>
<body>
<h1>{provider.display_name}</h1>
<div class="meta">
  Assessed by: <strong>{provider.assessed_by}</strong> &bull;
  Assessed at: <strong>{provider.assessed_at}</strong> &bull;
  Revision: <strong>{provider.revision}</strong> &bull;
  Methodology: <strong>{provider.methodology_version}</strong>
</div>
<table>
  <thead>
    <tr>
      <th>Control ID</th>
      <th>Score</th>
      <th>Service</th>
      <th>Evidence</th>
    </tr>
  </thead>
  <tbody>
{rows}
  </tbody>
</table>
</body>
</html>"""


@click.command()
@click.option(
    "--provider",
    "provider_slug",
    required=True,
    help="Provider slug (e.g. aws, gcp, scaleway).",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["json", "csv", "html"]),
    required=True,
    help="Output format.",
)
@click.option(
    "--output",
    "-o",
    default=None,
    type=click.Path(path_type=Path),
    help="Output file path. Defaults to stdout.",
)
@click.pass_context
def export(
    ctx: click.Context,
    provider_slug: str,
    output_format: str,
    output: Path,
) -> None:
    """Export a provider profile to JSON, CSV, or HTML.

    Examples:

      tenant-sec export --provider aws --format html > aws-report.html

      tenant-sec export --provider scaleway --format csv -o scaleway.csv
    """
    from .main import get_data_dir

    data_dir = get_data_dir(ctx)
    schema_dir = data_dir / "schema"
    providers_dir = data_dir / "providers"

    provider_path = providers_dir / f"{provider_slug}.yaml"
    if not provider_path.exists():
        raise click.ClickException(f"Provider profile not found: {provider_path}")

    provider = load_provider(provider_path, schema_dir)

    if output_format == "json":
        content = json.dumps(_provider_to_dict(provider), indent=2)
    elif output_format == "csv":
        content = _provider_to_csv(provider)
    else:  # html
        content = _provider_to_html(provider)

    if output:
        output.write_text(content)
        click.echo(f"Exported {provider.display_name} to {output}", err=True)
    else:
        click.echo(content)
