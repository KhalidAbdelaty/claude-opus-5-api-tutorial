"""Subscription state and trial handling."""

from dataclasses import dataclass
from datetime import datetime

from billing.timeutils import days_between


@dataclass
class Subscription:
    customer_id: str
    plan_code: str
    trial_ends_at: datetime


def trial_days_remaining(subscription: Subscription, now: datetime) -> int:
    """Return how many days of trial the customer still has."""
    return days_between(now, subscription.trial_ends_at)


def is_trial_active(subscription: Subscription, now: datetime) -> bool:
    """Return True while the customer still has trial time left."""
    return trial_days_remaining(subscription, now) > 0


def access_level(subscription: Subscription, now: datetime) -> str:
    """Return the feature tier the customer should see right now."""
    if is_trial_active(subscription, now):
        return "trial"
    return "locked"
