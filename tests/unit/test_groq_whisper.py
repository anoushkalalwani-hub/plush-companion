"""Groq Whisper speech-to-text against simulated HTTP. No test here touches the network."""

import httpx
import pytest

from backend.speech.base import SpeechError
from backend.speech.groq_whisper import GroqSpeechConfig, GroqWhisper

CONFIG = GroqSpeechConfig(api_key="test-key", stt_model="whisper-test")
WAV = b"RIFF....WAVEfake-audio"


def _whisper(handler) -> GroqWhisper:
    http = httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="https://example.test/openai/v1"
    )
    return GroqWhisper(CONFIG, http=http)


async def test_sends_audio_as_multipart_and_returns_text():
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"text": " why is the sky blue "})

    text = await _whisper(handler).transcribe(WAV)
    assert text == "why is the sky blue"
    [request] = seen
    assert request.url.path.endswith("/audio/transcriptions")
    assert request.headers["authorization"] == "Bearer test-key"
    assert request.headers["content-type"].startswith("multipart/form-data")
    body = request.content
    assert WAV in body
    assert b'name="model"' in body and b"whisper-test" in body
    assert b'name="language"' in body and b"en" in body


@pytest.mark.parametrize("status", [400, 401, 429, 500])
async def test_http_errors_carry_status_only(status):
    def handler(request):
        return httpx.Response(status, json={"error": {"message": "echo: why is the sky blue"}})

    with pytest.raises(SpeechError) as exc:
        await _whisper(handler).transcribe(WAV)
    assert str(status) in str(exc.value)
    assert "sky" not in str(exc.value)


@pytest.mark.parametrize("body", [{"nope": 1}, {"text": 5}, ["text"]])
async def test_malformed_responses_are_errors(body):
    with pytest.raises(SpeechError):
        await _whisper(lambda r: httpx.Response(200, json=body)).transcribe(WAV)


async def test_network_failure_is_a_speech_error():
    def handler(request):
        raise httpx.ConnectError("boom")

    with pytest.raises(SpeechError, match="ConnectError"):
        await _whisper(handler).transcribe(WAV)


async def test_empty_audio_is_refused_without_a_request():
    def handler(request):
        raise AssertionError("no request expected")

    with pytest.raises(SpeechError):
        await _whisper(handler).transcribe(b"")


def test_config_needs_key_and_model():
    with pytest.raises(ValueError, match="GROQ_STT_MODEL"):
        GroqSpeechConfig.from_env({"GROQ_API_KEY": "k"})
    config = GroqSpeechConfig.from_env({"GROQ_API_KEY": "k", "GROQ_STT_MODEL": "m"})
    assert config.stt_model == "m"
    assert "k" not in repr(config)
