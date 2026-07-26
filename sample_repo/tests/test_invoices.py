from datetime import datetime, timedelta, timezone

from billing.invoices import prorated_credit
from billing.plans import plan_period_days, plan_price_cents

NOW = datetime(2026, 7, 24, 9, 0, tzinfo=timezone.utc)


def test_prorated_credit_counts_partial_day():
    """Ten days and eight hours left bills as eleven unused days."""
    credit = prorated_credit(
        plan_price_cents=plan_price_cents("team"),
        period_days=plan_period_days("team"),
        period_end=NOW + timedelta(days=10, hours=8),
        now=NOW,
    )
    assert credit == 1100


def test_prorated_credit_after_period_end():
    credit = prorated_credit(
        plan_price_cents=plan_price_cents("team"),
        period_days=plan_period_days("team"),
        period_end=NOW - timedelta(days=2),
        now=NOW,
    )
    assert credit == 0
