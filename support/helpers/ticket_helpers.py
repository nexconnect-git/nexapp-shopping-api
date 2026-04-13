"""
Utility helpers for priority/category validation and SLA logic.
"""

from support.models import (
    TICKET_CATEGORY_CHOICES,
    TICKET_PRIORITY_CHOICES,
    TICKET_STATUS_CHOICES,
)

# Flat sets for O(1) membership checks
VALID_CATEGORIES = {key for key, _ in TICKET_CATEGORY_CHOICES}
VALID_PRIORITIES = {key for key, _ in TICKET_PRIORITY_CHOICES}
VALID_STATUSES = {key for key, _ in TICKET_STATUS_CHOICES}

# SLA response targets (hours) keyed by priority
SLA_RESPONSE_HOURS = {
    'low':    72,
    'medium': 24,
    'high':   4,
}


def validate_category(category: str) -> bool:
    """Return True if *category* is a recognised ticket category."""
    return category in VALID_CATEGORIES


def validate_priority(priority: str) -> bool:
    """Return True if *priority* is a recognised ticket priority."""
    return priority in VALID_PRIORITIES


def validate_status(status: str) -> bool:
    """Return True if *status* is a recognised ticket status."""
    return status in VALID_STATUSES


def get_sla_hours(priority: str) -> int:
    """Return the SLA target response time in hours for *priority*.

    Falls back to the 'medium' SLA if the priority is unrecognised.
    """
    return SLA_RESPONSE_HOURS.get(priority, SLA_RESPONSE_HOURS['medium'])
