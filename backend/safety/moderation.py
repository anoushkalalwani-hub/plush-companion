"""Provider-neutral moderation interface (D-005 layer 2, D-006).

Adapters map their provider's flag names onto our categories. Anything flagged without a mapped
category is reported as UNCLASSIFIABLE, so every flag still blocks.
"""

from typing import Protocol

from pydantic import BaseModel, ConfigDict

from backend.safety.classifier import Category


class ModerationResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    flagged: bool
    categories: frozenset[Category] = frozenset()


class ModerationProvider(Protocol):
    async def moderate(self, text: str) -> ModerationResult: ...
