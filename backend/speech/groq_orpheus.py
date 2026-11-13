"""Groq Orpheus text-to-speech (preview model; D-003: adult developer testing only).

Only validated reply text or a predefined template reaches this adapter (invariant 4). Replies
are split at sentence boundaries to fit Orpheus's 200-character limit; splitting never changes
or drops words. Each request starts with one fixed vocal direction chosen here, never by the
model: replies containing brackets are rejected by output validation (D-018), so generated
text cannot steer the voice. Errors carry status codes only.
"""

import asyncio
import os
import re
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field

import httpx

from backend.speech.base import SpeechError

GROQ_BASE_URL = "https://api.groq.com/openai/v1"
MAX_INPUT_CHARS = 200


@dataclass(frozen=True)
class GroqVoiceConfig:
    api_key: str = field(repr=False)
    tts_model: str
    voice: str
    direction: str = "[warm]"
    timeout_seconds: float = 20.0

    @classmethod
    def from_env(cls, env: Mapping[str, str] = os.environ) -> "GroqVoiceConfig":
        names = ("GROQ_API_KEY", "GROQ_TTS_MODEL", "GROQ_TTS_VOICE")
        missing = [n for n in names if not env.get(n)]
        if missing:
            raise ValueError(f"missing settings: {', '.join(missing)}")
        return cls(
            api_key=env["GROQ_API_KEY"],
            tts_model=env["GROQ_TTS_MODEL"],
            voice=env["GROQ_TTS_VOICE"],
        )


def split_for_speech(text: str, limit: int) -> list[str]:
    """Split text into chunks of at most `limit` characters, keeping every word in order.

    Whole sentences are grouped where they fit; a sentence longer than the limit is split at
    spaces.
    """
    sentences = [s for s in re.split(r"(?<=[.!?])\s+", text.strip()) if s]
    pieces: list[str] = []
    for sentence in sentences:
        if len(sentence) <= limit:
            pieces.append(sentence)
            continue
        line = ""
        for word in sentence.split():
            candidate = f"{line} {word}".strip()
            if len(candidate) <= limit:
                line = candidate
            else:
                if line:
                    pieces.append(line)
                line = word[:limit]  # A single word longer than the limit is not realistic.
        if line:
            pieces.append(line)

    chunks: list[str] = []
    for piece in pieces:
        if chunks and len(chunks[-1]) + 1 + len(piece) <= limit:
            chunks[-1] = f"{chunks[-1]} {piece}"
        else:
            chunks.append(piece)
    return chunks


class GroqOrpheus:
    def __init__(self, config: GroqVoiceConfig, http: httpx.AsyncClient | None = None) -> None:
        self._config = config
        self._http = http or httpx.AsyncClient(base_url=GROQ_BASE_URL)

    @property
    def chunk_limit(self) -> int:
        return MAX_INPUT_CHARS - len(self._config.direction) - 1

    async def aclose(self) -> None:
        await self._http.aclose()

    async def synthesize(self, text: str) -> bytes:
        """Return WAV audio for one chunk of at most `chunk_limit` characters."""
        if not text or len(text) > self.chunk_limit:
            raise SpeechError("tts input empty or too long")
        try:
            response = await self._http.post(
                "/audio/speech",
                json={
                    "model": self._config.tts_model,
                    "voice": self._config.voice,
                    "input": f"{self._config.direction} {text}",
                    "response_format": "wav",
                },
                headers={"Authorization": f"Bearer {self._config.api_key}"},
                timeout=self._config.timeout_seconds,
            )
        except httpx.HTTPError as exc:
            raise SpeechError(f"groq tts request failed: {type(exc).__name__}") from None
        if response.status_code != 200:
            raise SpeechError(f"groq tts http {response.status_code}")
        return response.content


Player = Callable[[bytes], Awaitable[None]]


class GroqVoiceSpeaker:
    """Speaks text with Groq Orpheus. All chunks are synthesized before any is played, so a
    failure leaves nothing half-said and a backup voice can say the whole reply."""

    def __init__(self, tts: GroqOrpheus, player: Player) -> None:
        self._tts = tts
        self._player = player

    async def speak(self, text: str) -> None:
        chunks = split_for_speech(text, self._tts.chunk_limit)
        audio = await asyncio.gather(*(self._tts.synthesize(c) for c in chunks))
        for wav in audio:
            await self._player(wav)
