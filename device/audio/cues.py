"""Non-verbal sound cues for the laptop simulator (D-022).

A short system sound plays while the pipeline works, so the wait doesn't feel dead. It carries
no words, so it needs no template review. Cues are best-effort: a missing player is ignored.
"""

import asyncio

THINKING_SOUND = "/System/Library/Sounds/Tink.aiff"


async def play_thinking_cue() -> None:
    """Start the cue and return immediately; never raises."""
    try:
        await asyncio.create_subprocess_exec(
            "afplay",
            THINKING_SOUND,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
    except Exception:
        pass
