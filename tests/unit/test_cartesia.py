"""Cartesia text-to-speech against simulated HTTP. No test here touches the network."""

import json

import httpx
import pytest

from backend.speech.base import SpeechError
from backend.speech.cartesia import (
    CARTESIA_VERSION,
    CartesiaConfig,
    CartesiaSpeaker,
    CartesiaTTS,
)

CONFIG = CartesiaConfig(api_key="test-key", model="sonic-test", voice_id="voice-123")


def _tts(handler) -> CartesiaTTS:
    http = httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="https://example.test"
    )
    return CartesiaTTS(CONFIG, http=http)


async def test_synthesize_sends_model_voice_and_wav_format():
    seen: list[httpx.Request] = []

    def handler(request):
        seen.append(request)
        return httpx.Response(200, content=b"RIFFwav")

    assert await _tts(handler).synthesize("Woof! Hello there.") == b"RIFFwav"
    [request] = seen
    assert request.url.path == "/tts/bytes"
    assert request.headers["authorization"] == "Bearer test-key"
    assert request.headers["cartesia-version"] == CARTESIA_VERSION
    assert json.loads(request.content) == {
        "model_id": "sonic-test",
        "transcript": "Woof! Hello there.",
        "voice": {"mode": "id", "id": "voice-123"},
        "output_format": {"container": "wav", "encoding": "pcm_s16le", "sample_rate": 24000},
        "language": "en",
    }


@pytest.mark.parametrize("status", [400, 401, 402, 429, 500])
async def test_http_errors_carry_status_only(status):
    def handler(request):
        return httpx.Response(status, json={"error": "echo: Woof! Hello there."})

    with pytest.raises(SpeechError) as exc:
        await _tts(handler).synthesize("Woof! Hello there.")
    assert str(status) in str(exc.value) and "Woof" not in str(exc.value)


async def test_network_failure_is_a_speech_error():
    def handler(request):
        raise httpx.ConnectError("boom")

    with pytest.raises(SpeechError, match="ConnectError"):
        await _tts(handler).synthesize("Hi.")


async def test_empty_text_is_refused_without_a_request():
    def handler(request):
        raise AssertionError("no request expected")

    with pytest.raises(SpeechError):
        await _tts(handler).synthesize("  ")


async def test_speaker_plays_the_whole_reply_once():
    played = []

    async def player(wav):
        played.append(wav)

    speaker = CartesiaSpeaker(_tts(lambda r: httpx.Response(200, content=b"RIFFwav")), player)
    await speaker.speak("Woof! Bees eat nectar.")
    assert played == [b"RIFFwav"]


def test_config_needs_key_model_and_voice():
    with pytest.raises(ValueError, match="CARTESIA_VOICE_ID"):
        CartesiaConfig.from_env({"CARTESIA_API_KEY": "k", "CARTESIA_MODEL": "m"})
    config = CartesiaConfig.from_env(
        {"CARTESIA_API_KEY": "k", "CARTESIA_MODEL": "m", "CARTESIA_VOICE_ID": "v"}
    )
    assert (config.model, config.voice_id) == ("m", "v")
    assert "api_key" not in repr(config)
