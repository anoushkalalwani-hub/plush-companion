"""Input safety classification (PRD §7.2).

M1 ships only the interface and a stub that is always unavailable. The real classifier, built
from the layers proposed in D-005, arrives in M2.
"""

from enum import StrEnum
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field


class Category(StrEnum):
    # Approved categories (PRD §6.3)
    GENERAL_KNOWLEDGE = "general_knowledge"
    EDUCATION = "education"
    CREATIVE_WRITING = "creative_writing"
    ANIMALS_AND_NATURE = "animals_and_nature"
    GAMES = "games"
    EVERYDAY_CONVERSATION = "everyday_conversation"
    EMOTIONAL_SUPPORT = "emotional_support"
    SOCIAL_SITUATIONS = "social_situations"

    # Restricted categories (PRD §6.3)
    MEDICAL = "medical"
    PERSONAL_INFORMATION = "personal_information"
    FAMILY_CONFLICT = "family_conflict"
    BULLYING_AND_MISTREATMENT = "bullying_and_mistreatment"
    ABUSE_OR_UNSAFE = "abuse_or_unsafe"
    DANGEROUS_ACTIVITIES = "dangerous_activities"
    SEXUAL_CONTENT = "sexual_content"
    SELF_HARM = "self_harm"
    SECRECY_REQUEST = "secrecy_request"
    ILLEGAL_ACTIVITY = "illegal_activity"

    UNCLASSIFIABLE = "unclassifiable"


APPROVED_CATEGORIES = frozenset(
    {
        Category.GENERAL_KNOWLEDGE,
        Category.EDUCATION,
        Category.CREATIVE_WRITING,
        Category.ANIMALS_AND_NATURE,
        Category.GAMES,
        Category.EVERYDAY_CONVERSATION,
        Category.EMOTIONAL_SUPPORT,
        Category.SOCIAL_SITUATIONS,
    }
)


class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ClassificationResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    category: Category
    risk_level: RiskLevel
    requires_special_handling: bool
    confidence: float = Field(ge=0.0, le=1.0)


class ClassificationUnavailable(Exception):
    """The classifier could not produce a result. Callers must fail closed."""


class Classifier(Protocol):
    async def classify(self, text: str) -> ClassificationResult: ...


class StubClassifier:
    """M1 default: always unavailable, so every message falls back."""

    async def classify(self, text: str) -> ClassificationResult:
        raise ClassificationUnavailable("input classifier not implemented (M2)")
