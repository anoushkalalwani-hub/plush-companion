"""espeak-ng as the backup voice on Linux, including the Raspberry Pi (D-026).

Runs locally. The text goes in on stdin, never as an argument, so it cannot be read as
options. Nothing is written to disk.
"""

import asyncio

from backend.speech.base import SpeechError


class EspeakSpeaker:
    def __init__(self, voice: str | None = None, rate: int | None = None) -> None:
        self._options: list[str] = []
        if voice:
            self._options += ["-v", voice]
        if rate:
            self._options += ["-s", str(rate)]

    async def speak(self, text: str) -> None:
        try:
            process = await asyncio.create_subprocess_exec(
                "espeak-ng",
                *self._options,
                "--stdin",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
        except OSError as exc:
            raise SpeechError(f"espeak-ng unavailable: {type(exc).__name__}") from None
        await process.communicate(text.encode())
        if process.returncode != 0:
            raise SpeechError(f"espeak-ng exit {process.returncode}")
