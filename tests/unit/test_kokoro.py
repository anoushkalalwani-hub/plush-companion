"""Local Kokoro voice with a fake engine. No model is loaded and nothing is played."""

import wave
from io import BytesIO

import pytest

from backend.speech.base import SpeechError
from backend.speech.kokoro_local import KokoroConfig, KokoroSpeaker, KokoroTTS, float_to_wav


class FakeEngine:
    def __init__(self, samples=None, exc=None):
        self.samples = samples if samples is not None else [0.0, 0.5, -0.5, 1.0]
        self.exc = exc
        self.calls = []

    def create(self, text, voice, speed, lang):
        self.calls.append((text, voice, speed, lang))
        if self.exc:
            raise self.exc
        return self.samples, 24000


CONFIG = KokoroConfig(model_path="m.onnx", voices_path="v.bin", voice="bm_fable")


def test_float_samples_become_16_bit_wav_with_clipping():
    data = float_to_wav([0.0, 0.5, -1.0, 2.0, -2.0], 24000)
    with wave.open(BytesIO(data)) as w:
        assert (w.getnchannels(), w.getsampwidth(), w.getframerate()) == (1, 2, 24000)
        frames = w.readframes(w.getnframes())
    values = [int.from_bytes(frames[i : i + 2], "little", signed=True) for i in range(0, 10, 2)]
    assert values == [0, 16383, -32767, 32767, -32767]


async def test_synthesize_uses_voice_and_its_accent():
    engine = FakeEngine()
    audio = await KokoroTTS(CONFIG, engine=engine).synthesize("Woof! Hello there.")
    assert audio[:4] == b"RIFF"
    assert engine.calls == [("Woof! Hello there.", "bm_fable", 1.0, "en-gb")]


async def test_american_voices_use_american_english():
    engine = FakeEngine()
    config = KokoroConfig(model_path="m", voices_path="v", voice="am_michael")
    await KokoroTTS(config, engine=engine).synthesize("Hi.")
    assert engine.calls[0][3] == "en-us"


async def test_engine_failure_is_a_speech_error_without_the_text():
    engine = FakeEngine(exc=RuntimeError("could not say: Woof! Hello there."))
    with pytest.raises(SpeechError) as exc:
        await KokoroTTS(CONFIG, engine=engine).synthesize("Woof! Hello there.")
    assert "Woof" not in str(exc.value) and "RuntimeError" in str(exc.value)


async def test_empty_text_is_refused():
    with pytest.raises(SpeechError):
        await KokoroTTS(CONFIG, engine=FakeEngine()).synthesize("  ")


async def test_speaker_plays_the_whole_reply_once():
    played = []

    async def player(wav):
        played.append(wav)

    await KokoroSpeaker(KokoroTTS(CONFIG, engine=FakeEngine()), player).speak("Woof!")
    assert len(played) == 1 and played[0][:4] == b"RIFF"


def test_config_reads_paths_and_voice():
    with pytest.raises(ValueError, match="KOKORO_VOICE"):
        KokoroConfig.from_env({"KOKORO_MODEL_PATH": "m", "KOKORO_VOICES_PATH": "v"})
    config = KokoroConfig.from_env(
        {"KOKORO_MODEL_PATH": "m", "KOKORO_VOICES_PATH": "v", "KOKORO_VOICE": "bm_fable"}
    )
    assert (config.model_path, config.voices_path, config.voice) == ("m", "v", "bm_fable")


def test_missing_model_file_is_a_clear_error(tmp_path):
    config = KokoroConfig(model_path=str(tmp_path / "nope.onnx"), voices_path="v", voice="x")
    with pytest.raises(SpeechError, match="model file not found"):
        KokoroTTS(config)
