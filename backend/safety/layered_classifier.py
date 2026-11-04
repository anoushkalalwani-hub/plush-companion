"""Three-layer input classifier (D-005).

Rules, moderation, and an LLM judge each look at the input independently. The most restrictive
result wins, and any layer failing makes the whole classifier unavailable, which the
conversation manager turns into a fallback.
"""

from dataclasses import dataclass

from backend.llm.base import JudgeModel
from backend.safety.classifier import (
    APPROVED_CATEGORIES,
    SEVERITY_ORDER,
    SPECIAL_HANDLING_CATEGORIES,
    Category,
    ClassificationResult,
    ClassificationUnavailable,
    RiskLevel,
)
from backend.safety.concurrency import run_both
from backend.safety.judge_prompts import CLASSIFICATION_SCHEMA, CLASSIFIER_INSTRUCTIONS
from backend.safety.moderation import ModerationProvider, ModerationResult
from backend.safety.rules import match_input_rules


@dataclass(frozen=True)
class LayerResults:
    """What each layer said before merging. Used by the adversarial suite's live report."""

    rule_hits: frozenset[Category]
    moderation: ModerationResult
    judged: ClassificationResult


class LayeredClassifier:
    def __init__(self, *, moderation: ModerationProvider, judge: JudgeModel) -> None:
        self._moderation = moderation
        self._judge = judge

    async def classify(self, text: str) -> ClassificationResult:
        result, _ = await self.classify_with_layers(text)
        return result

    async def classify_with_layers(self, text: str) -> tuple[ClassificationResult, LayerResults]:
        rule_hits = match_input_rules(text)
        try:
            moderation, raw = await run_both(
                self._moderation.moderate(text),
                self._judge.judge(CLASSIFIER_INSTRUCTIONS, text, CLASSIFICATION_SCHEMA),
            )
            if not isinstance(moderation, ModerationResult):
                raise TypeError("malformed moderation result")
            judged = ClassificationResult.model_validate(raw)
        except Exception as exc:
            # Class name only, and no exception chaining: messages may contain the input.
            raise ClassificationUnavailable(f"layer failed: {type(exc).__name__}") from None

        layers = LayerResults(rule_hits=rule_hits, moderation=moderation, judged=judged)
        return _merge(judged, _flags(rule_hits, moderation)), layers


def _flags(rule_hits: frozenset[Category], moderation: ModerationResult) -> set[Category]:
    flags = set(rule_hits)
    if moderation.flagged:
        flags |= moderation.categories or {Category.UNCLASSIFIABLE}
    # A flag can never mean "approved": anything outside the restricted list is unclassifiable.
    return {c if c in SEVERITY_ORDER else Category.UNCLASSIFIABLE for c in flags}


def _merge(judged: ClassificationResult, flags: set[Category]) -> ClassificationResult:
    category, risk_level = judged.category, judged.risk_level
    if flags:
        candidates = flags | ({judged.category} - APPROVED_CATEGORIES)
        category = min(candidates, key=SEVERITY_ORDER.index)
        risk_level = RiskLevel.HIGH
    special = judged.requires_special_handling or bool(
        (flags | {category}) & SPECIAL_HANDLING_CATEGORIES
    )
    return ClassificationResult(
        category=category,
        risk_level=risk_level,
        requires_special_handling=special,
        confidence=judged.confidence,
    )
