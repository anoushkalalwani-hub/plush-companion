"""Play WAV audio from memory on the laptop speakers (D-022). Nothing is written to disk."""

import asyncio
import struct
from dataclasses import dataclass

from backend.speech.base import SpeechError


@dataclass(frozen=True)
class Audio:
    pcm: bytes
    sample_rate: int
    channels: int
    sample_width: int


def decode_wav(data: bytes) -> Audio:
    """Read a PCM WAV in memory. Tolerates streaming headers whose sizes are 0xFFFFFFFF."""
    if len(data) < 12 or data[:4] != b"RIFF" or data[8:12] != b"WAVE":
        raise SpeechError("not a wav file")
    position, fmt = 12, None
    while position + 8 <= len(data):
        chunk_id = data[position : position + 4]
        (size,) = struct.unpack_from("<I", data, position + 4)
        body = position + 8
        if chunk_id == b"fmt ":
            audio_format, channels, rate = struct.unpack_from("<HHI", data, body)
            (bits,) = struct.unpack_from("<H", data, body + 14)
            if audio_format != 1:
                raise SpeechError("wav is not pcm")
            fmt = (rate, channels, bits // 8)
        elif chunk_id == b"data":
            if fmt is None:
                raise SpeechError("wav data before format")
            end = len(data) if size == 0xFFFFFFFF else min(len(data), body + size)
            rate, channels, width = fmt
            return Audio(data[body:end], rate, channels, width)
        if size == 0xFFFFFFFF:
            break
        position = body + size + (size % 2)
    raise SpeechError("wav has no audio data")


def _play_blocking(audio: Audio) -> None:
    import sounddevice  # Optional "voice" dependency group.

    dtype = {1: "uint8", 2: "int16", 4: "int32"}.get(audio.sample_width)
    if dtype is None:
        raise SpeechError("unsupported sample width")
    with sounddevice.RawOutputStream(
        samplerate=audio.sample_rate, channels=audio.channels, dtype=dtype
    ) as stream:
        stream.write(audio.pcm)


async def play_wav(data: bytes) -> None:
    await asyncio.to_thread(_play_blocking, decode_wav(data))
