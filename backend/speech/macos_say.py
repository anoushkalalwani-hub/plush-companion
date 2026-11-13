"""macOS `say` as the laptop simulator's speaker (D-022).

Runs locally: no audio leaves the laptop and nothing is written to disk. The text is passed as
a single argument after `--`, never through a shell, so it cannot be read as options.
"""

import asyncio

from backend.speech.base import SpeechError


class MacSaySpeaker:
    def __init__(self, voice: str | None = None, rate: int | None = None) -> None:
        self._options: list[str] = []
        if voice:
            self._options += ["-v", voice]
        if rate:
            self._options += ["-r", str(rate)]

    async def speak(self, text: str) -> None:
        try:
            process = await asyncio.create_subprocess_exec(
                "say",
                *self._options,
                "--",
                text,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
        except OSError as exc:
            raise SpeechError(f"say unavailable: {type(exc).__name__}") from None
        code = await process.wait()
        if code != 0:
            raise SpeechError(f"say exit {code}")
