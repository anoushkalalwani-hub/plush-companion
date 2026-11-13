"""macOS `say` speaker, with the subprocess replaced. Nothing is spoken."""

import asyncio

import pytest

from backend.speech.base import SpeechError
from backend.speech.macos_say import MacSaySpeaker


class FakeProcess:
    def __init__(self, returncode: int) -> None:
        self.returncode = returncode

    async def wait(self) -> int:
        return self.returncode


@pytest.fixture
def spawned(monkeypatch):
    calls: list[tuple] = []
    result = {"returncode": 0, "exc": None}

    async def fake_exec(*args, **kwargs):
        calls.append(args)
        if result["exc"]:
            raise result["exc"]
        return FakeProcess(result["returncode"])

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)
    return calls, result


async def test_text_is_passed_as_an_argument_after_double_dash(spawned):
    calls, _ = spawned
    await MacSaySpeaker().speak("-v Bad -o /tmp/x hello")
    [args] = calls
    assert args[0] == "say"
    assert args[-2:] == ("--", "-v Bad -o /tmp/x hello")
    assert "-o" not in args[:-1]


async def test_voice_and_rate_are_optional(spawned):
    calls, _ = spawned
    await MacSaySpeaker(voice="Samantha", rate=170).speak("hi")
    assert calls[0] == ("say", "-v", "Samantha", "-r", "170", "--", "hi")


async def test_failed_say_is_a_speech_error(spawned):
    _, result = spawned
    result["returncode"] = 1
    with pytest.raises(SpeechError, match="exit 1"):
        await MacSaySpeaker().speak("hi")


async def test_missing_say_is_a_speech_error(spawned):
    _, result = spawned
    result["exc"] = FileNotFoundError("say")
    with pytest.raises(SpeechError):
        await MacSaySpeaker().speak("hi")
