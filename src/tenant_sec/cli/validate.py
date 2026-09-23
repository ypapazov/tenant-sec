"""tenant-sec validate command."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import click

from ..core.loader import validate_file


@click.command()
@click.argument("path", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--type",
    "file_type",
    type=click.Choice(
        ["control", "provider", "scoring-profile", "certification-catalog"]
    ),
    default=None,
    help="File type to validate against. Auto-detected if omitted.",
)
@click.pass_context
def validate(ctx: click.Context, path: Path, file_type: Optional[str]) -> None:
    """Validate a YAML file against the tenant-sec schemas.

    PATH is the YAML file to validate (control, provider profile, or scoring profile).

    Examples:

      tenant-sec validate providers/scaleway.yaml

      tenant-sec validate controls/iam/abac.yaml --type control
    """
    from .main import get_data_dir

    data_dir = get_data_dir(ctx)
    schema_dir = data_dir / "schema"
    controls_dir = data_dir / "controls"
    catalog_path = schema_dir / "service-catalog.yaml"

    if not schema_dir.exists():
        raise click.ClickException(f"Schema directory not found: {schema_dir}")

    errors = validate_file(
        path=path,
        schema_dir=schema_dir,
        file_type=file_type,
        controls_dir=controls_dir if controls_dir.exists() else None,
        catalog_path=catalog_path if catalog_path.exists() else None,
    )

    if errors:
        click.echo(click.style(f"✗ {path}", fg="red", bold=True))
        for error in errors:
            click.echo(f"  {click.style('ERROR', fg='red')}: {error}")
        raise SystemExit(1)
    else:
        click.echo(click.style(f"✓ {path} is valid", fg="green"))
