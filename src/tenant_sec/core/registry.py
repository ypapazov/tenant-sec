"""Control registry and service catalog resolution."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import yaml

from .models import Control


class ControlRegistry:
    """Index of all known controls, queryable by ID, domain, and parent/child."""

    def __init__(self, controls: list[Control]) -> None:
        self._by_id: dict[str, Control] = {c.id: c for c in controls}
        self._by_domain: dict[str, list[Control]] = {}
        self._children: dict[str, list[str]] = {}  # parent_id → child_ids

        for control in controls:
            self._by_domain.setdefault(control.domain, []).append(control)
            if control.parent:
                self._children.setdefault(control.parent, []).append(control.id)

    def get(self, control_id: str) -> Optional[Control]:
        return self._by_id.get(control_id)

    def by_domain(self, domain: str) -> list[Control]:
        return self._by_domain.get(domain, [])

    def children_of(self, parent_id: str) -> list[Control]:
        child_ids = self._children.get(parent_id, [])
        return [self._by_id[cid] for cid in child_ids if cid in self._by_id]

    def all_controls(self) -> list[Control]:
        return list(self._by_id.values())

    def all_ids(self) -> set[str]:
        return set(self._by_id.keys())

    def domains(self) -> list[str]:
        return list(self._by_domain.keys())

    @classmethod
    def from_directory(cls, controls_dir: Path) -> "ControlRegistry":
        """Load all control YAML files from a controls/ directory tree."""
        controls: list[Control] = []

        index_path = controls_dir / "_index.yaml"
        if not index_path.exists():
            raise FileNotFoundError(f"Controls index not found: {index_path}")

        with open(index_path) as f:
            index = yaml.safe_load(f)

        for domain_slug, domain_info in index.get("domains", {}).items():
            domain_dir = controls_dir / domain_slug
            if not domain_dir.exists():
                continue
            for control_id in domain_info.get("controls", []):
                # Derive filename from the part after the first dot
                filename = control_id.split(".", 1)[1] + ".yaml"
                control_path = domain_dir / filename
                if control_path.exists():
                    with open(control_path) as f:
                        data = yaml.safe_load(f)
                    controls.append(_parse_control(data))

        return cls(controls)


def _parse_control(data: dict) -> Control:
    from .models import Control

    return Control(
        id=data["id"],
        domain=data["domain"],
        name=data["name"],
        description=data.get("description", ""),
        criteria=data.get("criteria", {}),
        framework_mappings=data.get("framework_mappings", {}),
        service_scoped=data.get("service_scoped", False),
        parent=data.get("parent"),
        sub_control_aggregation=data.get("sub_control_aggregation"),
    )


class ServiceCatalog:
    """Canonical service category taxonomy with provider alias resolution."""

    def __init__(self, catalog_data: dict) -> None:
        self._categories: dict[str, dict] = catalog_data.get("categories", {})
        # Build reverse index: (provider, alias) → canonical_id
        self._alias_index: dict[tuple[str, str], str] = {}
        for canonical_id, category in self._categories.items():
            for provider, aliases in category.get("aliases", {}).items():
                for alias in aliases:
                    self._alias_index[(provider, alias)] = canonical_id

    def resolve(self, provider: str, service_alias: str) -> Optional[str]:
        """Resolve a provider-specific service alias to its canonical category ID."""
        return self._alias_index.get((provider, service_alias))

    def canonical_categories(self) -> list[str]:
        return list(self._categories.keys())

    def aliases_for_provider(self, provider: str) -> dict[str, str]:
        """Returns {alias: canonical_id} for the given provider."""
        return {
            alias: canonical_id
            for (prov, alias), canonical_id in self._alias_index.items()
            if prov == provider
        }

    @classmethod
    def from_file(cls, catalog_path: Path) -> "ServiceCatalog":
        with open(catalog_path) as f:
            data = yaml.safe_load(f)
        return cls(data)
