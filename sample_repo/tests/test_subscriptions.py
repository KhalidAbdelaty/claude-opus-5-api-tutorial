from datetime import datetime, timedelta, timezone

from billing.subscriptions import Subscription, access_level, is_trial_active

NOW = datetime(2026, 7, 24, 9, 0, tzinfo=timezone.utc)


def make_subscription(trial_ends_at):
    return Subscription(
        customer_id="cus_1042",
        plan_code="team",
        trial_ends_at=trial_ends_at,
    )


def test_trial_active_with_days_left():
    subscription = make_subscription(NOW + timedelta(days=5))
    assert is_trial_active(subscription, NOW) is True


def test_trial_active_on_final_day():
    """A customer with hours left is still on trial."""
    subscription = make_subscription(NOW + timedelta(hours=10))
    assert is_trial_active(subscription, NOW) is True
    assert access_level(subscription, NOW) == "trial"


def test_trial_inactive_at_exact_expiry():
    """The trial ends the moment the clock reaches trial_ends_at."""
    subscription = make_subscription(NOW)
    assert is_trial_active(subscription, NOW) is False
    assert access_level(subscription, NOW) == "locked"


def test_trial_inactive_after_expiry():
    subscription = make_subscription(NOW - timedelta(days=2))
    assert is_trial_active(subscription, NOW) is False
