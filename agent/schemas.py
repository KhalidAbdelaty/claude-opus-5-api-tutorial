"""The machine-readable report the agent has to produce."""

from typing import Literal

from pydantic import BaseModel, Field, field_validator

Status = Literal["fixed", "partial", "not_fixed"]
Confidence = Literal["low", "medium", "high"]


class RepairReport(BaseModel):
    """What Claude concluded. Runtime facts are measured by the runner instead."""

    status: Status = Field(description="fixed, partial, or not_fixed.")
    root_cause: str = Field(description="The underlying defect, not the visible symptom.")
    files_inspected: list[str] = Field(description="Repository-relative paths that were read.")
    files_changed: list[str] = Field(description="Repository-relative paths that were edited.")
    fix_summary: str = Field(description="What was changed and why it addresses the root cause.")
    tests_before: str = Field(description="Test outcome observed before patching.")
    tests_after: str = Field(description="Test outcome observed after patching.")
    remaining_risks: list[str] = Field(description="Edge cases or follow-up work still open.")
    confidence: Confidence = Field(description="low, medium, or high.")

    @field_validator("status", "confidence", mode="before")
    @classmethod
    def _normalize_case(cls, value):
        """Enum capitalization is not guaranteed, so fold it before validating."""
        if isinstance(value, str):
            return value.strip().lower().replace(" ", "_").replace("-", "_")
        return value
