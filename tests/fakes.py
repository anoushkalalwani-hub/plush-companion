"""Scriptable test doubles for the pipeline's external stages.

These live in tests/ on purpose: an allow-everything classifier or validator must never be
importable from backend/.
"""

import asyncio
from dataclasses import dataclass, field

from backend.llm.base import GenerationConstraints, GenerationResult, Message
from backend.safety.classifier import Category, ClassificationResult, RiskLevel
from backend.safety.moderation import ModerationResult
from backend.safety.validator import ValidationResult

SAFE_EDUCATIONAL = ClassificationResult(
    category=Category.EDUCATION,
    risk_level=RiskLevel.LOW,
    requires_special_handling=False,
    confidence=0.99,
)


@dataclass
class ScriptedClassifier:
    result: object = SAFE_EDUCATIONAL
    exc: Exception | None = None
    delay: float = 0.0
    calls: list[str] = field(default_factory=list)

    async def classify(self, text: str) -> ClassificationResult:
        self.calls.append(text)
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.exc:
            raise self.exc
        return self.result  # type: ignore[return-value]


@dataclass
class ScriptedLLM:
    result: object = field(default_factory=lambda: GenerationResult(text="Bees make honey!"))
    exc: Exception | None = None
    delay: float = 0.0
    calls: list[list[Message]] = field(default_factory=list)

    async def generate(
        self, messages: list[Message], constraints: GenerationConstraints
    ) -> GenerationResult:
        self.calls.append(list(messages))
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.exc:
            raise self.exc
        return self.result  # type: ignore[return-value]


@dataclass
class ScriptedValidator:
    result: object = field(default_factory=lambda: ValidationResult(passed=True, reason="ok"))
    exc: Exception | None = None
    delay: float = 0.0
    calls: list[tuple[str, Category]] = field(default_factory=list)

    async def validate(self, text: str, category: Category) -> ValidationResult:
        self.calls.append((text, category))
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.exc:
            raise self.exc
        return self.result  # type: ignore[return-value]


SAFE_JUDGE_CLASSIFICATION = {
    "category": "education",
    "risk_level": "low",
    "requires_special_handling": False,
    "confidence": 0.95,
}
PASSING_JUDGE_VERDICT = {"passed": True, "failed_checks": []}


@dataclass
class ScriptedJudge:
    result: object = field(default_factory=lambda: dict(SAFE_JUDGE_CLASSIFICATION))
    exc: Exception | None = None
    calls: list[tuple[str, str]] = field(default_factory=list)

    async def judge(self, instructions: str, content: str, schema: dict) -> dict:
        self.calls.append((instructions, content))
        if self.exc:
            raise self.exc
        return self.result  # type: ignore[return-value]


@dataclass
class ScriptedModeration:
    result: object = field(default_factory=lambda: ModerationResult(flagged=False))
    exc: Exception | None = None
    calls: list[str] = field(default_factory=list)

    async def moderate(self, text: str) -> ModerationResult:
        self.calls.append(text)
        if self.exc:
            raise self.exc
        return self.result  # type: ignore[return-value]
