"""Laptop voice simulator turn logic, with fake speech and a fake conversation manager."""

import asyncio
import wave
from dataclasses import dataclass, field
from io import BytesIO

from backend.conversation.manager import FALLBACK_REPLY, Reply, ResponseSource
from backend.speech.base import SpeechError
from device.audio.microphone import pcm_to_wav
from device.simulator.chat import text_turn, voice_turn

SESSION = object()


@dataclass
class FakeManager:
    reply: Reply = field(
        default_factory=lambda: Reply("Bees eat nectar.", ResponseSource.GENERATED)
    )
    seen: list[str] = field(default_factory=list)

    async def handle_message(self, session, text):
        self.seen.append(text)
        return self.reply


@dataclass
class FakeSpeaker:
    spoken: list[str] = field(default_factory=list)
    exc: Exception | None = None

    async def speak(self, text):
        if self.exc:
            raise self.exc
        self.spoken.append(text)


@dataclass
class FakeSTT:
    text: str = "what do bees eat"
    exc: Exception | None = None
    delay: float = 0.0

    async def transcribe(self, wav):
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.exc:
            raise self.exc
        return self.text


async def test_voice_turn_speaks_only_the_managers_reply():
    manager, speaker = FakeManager(), FakeSpeaker()
    turn = await voice_turn(b"wav", FakeSTT(), manager, SESSION, speaker)
    assert manager.seen == ["what do bees eat"]
    assert speaker.spoken == ["Bees eat nectar."]
    assert turn.heard == "what do bees eat" and turn.source is ResponseSource.GENERATED


async def test_speech_to_text_failure_speaks_the_fallback_without_the_pipeline():
    manager, speaker = FakeManager(), FakeSpeaker()
    turn = await voice_turn(
        b"wav", FakeSTT(exc=SpeechError("groq http 429")), manager, SESSION, speaker
    )
    assert manager.seen == []
    assert speaker.spoken == [FALLBACK_REPLY.text]
    assert turn.source is ResponseSource.FALLBACK
    assert "SpeechError" in turn.note


async def test_speech_to_text_timeout_falls_back():
    manager, speaker = FakeManager(), FakeSpeaker()
    turn = await voice_turn(
        b"wav", FakeSTT(delay=1.0), manager, SESSION, speaker, stt_timeout_seconds=0.01
    )
    assert manager.seen == [] and speaker.spoken == [FALLBACK_REPLY.text]
    assert "timeout" in turn.note


async def test_nothing_heard_speaks_nothing():
    manager, speaker = FakeManager(), FakeSpeaker()
    turn = await voice_turn(b"wav", FakeSTT(text="   "), manager, SESSION, speaker)
    assert manager.seen == [] and speaker.spoken == []
    assert turn.reply is None


async def test_manager_exception_falls_back():
    class Broken(FakeManager):
        async def handle_message(self, session, text):
            raise RuntimeError("why is the sky blue")

    speaker = FakeSpeaker()
    turn = await text_turn("hi", Broken(), SESSION, speaker)
    assert speaker.spoken == [FALLBACK_REPLY.text]
    assert "sky" not in turn.note


async def test_speaker_failure_is_reported_not_raised():
    speaker = FakeSpeaker(exc=SpeechError("say exit 1"))
    turn = await text_turn("hi", FakeManager(), SESSION, speaker)
    assert turn.reply == "Bees eat nectar."
    assert "speaker failed" in turn.note


def test_pcm_is_wrapped_as_16_bit_mono_wav_in_memory():
    pcm = b"\x00\x01" * 1600
    data = pcm_to_wav(pcm, sample_rate=16000)
    with wave.open(BytesIO(data)) as w:
        assert (w.getnchannels(), w.getsampwidth(), w.getframerate()) == (1, 2, 16000)
        assert w.readframes(w.getnframes()) == pcm


def test_simulator_without_groq_settings_exits_before_any_network_call(monkeypatch, capsys):
    from device.simulator.__main__ import main

    for name in (
        "GROQ_API_KEY",
        "GROQ_CHAT_MODEL",
        "GROQ_JUDGE_MODEL",
        "GROQ_MODERATION_MODEL",
        "GROQ_STT_MODEL",
    ):
        monkeypatch.delenv(name, raising=False)
    assert main(["--type"]) == 2
    assert "Missing Groq settings" in capsys.readouterr().err


def test_simulator_refuses_an_out_of_range_threshold():
    import pytest

    from device.simulator.__main__ import main

    with pytest.raises(SystemExit):
        main(["--type", "--threshold", "2"])
