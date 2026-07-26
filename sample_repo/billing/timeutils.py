"""Date helpers shared across the billing package."""

from datetime import datetime


def days_between(start: datetime, end: datetime) -> int:
    """Return the number of days from start to end, counting a partial day as a full day.

    Billing treats any remaining fraction of a day as a whole day, so a customer
    with four hours left has one day remaining, not zero. A moment that has
    already passed returns zero or a negative number.
    """
    delta = end - start
    return delta.days


def is_past(moment: datetime, now: datetime) -> bool:
    """Return True when moment is strictly before now."""
    return moment < now
