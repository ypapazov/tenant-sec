"""Typed dataclasses for all tenant-sec entities."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import IntEnum
from typing import Optional


class MaturityLevel(IntEnum):
    IMPOSSIBLE = 0
    REQUIRES_OWN_LOOP = 1
    MANAGED_LIMITED = 2
    MANAGED_CUSTOMIZABLE = 3

    @classmethod
    def label(cls, value: int) -> str:
        labels = {
            0: "L0: Impossible from tenant space",
            1: "L1: Requires own processing loop",
            2: "L2: Available managed, limited",
            3: "L3: Available managed, customizable",
        }
        return labels.get(value, f"L{value}")


@dataclass
class Control:
    """A single control definition from controls/{domain}/*.yaml."""

    id: str
    domain: str
    name: str
    description: str
    criteria: dict[str, str]  # keys: L0, L1, L2, L3
    framework_mappings: dict[str, list[str]]
    service_scoped: bool = False
    parent: Optional[str] = None
    sub_control_aggregation: Optional[str] = None  # min, max, mean, worst


@dataclass
class ServiceScore:
    """An individual service score within a mixed composite."""

    score: Optional[int]  # None means not applicable
    evidence: str


@dataclass
class LeafControlScore:
    """A direct maturity level score for a control."""

    score: int  # 0-3
    evidence: str
    compensating_controls: Optional[str] = None
    verified_at: Optional[date] = None


@dataclass
class MixedControlScore:
    """A per-service breakdown score for a control."""

    services: dict[str, ServiceScore]  # service_id → ServiceScore
    summary: Optional[str] = None
    verified_at: Optional[date] = None


# Union type for a control score entry in a provider profile
ControlScore = LeafControlScore | MixedControlScore


@dataclass
class ServiceInScope:
    """A service listed in a provider's services_in_scope."""

    id: str  # Provider-local alias
    name: str
    category: str  # Canonical category from service catalog
    aliases: list[str] = field(default_factory=list)


@dataclass
class ProviderProfile:
    """A provider assessment profile from providers/*.yaml."""

    provider: str
    display_name: str
    assessed_by: str
    assessed_at: date
    methodology_version: str
    revision: int
    services_in_scope: list[ServiceInScope]
    controls: dict[str, ControlScore]  # control_id → score


@dataclass
class MustHaveEntry:
    """A must-have requirement in a scoring profile."""

    control: str
    min_level: int


@dataclass
class ScoringProfile:
    """A scoring profile from profiles/*.yaml."""

    name: str
    weights: dict[str, float]  # domain → weight (must sum to 1.0)
    mixed_aggregation: str
    description: Optional[str] = None
    must_have: list[MustHaveEntry] = field(default_factory=list)
