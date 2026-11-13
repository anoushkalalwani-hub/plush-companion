"""Push-to-talk microphone capture for the laptop simulator (D-022).

Audio stays in memory: it is captured into a buffer, wrapped as WAV with the standard library,
and never written to disk.
"""

import sys
import wave
from io import BytesIO

SAMPLE_RATE = 16000  # Whisper resamples to 16 kHz anyway.
MAX_SECONDS = 15.0


def pcm_to_wav(pcm: bytes, sample_rate: int = SAMPLE_RATE) -> bytes:
    """Wrap 16-bit mono PCM in a WAV header, in memory."""
    buffer = BytesIO()
    with wave.open(buffer, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        w.writeframes(pcm)
    return buffer.getvalue()


def record_until_enter(sample_rate: int = SAMPLE_RATE, max_seconds: float = MAX_SECONDS) -> bytes:
    """Record 16-bit mono PCM until the user presses Enter. Audio past max_seconds is dropped."""
    import sounddevice  # Optional "voice" dependency group; only needed for spoken input.

    limit = int(sample_rate * max_seconds) * 2
    chunks: list[bytes] = []
    size = 0

    def on_audio(data, frames, time, status) -> None:
        nonlocal size
        if size < limit:
            chunk = bytes(data)[: limit - size]
            chunks.append(chunk)
            size += len(chunk)

    with sounddevice.RawInputStream(
        samplerate=sample_rate, channels=1, dtype="int16", callback=on_audio
    ):
        sys.stdin.readline()
    if size >= limit:
        print(f"  (stopped listening after {max_seconds:.0f} seconds)")
    return b"".join(chunks)
