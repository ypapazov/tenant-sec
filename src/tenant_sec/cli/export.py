"""tenant-sec export command."""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path

import click

from ..core.models import LeafControlScore, MixedControlScore
from ._providers import load_all_assessments, select_one_assessment


def _references_to_dict(references) -> list[dict[str, str]]:
    return [{"url": ref.url, "title": ref.title} for ref in references]


def _claim_bundle_to_dict(entry) -> dict:
    out: dict = {}
    if entry.evidence_items:
        out["evidence_items"] = [
            {
                "id": item.id,
                "url": item.url,
                "title": item.title,
                "source_class": item.source_class,
                "retrieved_at": item.retrieved_at.isoformat(),
                **(
                    {"updated_at": item.updated_at.isoformat()}
                    if item.updated_at
                    else {}
                ),
                "content_hash": item.content_hash,
                "quote": item.quote,
                "applicability": {
                    "offering": item.applicability.offering,
                    "regions": item.applicability.regions,
                    "services": item.applicability.services,
                    "edition": item.applicability.edition,
                },
            }
            for item in entry.evidence_items
        ]
    if entry.claims:
        out["claims"] = [
            {
                "id": claim.id,
                "assertion": claim.assertion,
                "result": claim.result,
                "evidence_item_ids": claim.evidence_item_ids,
                **({"services": claim.services} if claim.services else {}),
            }
            for claim in entry.claims
        ]
    if entry.criteria_results:
        out["criteria_results"] = [
            {
                "level": result.level,
                "met": result.met,
                "reasoning": result.reasoning,
                "claim_ids": result.claim_ids,
            }
            for result in entry.criteria_results
        ]
    return out


def _provider_to_dict(provider) -> dict:
    """Convert a ProviderProfile to a JSON-serializable dict."""
    controls = {}
    for control_id, entry in provider.controls.items():
        if isinstance(entry, LeafControlScore):
            c: dict = {
                "evidence": entry.evidence,
            }
            if entry.score is not None or entry.status is None:
                c["score"] = entry.score
            if entry.status is not None:
                c["status"] = str(entry.status)
            if entry.confidence:
                c["confidence"] = entry.confidence
            if entry.references:
                c["references"] = _references_to_dict(entry.references)
            if entry.compensating_controls:
                c["compensating_controls"] = entry.compensating_controls
            if entry.verified_at:
                c["verified_at"] = entry.verified_at.isoformat()
            c.update(_claim_bundle_to_dict(entry))
            controls[control_id] = c
        elif isinstance(entry, MixedControlScore):
            c = {
                "score": "mixed",
                "services": {
                    svc_id: {
                        "evidence": svc.evidence,
                        **(
                            {"score": svc.score}
                            if svc.score is not None or svc.status is None
                            else {}
                        ),
                        **(
                            {"status": str(svc.status)}
                            if svc.status is not None
                            else {}
                        ),
                        **(
                            {"confidence": svc.confidence}
                            if svc.confidence
                            else {}
                        ),
                        **(
                            {"references": _references_to_dict(svc.references)}
                            if svc.references
                            else {}
                        ),
                    }
                    for svc_id, svc in entry.services.items()
                },
            }
            if entry.summary:
                c["summary"] = entry.summary
            if entry.verified_at:
                c["verified_at"] = entry.verified_at.isoformat()
            if entry.status is not None:
                c["status"] = str(entry.status)
            if entry.confidence:
                c["confidence"] = entry.confidence
            if entry.references:
                c["references"] = _references_to_dict(entry.references)
            c.update(_claim_bundle_to_dict(entry))
            controls[control_id] = c

    result = {
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
                **({"aliases": svc.aliases} if svc.aliases else {}),
                **({"regions": svc.regions} if svc.regions else {}),
                **({"edition": svc.edition} if svc.edition else {}),
            }
            for svc in provider.services_in_scope
        ],
        "controls": controls,
    }
    if provider.assessment_id:
        result["assessment_id"] = provider.assessment_id
    if provider.offering:
        result["offering"] = {
            key: value
            for key, value in {
                "id": provider.offering.id,
                "name": provider.offering.name,
                "partition": provider.offering.partition,
                "regions": provider.offering.regions,
                "region_equivalence": provider.offering.region_equivalence,
                "edition": provider.offering.edition,
                "cohort": provider.offering.cohort,
            }.items()
            if value not in (None, [])
        }
    if provider.vignette:
        result["vignette"] = provider.vignette
    if provider.certifications:
        certifications = []
        for record in provider.certifications:
            certifications.append(
                {
                    key: value
                    for key, value in {
                        "id": record.id,
                        "kind": record.kind,
                        "status": record.status,
                        "valid_from": (
                            record.valid_from.isoformat()
                            if record.valid_from
                            else None
                        ),
                        "valid_until": (
                            record.valid_until.isoformat()
                            if record.valid_until
                            else None
                        ),
                        "validity": record.validity,
                        "scope": record.scope,
                        "offering": record.offering,
                        "regions": record.regions,
                        "services": record.services,
                        "all_services": record.all_services or None,
                        "report_access": record.report_access,
                        "evidence": _references_to_dict(record.evidence),
                    }.items()
                    if value not in (None, [])
                }
            )
        result["certifications"] = certifications
    if provider.service_scope_exceptions:
        result["service_scope_exceptions"] = provider.service_scope_exceptions
    return result


