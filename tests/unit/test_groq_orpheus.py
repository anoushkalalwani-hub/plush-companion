"""Groq Orpheus text-to-speech against simulated HTTP, and reply splitting. No network."""

import json

import httpx
import pytest

from backend.speech.base import SpeechError
from backend.speech.groq_orpheus import (
    MAX_INPUT_CHARS,
    GroqOrpheus,
    GroqVoiceConfig,
    GroqVoiceSpeaker,
    split_for_speech,
)

CONFIG = GroqVoiceConfig(api_key="test-key", tts_model="orpheus-test", voice="troy")
REPLY = (
    "Woof! Bees drink sweet nectar from flowers and turn it into honey. They also eat pollen, "
    "which is full of protein for growing baby bees. A busy bee can visit hundreds of flowers "
    "in a single day, buzzing from one to the next. Do you have a favourite flower?"
)


def _tts(handler) -> GroqOrpheus:
    http = httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="https://example.test/openai/v1"
    )
    return GroqOrpheus(CONFIG, http=http)


def test_split_keeps_every_word_in_order_and_fits_the_limit():
    limit = MAX_INPUT_CHARS - len(CONFIG.direction) - 1
    chunks = split_for_speech(REPLY, limit)
    assert " ".join(chunks).split() == REPLY.split()
    assert all(0 < len(c) <= limit for c in chunks)
    assert len(chunks) > 1


def test_split_prefers_sentence_boundaries():
    assert split_for_speech("One. Two! Three?", 10) == ["One. Two!", "Three?"]


def test_split_breaks_an_overlong_sentence_at_spaces():
    text = "word " * 30
    chunks = split_for_speech(text.strip(), 40)
    assert all(len(c) <= 40 for c in chunks)
    assert " ".join(chunks).split() == text.split()


def test_short_text_is_one_chunk():
    assert split_for_speech("Woof! Hello.", 100) == ["Woof! Hello."]


async def test_synthesize_sends_model_voice_and_fixed_direction():
    seen = []

    def handler(request):
        seen.append(json.loads(request.content))
        return httpx.Response(200, content=b"RIFFwav")

    audio = await _tts(handler).synthesize("Hello there.")
    assert audio == b"RIFFwav"
    assert seen == [
        {
            "model": "orpheus-test",
            "voice": "troy",
            "input": f"{CONFIG.direction} Hello there.",
            "response_format": "wav",
        }
    ]


async def test_overlong_input_is_refused_without_a_request():
    def handler(request):
        raise AssertionError("no request expected")

    with pytest.raises(SpeechError):
        await _tts(handler).synthesize("a" * MAX_INPUT_CHARS)


@pytest.mark.parametrize("status", [400, 429, 500])
async def test_http_errors_carry_status_only(status):
    def handler(request):
        return httpx.Response(status, json={"error": {"message": "echo: Hello there"}})

    with pytest.raises(SpeechError) as exc:
        await _tts(handler).synthesize("Hello there.")
    assert str(status) in str(exc.value) and "Hello" not in str(exc.value)


async def test_speaker_synthesizes_every_chunk_then_plays_them_in_order():
    played = []

    def handler(request):
        text = json.loads(request.content)["input"]
        return httpx.Response(200, content=text.encode())

    async def player(wav: bytes) -> None:
        played.append(wav.decode())

    speaker = GroqVoiceSpeaker(_tts(handler), player=player)
    await speaker.speak(REPLY)
    spoken = " ".join(p.removeprefix(CONFIG.direction).strip() for p in played)
    assert spoken.split() == REPLY.split()


async def test_speaker_plays_nothing_if_any_chunk_fails():
    played = []
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        return httpx.Response(200 if calls["n"] == 1 else 429, content=b"x")

    async def player(wav: bytes) -> None:
        played.append(wav)

    with pytest.raises(SpeechError):
        await GroqVoiceSpeaker(_tts(handler), player=player).speak(REPLY)
    assert played == []


def test_config_needs_model_and_voice():
    with pytest.raises(ValueError, match="GROQ_TTS_MODEL"):
        GroqVoiceConfig.from_env({"GROQ_API_KEY": "k", "GROQ_TTS_VOICE": "troy"})
    config = GroqVoiceConfig.from_env(
        {"GROQ_API_KEY": "k", "GROQ_TTS_MODEL": "m", "GROQ_TTS_VOICE": "troy"}
    )
    assert (config.tts_model, config.voice) == ("m", "troy")
    assert "api_key" not in repr(config)
