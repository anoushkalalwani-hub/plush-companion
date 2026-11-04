"""Provider-neutral LLM interface (PRD §6.1).

There is deliberately no tool, function-calling, or browsing parameter.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol


class Role(StrEnum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


@dataclass(frozen=True)
class Message:
    role: Role
    content: str


@dataclass(frozen=True)
class GenerationConstraints:
    max_output_tokens: int
    # Providers pass this to their HTTP client. The conversation manager also enforces it.
    timeout_seconds: float


@dataclass(frozen=True)
class GenerationResult:
    text: str


class LLMError(Exception):
    """A provider failed in a known way (HTTP error, refusal, bad response)."""


class LLMProvider(Protocol):
    async def generate(
        self, messages: Sequence[Message], constraints: GenerationConstraints
    ) -> GenerationResult: ...
