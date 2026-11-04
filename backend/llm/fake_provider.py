"""Offline provider used in fake mode. Makes no network calls."""

from collections.abc import Sequence

from backend.llm.base import GenerationConstraints, GenerationResult, Message


class FakeLLMProvider:
    def __init__(self, reply: str = "That's a great question! Let's find out together.") -> None:
        self._reply = reply

    async def generate(
        self, messages: Sequence[Message], constraints: GenerationConstraints
    ) -> GenerationResult:
        return GenerationResult(text=self._reply)
