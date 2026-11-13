"""Voice selection for the laptop simulator (D-022, D-023)."""

from backend.speech.base import Speaker, SpeechError


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
            print(f"  (Groq voice unavailable: {exc}; using the macOS voice)")
            await self._backup.speak(text)
