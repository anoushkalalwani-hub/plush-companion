"""Local Kokoro text-to-speech (D-025): runs on this machine, no key, nothing sent anywhere.

Kokoro-82M (Apache 2.0) via the kokoro-onnx package (MIT), in the optional "voice" dependency
group. Only validated reply text or a predefined template reaches it (invariant 4). Audio is
returned as WAV in memory and never written to disk. Errors carry class names only.
"""

import asyncio
import os
import struct
import wave
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Protocol

from backend.speech.base import SpeechError


@dataclass(frozen=True)
class KokoroConfig:
    model_path: str
    voices_path: str
    voice: str
    speed: float = 1.0

    @classmethod
    def from_env(cls, env: Mapping[str, str] = os.environ) -> "KokoroConfig":
        names = ("KOKORO_MODEL_PATH", "KOKORO_VOICES_PATH", "KOKORO_VOICE")
        missing = [n for n in names if not env.get(n)]
        if missing:
            raise ValueError(f"missing settings: {', '.join(missing)}")
        return cls(
            model_path=env["KOKORO_MODEL_PATH"],
            voices_path=env["KOKORO_VOICES_PATH"],
            voice=env["KOKORO_VOICE"],
        )

    @property
    def lang(self) -> str:
        # Kokoro voice names start with a for American English and b for British English.
        return "en-gb" if self.voice.startswith("b") else "en-us"


class Engine(Protocol):
    def create(self, text: str, voice: str, speed: float, lang: str): ...


def float_to_wav(samples: Sequence[float], sample_rate: int) -> bytes:
    """Convert float samples in [-1, 1] to 16-bit mono WAV in memory, clipping out-of-range."""
    pcm = struct.pack(
        f"<{len(samples)}h", *(int(max(-1.0, min(1.0, float(x))) * 32767) for x in samples)
    )
    buffer = BytesIO()
    with wave.open(buffer, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        w.writeframes(pcm)
    return buffer.getvalue()


def load_engine(config: KokoroConfig) -> Engine:
    for path, what in ((config.model_path, "model"), (config.voices_path, "voices")):
        if not Path(path).is_file():
            raise SpeechError(f"kokoro {what} file not found")
    from kokoro_onnx import Kokoro  # Optional "voice" dependency group.

    return Kokoro(config.model_path, config.voices_path)


class KokoroTTS:
    def __init__(self, config: KokoroConfig, engine: Engine | None = None) -> None:
        self._config = config
        self._engine = engine or load_engine(config)

    async def synthesize(self, text: str) -> bytes:
        if not text.strip():
            raise SpeechError("tts input empty")
        try:
            samples, rate = await asyncio.to_thread(
                self._engine.create,
                text,
                voice=self._config.voice,
                speed=self._config.speed,
                lang=self._config.lang,
            )
        except Exception as exc:
            raise SpeechError(f"kokoro failed: {type(exc).__name__}") from None
        return await asyncio.to_thread(float_to_wav, samples, rate)


Player = Callable[[bytes], Awaitable[None]]


class KokoroSpeaker:
    def __init__(self, tts: KokoroTTS, player: Player) -> None:
        self._tts = tts
        self._player = player

    async def speak(self, text: str) -> None:
        await self._player(await self._tts.synthesize(text))
