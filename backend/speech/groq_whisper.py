"""Groq Whisper speech-to-text (D-003: approved for adult developer testing only).

Audio is sent from memory as a multipart upload and never written to disk. Errors carry status
codes and class names only: response bodies may echo the speaker's words.
"""

import os
from collections.abc import Mapping
from dataclasses import dataclass, field

import httpx

from backend.speech.base import SpeechError

GROQ_BASE_URL = "https://api.groq.com/openai/v1"


@dataclass(frozen=True)
class GroqSpeechConfig:
    api_key: str = field(repr=False)
    stt_model: str
    timeout_seconds: float = 15.0

    @classmethod
    def from_env(cls, env: Mapping[str, str] = os.environ) -> "GroqSpeechConfig":
        missing = [n for n in ("GROQ_API_KEY", "GROQ_STT_MODEL") if not env.get(n)]
        if missing:
            raise ValueError(f"missing settings: {', '.join(missing)}")
        return cls(api_key=env["GROQ_API_KEY"], stt_model=env["GROQ_STT_MODEL"])


class GroqWhisper:
    def __init__(self, config: GroqSpeechConfig, http: httpx.AsyncClient | None = None) -> None:
        self._config = config
        self._http = http or httpx.AsyncClient(base_url=GROQ_BASE_URL)

    async def aclose(self) -> None:
        await self._http.aclose()

    async def transcribe(self, wav: bytes) -> str:
        if not wav:
            raise SpeechError("no audio")
        try:
            response = await self._http.post(
                "/audio/transcriptions",
                files={"file": ("speech.wav", wav, "audio/wav")},
                data={
                    "model": self._config.stt_model,
                    "language": "en",
                    "response_format": "json",
                    "temperature": "0",
                },
                headers={"Authorization": f"Bearer {self._config.api_key}"},
                timeout=self._config.timeout_seconds,
            )
        except httpx.HTTPError as exc:
            raise SpeechError(f"groq stt request failed: {type(exc).__name__}") from None
        if response.status_code != 200:
            raise SpeechError(f"groq stt http {response.status_code}")
        try:
            text = response.json()["text"]
        except (ValueError, KeyError, TypeError):
            raise SpeechError("groq stt malformed response") from None
        if not isinstance(text, str):
            raise SpeechError("groq stt malformed response")
        return text.strip()
