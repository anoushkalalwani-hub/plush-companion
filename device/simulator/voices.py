"""Voice selection for the simulator (D-022 to D-026)."""

import shutil
import sys

from backend.speech.base import Speaker, SpeechError
from backend.speech.espeak import EspeakSpeaker
from backend.speech.macos_say import MacSaySpeaker


class NoVoice:
    async def speak(self, text: str) -> None:
        raise SpeechError("no backup voice installed")


def backup_speaker(voice: str | None = None, rate: int | None = None) -> Speaker:
    """macOS `say` on a Mac, espeak-ng on Linux (Raspberry Pi) when installed."""
    if sys.platform == "darwin":
        return MacSaySpeaker(voice=voice, rate=rate)
    if shutil.which("espeak-ng"):
        return EspeakSpeaker(voice=voice, rate=rate)
    return NoVoice()


class FallbackSpeaker:
    """Use the main voice; if it fails, the backup voice says the same text."""

    def __init__(self, main: Speaker, backup: Speaker) -> None:
        self._main = main
        self._backup = backup

    async def speak(self, text: str) -> None:
        try:
            await self._main.speak(text)
        except SpeechError as exc:
            # Status codes and class names only, never the text.
            print(f"  (voice unavailable: {exc}; using the backup voice)")
            await self._backup.speak(text)
