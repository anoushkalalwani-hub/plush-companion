"""Cartesia text-to-speech (D-024; D-003: adult developer testing only).

Only validated reply text or a predefined template reaches this adapter (invariant 4). Output
validation rejects < > [ ], so generated text cannot carry Cartesia's SSML-like tags. Audio is
returned as WAV in memory. Errors carry status codes only.
"""

import os
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field

import httpx

from backend.speech.base import SpeechError

CARTESIA_BASE_URL = "https://api.cartesia.ai"
CARTESIA_VERSION = "2026-08-14"
SAMPLE_RATE = 24000


@dataclass(frozen=True)
class CartesiaConfig:
    api_key: str = field(repr=False)
    model: str
    voice_id: str
    timeout_seconds: float = 20.0

    @classmethod
    def from_env(cls, env: Mapping[str, str] = os.environ) -> "CartesiaConfig":
        names = ("CARTESIA_API_KEY", "CARTESIA_MODEL", "CARTESIA_VOICE_ID")
        missing = [n for n in names if not env.get(n)]
        if missing:
            raise ValueError(f"missing settings: {', '.join(missing)}")
        return cls(
            api_key=env["CARTESIA_API_KEY"],
            model=env["CARTESIA_MODEL"],
            voice_id=env["CARTESIA_VOICE_ID"],
        )


class CartesiaTTS:
    def __init__(self, config: CartesiaConfig, http: httpx.AsyncClient | None = None) -> None:
        self._config = config
        self._http = http or httpx.AsyncClient(base_url=CARTESIA_BASE_URL)

    async def aclose(self) -> None:
        await self._http.aclose()

    async def synthesize(self, text: str) -> bytes:
        if not text.strip():
            raise SpeechError("tts input empty")
        try:
            response = await self._http.post(
                "/tts/bytes",
                json={
                    "model_id": self._config.model,
                    "transcript": text,
                    "voice": {"mode": "id", "id": self._config.voice_id},
                    "output_format": {
                        "container": "wav",
                        "encoding": "pcm_s16le",
                        "sample_rate": SAMPLE_RATE,
                    },
                    "language": "en",
                },
                headers={
                    "Authorization": f"Bearer {self._config.api_key}",
                    "Cartesia-Version": CARTESIA_VERSION,
                },
                timeout=self._config.timeout_seconds,
            )
        except httpx.HTTPError as exc:
            raise SpeechError(f"cartesia request failed: {type(exc).__name__}") from None
        if response.status_code != 200:
            raise SpeechError(f"cartesia http {response.status_code}")
        return response.content


Player = Callable[[bytes], Awaitable[None]]


class CartesiaSpeaker:
    def __init__(self, tts: CartesiaTTS, player: Player) -> None:
        self._tts = tts
        self._player = player

    async def speak(self, text: str) -> None:
        await self._player(await self._tts.synthesize(text))
