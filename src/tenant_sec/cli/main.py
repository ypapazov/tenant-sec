"""tenant-sec CLI entry point."""

from __future__ import annotations

import os
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Optional

import click

from . import validate as validate_cmd
from . import score as score_cmd
from . import detail as detail_cmd
from . import compare as compare_cmd
from . import export as export_cmd


def find_data_dir(explicit: Optional[str]) -> Optional[Path]:
    """Resolve the data directory in order:
    1. Explicit --data-dir flag
    2. TENANT_SEC_DATA environment variable
    3. Walk up from CWD looking for controls/ + schema/
    4. Data bundled in an installed package
    5. Parent of this file (editable monorepo layout)
    """
    if explicit:
        return Path(explicit)

    env_path = os.environ.get("TENANT_SEC_DATA")
    if env_path:
        return Path(env_path)

    # Walk up from CWD
    candidate = Path.cwd()
    for _ in range(10):
        if (candidate / "controls").is_dir() and (candidate / "schema").is_dir():
            return candidate
        parent = candidate.parent
        if parent == candidate:
            break
        candidate = parent

    package_data = Path(__file__).parent.parent / "data"
    if (package_data / "controls").is_dir() and (package_data / "schema").is_dir():
        return package_data

    # Fall back to monorepo root (cli/ → tenant_sec/ → src/ → root)
    module_root = Path(__file__).parent.parent.parent.parent
    if (module_root / "controls").is_dir() and (module_root / "schema").is_dir():
        return module_root

    return None


DATA_DIR_HELP = (
    "Root of the tenant-sec data tree (contains controls/, schema/, providers/). "
    "Defaults to TENANT_SEC_DATA env var or auto-detected from CWD."
)


try:
    PACKAGE_VERSION = version("tenant-sec")
except PackageNotFoundError:
    PACKAGE_VERSION = "1.0.0rc1"


@click.group()
@click.version_option(version=PACKAGE_VERSION, prog_name="tenant-sec")
@click.option("--data-dir", envvar="TENANT_SEC_DATA", default=None, help=DATA_DIR_HELP)
@click.pass_context
def cli(ctx: click.Context, data_dir: Optional[str]) -> None:
    """tenant-sec — Cloud provider security capability assessment tool."""
    ctx.ensure_object(dict)
    resolved = find_data_dir(data_dir)
    ctx.obj["data_dir"] = resolved


def get_data_dir(ctx: click.Context) -> Path:
    data_dir = ctx.obj.get("data_dir")
    if data_dir is None:
        raise click.UsageError(
            "Cannot find tenant-sec data directory. "
            "Set --data-dir, TENANT_SEC_DATA env var, or run from within the repository."
        )
    return Path(data_dir)


cli.add_command(validate_cmd.validate)
cli.add_command(score_cmd.score)
cli.add_command(detail_cmd.detail)
cli.add_command(compare_cmd.compare)
cli.add_command(export_cmd.export)
