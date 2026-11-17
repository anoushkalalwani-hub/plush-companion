"""Play WAV audio from memory on the chosen speaker (D-022, D-026). Nothing is written to disk.

USB speakers often accept only 44.1 or 48 kHz. If the speaker refuses the audio's own rate, the
audio is resampled to the speaker's preferred rate and played again.
"""

import asyncio
import struct
from array import array
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from backend.speech.base import SpeechError
from device.audio.devices import Device, default_rate


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


def resample_pcm16(pcm: bytes, channels: int, src_rate: int, dst_rate: int) -> bytes:
    """Linear-interpolation resampling of interleaved 16-bit PCM."""
    if src_rate == dst_rate:
        return pcm
    samples = array("h")
    samples.frombytes(pcm[: len(pcm) - len(pcm) % (2 * channels)])
    frames = len(samples) // channels
    if frames == 0:
        return b""
    out_frames = max(1, round(frames * dst_rate / src_rate))
    step = src_rate / dst_rate
    out = array("h", bytes(2 * out_frames * channels))
    for i in range(out_frames):
        position = i * step
        left = min(int(position), frames - 1)
        right = min(left + 1, frames - 1)
        fraction = position - left
        for c in range(channels):
            a, b = samples[left * channels + c], samples[right * channels + c]
            out[i * channels + c] = round(a + (b - a) * fraction)
    return out.tobytes()


def _play_blocking(audio: Audio, device: Device) -> None:
    import sounddevice  # Optional "voice" dependency group.

    if audio.sample_width != 2:
        raise SpeechError("unsupported sample width")

    def play(pcm: bytes, rate: int) -> None:
        with sounddevice.RawOutputStream(
            samplerate=rate, channels=audio.channels, dtype="int16", device=device
        ) as stream:
            stream.write(pcm)

    try:
        play(audio.pcm, audio.sample_rate)
    except sounddevice.PortAudioError:
        rate = default_rate(device, "output")
        if rate == audio.sample_rate:
            raise SpeechError("speaker refused the audio") from None
        try:
            play(resample_pcm16(audio.pcm, audio.channels, audio.sample_rate, rate), rate)
        except sounddevice.PortAudioError:
            raise SpeechError("speaker refused the audio") from None


async def play_wav(data: bytes, device: Device = None) -> None:
    await asyncio.to_thread(_play_blocking, decode_wav(data), device)


Player = Callable[[bytes], Awaitable[None]]


def player_for(device: Device) -> Player:
    async def play(data: bytes) -> None:
        await play_wav(data, device)

    return play
