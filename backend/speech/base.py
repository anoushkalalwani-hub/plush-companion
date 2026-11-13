"""Speech interfaces (M3). Provider code lives in adapters next to this file.

Privacy rules (AGENTS.md): audio stays in memory and is never written to disk; transcripts and
spoken text never appear in logs or error messages. Only validated text or a predefined
template may be spoken (pipeline invariant 4).
"""

from typing import Protocol


class SpeechError(Exception):
    """A speech provider failed. The message carries status codes or class names only."""


class SpeechToText(Protocol):
    async def transcribe(self, wav: bytes) -> str:
        """Return the words in a WAV clip (possibly empty), or raise SpeechError."""
        ...


class Speaker(Protocol):
    async def speak(self, text: str) -> None:
        """Say text aloud and return when finished, or raise SpeechError."""
        ...
