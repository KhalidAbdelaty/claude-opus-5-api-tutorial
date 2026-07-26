"""Invoice math for mid-cycle plan changes."""

from datetime import datetime

from billing.timeutils import days_between


def unused_days(period_end: datetime, now: datetime) -> int:
    """Return the days left in the current billing period."""
    return days_between(now, period_end)


def prorated_credit(
    plan_price_cents: int,
    period_days: int,
    period_end: datetime,
    now: datetime,
) -> int:
    """Return the credit owed for the unused part of a billing period."""
    if period_days <= 0:
        raise ValueError("period_days must be positive")
    remaining = unused_days(period_end, now)
    if remaining <= 0:
        return 0
    return round(plan_price_cents * remaining / period_days)