def _provider_to_csv(provider) -> str:
    buf = io.StringIO()
    profile_data = _provider_to_dict(provider)
    profile_columns = {
        "assessment_id": provider.identity,
        "provider": provider.provider,
        "offering_id": (
            provider.offering.id if provider.offering and provider.offering.id else ""
        ),
        "cohort": (
            provider.offering.cohort
            if provider.offering and provider.offering.cohort
            else ""
        ),
        "certifications_json": json.dumps(
            profile_data.get("certifications", []), separators=(",", ":")
        ),
        "vignette_json": json.dumps(
            profile_data.get("vignette", {}), separators=(",", ":")
        ),
    }
    fieldnames = [
        "assessment_id",
        "provider",
        "offering_id",
        "cohort",
        "certifications_json",
        "vignette_json",
        "control_id",
        "type",
        "service",
        "score",
        "status",
        "confidence",
        "evidence",
        "references",
        "compensating_controls",
        "verified_at",
    ]
    writer = csv.DictWriter(buf, fieldnames=fieldnames)
    writer.writeheader()

    for control_id, entry in sorted(provider.controls.items()):
        if isinstance(entry, LeafControlScore):
            writer.writerow(
                {
                    **profile_columns,
                    "control_id": control_id,
                    "type": "leaf",
                    "service": "",
                    "score": entry.score,
                    "status": str(entry.status) if entry.status else "assessed",
                    "confidence": entry.confidence or "",
                    "evidence": entry.evidence.strip().replace("\n", " "),
                    "references": " ".join(ref.url for ref in entry.references),
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
                        **profile_columns,
                        "control_id": control_id,
                        "type": "mixed",
                        "service": svc_id,
                        "score": svc.score if svc.score is not None else "N/A",
                        "status": str(svc.status) if svc.status else (
                            "assessed" if svc.score is not None else "not_applicable"
                        ),
                        "confidence": svc.confidence or entry.confidence or "",
                        "evidence": svc.evidence.strip().replace("\n", " "),
                        "references": " ".join(ref.url for ref in svc.references),
                        "compensating_controls": "",
                        "verified_at": (
                            entry.verified_at.isoformat() if entry.verified_at else ""
                        ),
                    }
                )
    return buf.getvalue()


def _provider_to_html(provider) -> str:
    level_colors = {0: "#dc2626", 1: "#d97706", 2: "#0891b2", 3: "#16a34a"}

    def badge(score, status=None) -> str:
        if score is None:
            label = str(status or "not_applicable").upper()
            return f'<span style="color:#6b7280">{label}</span>'
        color = level_colors.get(score, "#6b7280")
        return f'<span style="color:{color};font-weight:bold">L{score}</span>'

    rows_html = []
    for control_id, entry in sorted(provider.controls.items()):
        if isinstance(entry, LeafControlScore):
            evidence_html = entry.evidence.strip().replace("\n", " ")
            rows_html.append(
                f"<tr>"
                f"<td><code>{control_id}</code></td>"
                f"<td>{badge(entry.score, entry.status)}</td>"
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
                    f"<td>{badge(svc.score, svc.status)}</td>"
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
  Assessment: <strong>{provider.identity}</strong> &bull;
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
    help="Provider slug, profile filename stem, or assessment ID.",
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

    provider = select_one_assessment(
        load_all_assessments(providers_dir, schema_dir),
        provider_slug,
    )

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
