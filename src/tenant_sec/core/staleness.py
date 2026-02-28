"""Staleness computation from assessed_at date and assessor tier."""

from __future__ import annotations

from datetime import date
import calendar


# Validity thresholds per assessor tier
STALENESS_THRESHOLDS: dict[str, int] = {
    "accredited": 12,  # months
    "community": 6,
    "self": 6,
}


def _assessor_tier(assessed_by: str) -> str:
    """Extract the tier prefix from an assessed_by string."""
    if assessed_by.startswith("accredited:"):
        return "accredited"
    if assessed_by.startswith("community:"):
        return "community"
    return "self"


def is_stale(
    assessed_at: date,
    assessed_by: str,
    reference_date: date | None = None,
) -> bool:
    """Return True if the assessment is older than the tier-based threshold.

    Args:
        assessed_at: Date the assessment was performed.
        assessed_by: Assessor identifier (self, community:{handle}, accredited:{org}).
        reference_date: Date to compare against; defaults to today.
    """
    if reference_date is None:
        reference_date = date.today()

    tier = _assessor_tier(assessed_by)
    months = STALENESS_THRESHOLDS.get(tier, 6)
    expiry = _add_months(assessed_at, months)
    return reference_date > expiry


def _add_months(d: date, months: int) -> date:
    """Add a number of months to a date, clamping to the last day of the month."""
    month = d.month - 1 + months
    year = d.year + month // 12
    month = month % 12 + 1
    day = min(d.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def staleness_info(
    assessed_at: date,
    assessed_by: str,
    reference_date: date | None = None,
) -> dict:
    """Return a dict with staleness details for display purposes."""
    if reference_date is None:
        reference_date = date.today()

    tier = _assessor_tier(assessed_by)
    months = STALENESS_THRESHOLDS.get(tier, 6)
    expiry = _add_months(assessed_at, months)
    stale = reference_date > expiry

    return {
        "stale": stale,
        "tier": tier,
        "assessed_at": assessed_at,
        "valid_months": months,
        "expiry": expiry,
    }
