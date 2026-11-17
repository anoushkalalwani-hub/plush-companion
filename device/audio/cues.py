"""Non-verbal sound cues for the simulator (D-022, D-026).

The thinking chime is two soft beeps generated in memory, so it works on macOS and on a
Raspberry Pi alike. It carries no words, so it needs no template review. Cues are best-effort:
a failure is ignored.
"""

import asyncio
import math
from array import array
from collections.abc import Awaitable, Callable

from device.audio.microphone import pcm_to_wav

TONE_RATE = 24000
_tasks: set[asyncio.Task] = set()


def thinking_tone_wav() -> bytes:
    samples = array("h")
    for frequency, seconds in ((880.0, 0.09), (0.0, 0.05), (1175.0, 0.12)):
        count = int(TONE_RATE * seconds)
        for i in range(count):
            fade = min(1.0, i / 240, (count - i) / 240)  # Short fades avoid clicks.
            value = math.sin(2 * math.pi * frequency * i / TONE_RATE) if frequency else 0.0
            samples.append(int(value * fade * 6000))
    return pcm_to_wav(samples.tobytes(), TONE_RATE)


async def play_thinking_cue(player: Callable[[bytes], Awaitable[None]]) -> None:
    """Start the chime and return immediately; never raises."""

    async def run() -> None:
        try:
            await player(thinking_tone_wav())
        except Exception:
            pass

    task = asyncio.create_task(run())
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)
