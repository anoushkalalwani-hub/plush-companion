"""Output validation (PRD §7.5).

M1 ships only the interface and a stub that rejects everything. The real validator (D-006)
arrives in M2.
"""

from typing import Protocol

from pydantic import BaseModel, ConfigDict

from backend.safety.classifier import Category


class ValidationResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    passed: bool
    reason: str


class Validator(Protocol):
    async def validate(self, text: str, category: Category) -> ValidationResult: ...


class StubValidator:
    """M1 default: rejects every response, so generated text is never returned."""

    async def validate(self, text: str, category: Category) -> ValidationResult:
        return ValidationResult(passed=False, reason="validator_not_implemented")
