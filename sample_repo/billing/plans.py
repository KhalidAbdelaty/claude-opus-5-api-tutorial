"""Plan catalog."""

PLANS = {
    "starter": {"price_cents": 1500, "period_days": 30},
    "team": {"price_cents": 3000, "period_days": 30},
    "scale": {"price_cents": 9000, "period_days": 30},
}


def plan_price_cents(plan_code: str) -> int:
    """Return the monthly price for a plan code."""
    return PLANS[plan_code]["price_cents"]


def plan_period_days(plan_code: str) -> int:
    """Return the billing period length for a plan code."""
    return PLANS[plan_code]["period_days"]
