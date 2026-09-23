"""Provider-assessment discovery shared by CLI commands."""

from __future__ import annotations

from pathlib import Path

import click

from ..core.loader import load_provider
from ..core.models import ProviderProfile


def load_all_assessments(
    providers_dir: Path,
    schema_dir: Path,
) -> list[tuple[Path, ProviderProfile]]:
    return [
        (path, load_provider(path, schema_dir))
        for path in sorted(providers_dir.glob("*.yaml"))
    ]


def select_assessments(
    candidates: list[tuple[Path, ProviderProfile]],
    selectors: list[str],
) -> list[ProviderProfile]:
    """Resolve selectors as file stems, assessment IDs, or provider slugs."""
    selected: list[ProviderProfile] = []
    for selector in selectors:
        matches = [
            profile
            for path, profile in candidates
            if selector in (path.stem, profile.identity, profile.provider)
        ]
        if not matches:
            raise click.ClickException(
                f"Provider assessment not found: {selector}"
            )
        for profile in matches:
            if all(existing.identity != profile.identity for existing in selected):
                selected.append(profile)
    return selected


def select_one_assessment(
    candidates: list[tuple[Path, ProviderProfile]],
    selector: str,
) -> ProviderProfile:
    slug_matches = [
        profile for _, profile in candidates if selector == profile.provider
    ]
    if len(slug_matches) > 1:
        choices = ", ".join(profile.identity for profile in slug_matches)
        raise click.ClickException(
            f"Provider slug '{selector}' is ambiguous; use an assessment ID: "
            f"{choices}"
        )
    exact = [
        profile
        for path, profile in candidates
        if selector in (path.stem, profile.identity)
    ]
    if len(exact) == 1:
        return exact[0]
    if len(slug_matches) == 1:
        return slug_matches[0]
    raise click.ClickException(f"Provider assessment not found: {selector}")
