"""WAV decoding for playback, and the simulator's voice fallback. Nothing is played."""

import struct
from dataclasses import dataclass, field

from backend.speech.base import SpeechError
from device.audio.microphone import pcm_to_wav
from device.audio.playback import decode_wav
from device.simulator.voices import FallbackSpeaker


def test_decodes_a_standard_wav():
    pcm = b"\x01\x00\x02\x00" * 10
    audio = decode_wav(pcm_to_wav(pcm, 24000))
    assert (audio.sample_rate, audio.channels, audio.sample_width) == (24000, 1, 2)
    assert audio.pcm == pcm


def test_decodes_a_streaming_wav_with_unknown_data_size():
    pcm = b"\x05\x00" * 8
    header = bytearray(pcm_to_wav(pcm, 24000)[:44])
    struct.pack_into("<I", header, 4, 0xFFFFFFFF)
    struct.pack_into("<I", header, 40, 0xFFFFFFFF)
    audio = decode_wav(bytes(header) + pcm)
    assert audio.pcm == pcm and audio.sample_rate == 24000


def test_rejects_non_wav():
    import pytest

    with pytest.raises(SpeechError):
        decode_wav(b"not audio at all")


@dataclass
class FakeSpeaker:
    exc: Exception | None = None
    spoken: list[str] = field(default_factory=list)

    async def speak(self, text):
        if self.exc:
            raise self.exc
        self.spoken.append(text)


async def test_backup_voice_says_the_same_text_when_the_main_voice_fails(capsys):
    main, backup = FakeSpeaker(exc=SpeechError("groq tts http 429")), FakeSpeaker()
    await FallbackSpeaker(main, backup).speak("Woof! Hello.")
    assert backup.spoken == ["Woof! Hello."]
    assert "429" in capsys.readouterr().out


async def test_main_voice_is_used_when_it_works():
    main, backup = FakeSpeaker(), FakeSpeaker()
    await FallbackSpeaker(main, backup).speak("Woof!")
    assert main.spoken == ["Woof!"] and backup.spoken == []
