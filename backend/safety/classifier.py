"""Input safety classification (PRD §7.2): shared types and the M1 stub.

The real classifier is LayeredClassifier in layered_classifier.py (D-005).
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


# Sensitive disclosures (PRD §7.4 examples): always special handling, which blocks and purges
# session context (D-015).
SPECIAL_HANDLING_CATEGORIES = frozenset(
    {
        Category.ABUSE_OR_UNSAFE,
        Category.BULLYING_AND_MISTREATMENT,
        Category.SELF_HARM,
        Category.PERSONAL_INFORMATION,
    }
)

# Which restricted label wins when layers flag several. Every one of these blocks; the order only
# decides the logged category and, once D-004 templates exist, which template is used.
SEVERITY_ORDER = (
    Category.SELF_HARM,
    Category.ABUSE_OR_UNSAFE,
    Category.SEXUAL_CONTENT,
    Category.PERSONAL_INFORMATION,
    Category.BULLYING_AND_MISTREATMENT,
    Category.DANGEROUS_ACTIVITIES,
    Category.ILLEGAL_ACTIVITY,
    Category.MEDICAL,
    Category.SECRECY_REQUEST,
    Category.FAMILY_CONFLICT,
    Category.UNCLASSIFIABLE,
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
