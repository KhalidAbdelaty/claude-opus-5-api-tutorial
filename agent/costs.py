"""Token accounting across every request in an agent run."""

from dataclasses import dataclass, asdict

from agent.config import (
    PRICE_CACHE_READ,
    PRICE_CACHE_WRITE_5M,
    PRICE_INPUT,
    PRICE_OUTPUT,
)


@dataclass
class Usage:
    """Cumulative token counts for one or more requests."""

    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0
    requests: int = 0

    def add(self, usage) -> "Usage":
        """Fold one response's usage object into the running total."""
        self.input_tokens += usage.input_tokens or 0
        self.output_tokens += usage.output_tokens or 0
        self.cache_creation_input_tokens += getattr(usage, "cache_creation_input_tokens", 0) or 0
        self.cache_read_input_tokens += getattr(usage, "cache_read_input_tokens", 0) or 0
        self.requests += 1
        return self

    @property
    def total_input_tokens(self) -> int:
        """Every input token billed, cached or not."""
        return (
            self.input_tokens
            + self.cache_creation_input_tokens
            + self.cache_read_input_tokens
        )

    def cost_usd(self) -> float:
        """Apply all four rates separately.

        Charging everything at the base input rate understates cache writes by
        25 percent and overstates cache reads by a factor of ten.
        """
        return (
            self.input_tokens * PRICE_INPUT
            + self.output_tokens * PRICE_OUTPUT
            + self.cache_creation_input_tokens * PRICE_CACHE_WRITE_5M
            + self.cache_read_input_tokens * PRICE_CACHE_READ
        ) / 1_000_000

    def as_dict(self) -> dict:
        data = asdict(self)
        data["total_input_tokens"] = self.total_input_tokens
        data["cost_usd"] = round(self.cost_usd(), 6)
        return data


class BudgetExceeded(RuntimeError):
    """Raised when the experiment reaches its spending ceiling."""


class BudgetGuard:
    """Stops the experiment once cumulative spend reaches a ceiling."""

    def __init__(self, ceiling_usd: float):
        self.ceiling_usd = ceiling_usd
        self.spent_usd = 0.0

    def record(self, cost_usd: float) -> None:
        self.spent_usd += cost_usd

    @property
    def remaining_usd(self) -> float:
        return self.ceiling_usd - self.spent_usd

    def check(self) -> None:
        if self.spent_usd >= self.ceiling_usd:
            raise BudgetExceeded(
                f"Spent ${self.spent_usd:.2f} of the ${self.ceiling_usd:.2f} ceiling."
            )
