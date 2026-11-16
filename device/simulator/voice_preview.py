"""Hear Winston's greeting in each candidate Kokoro voice, one after another (D-025).

    uv run --group voice --env-file .env python -m device.simulator.voice_preview
    ... python -m device.simulator.voice_preview am_fenrir bm_george   # only these

Speaks only the WINSTON_GREETING template. Runs locally; audio plays from memory.
"""

import asyncio
import sys
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import replace

from backend.safety.templates import WINSTON_GREETING
from backend.speech.base import SpeechError
from backend.speech.kokoro_local import KokoroConfig, KokoroTTS, load_engine

# Deeper or older-sounding English voices first, then the current default and two others.
CANDIDATES = ("am_fenrir", "bm_george", "am_onyx", "bm_fable", "am_michael", "am_puck")


async def preview(
    voices: Sequence[str],
    synthesize_for: Callable[[str], Awaitable[bytes]],
    play: Callable[[bytes], Awaitable[None]],
) -> list[str]:
    """Play the greeting in each voice; return the voices that failed."""
    failed = []
    for number, voice in enumerate(voices, start=1):
        print(f"[{number}/{len(voices)}] {voice}")
        try:
            await play(await synthesize_for(voice))
        except SpeechError as exc:
            print(f"    could not play {voice}: {exc}")
            failed.append(voice)
        await asyncio.sleep(0.6)
    return failed


async def _main(voices: Sequence[str]) -> int:
    import os

    from device.audio.devices import device_from_text
    from device.audio.playback import player_for

    play_wav = player_for(device_from_text(os.environ.get("AUDIO_OUTPUT_DEVICE")))

    try:
        config = KokoroConfig.from_env()
        print("Loading Kokoro...")
        engine = load_engine(config)
    except (ValueError, SpeechError) as exc:
        print(f"Kokoro is not set up ({exc}). See docs/DEVELOPMENT.md.", file=sys.stderr)
        return 2

    async def synthesize_for(voice: str) -> bytes:
        return await KokoroTTS(replace(config, voice=voice), engine=engine).synthesize(
            WINSTON_GREETING.text
        )

    failed = await preview(voices, synthesize_for, play_wav)
    print("\nPick one with: --voice NAME  (or set KOKORO_VOICE in .env)")
    return 1 if failed else 0


def main(argv: list[str] | None = None) -> int:
    voices = (argv if argv is not None else sys.argv[1:]) or list(CANDIDATES)
    return asyncio.run(_main(voices))


if __name__ == "__main__":
    sys.exit(main())
