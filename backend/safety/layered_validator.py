"""Three-part output validator (D-006).

Deterministic checks run first; if they pass, moderation and an LLM judge run concurrently. The
judge sees only the candidate reply and its category, never the conversation. Every part must
pass. Provider errors and malformed results propagate, and the conversation manager turns them
into a fallback.
"""

from backend.llm.base import JudgeModel
from backend.safety.classifier import Category
from backend.safety.concurrency import run_both
from backend.safety.judge_prompts import (
    CANDIDATE_REPLY_TAG,
    VALIDATION_SCHEMA,
    VALIDATOR_INSTRUCTIONS,
    ValidatorVerdict,
    delimit,
)
from backend.safety.moderation import ModerationProvider, ModerationResult
from backend.safety.output_rules import check_output
from backend.safety.validator import ValidationResult


class LayeredValidator:
    def __init__(self, *, moderation: ModerationProvider, judge: JudgeModel) -> None:
        self._moderation = moderation
        self._judge = judge

    async def validate(self, text: str, category: Category) -> ValidationResult:
        if reason := check_output(text):
            return ValidationResult(passed=False, reason=reason)

        content = f"Conversation category: {category.value}\n\n{delimit(CANDIDATE_REPLY_TAG, text)}"
        moderation, raw = await run_both(
            self._moderation.moderate(text),
            self._judge.judge(VALIDATOR_INSTRUCTIONS, content, VALIDATION_SCHEMA),
        )
        if not isinstance(moderation, ModerationResult):
            raise TypeError("malformed moderation result")
        verdict = ValidatorVerdict.model_validate(raw)

        if moderation.flagged:
            return ValidationResult(passed=False, reason="moderation_flagged")
        if not verdict.passed or verdict.failed_checks:
            checks = ",".join(sorted(verdict.failed_checks))
            return ValidationResult(
                passed=False, reason=f"judge_rejected:{checks}" if checks else "judge_rejected"
            )
        return ValidationResult(passed=True, reason="ok")
