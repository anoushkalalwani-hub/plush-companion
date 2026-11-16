"""Audio pieces that must work on a Raspberry Pi as well as a Mac (D-026). Nothing is played."""

import asyncio
import wave
from array import array
from io import BytesIO

import pytest

from backend.speech.base import SpeechError
from backend.speech.espeak import EspeakSpeaker
from device.audio.cues import play_thinking_cue, thinking_tone_wav
from device.audio.devices import device_from_text
from device.audio.playback import decode_wav, resample_pcm16
from device.simulator.voices import backup_speaker

# Device names


@pytest.mark.parametrize(
    ("text", "expected"),
    [(None, None), ("", None), ("  ", None), ("3", 3), ("USB Audio", "USB Audio")],
)
def test_device_from_text(text, expected):
    assert device_from_text(text) == expected


# Resampling for USB devices that only accept 44.1 or 48 kHz


def _pcm(values):
    return array("h", values).tobytes()


def _values(pcm):
    out = array("h")
    out.frombytes(pcm)
    return list(out)


def test_same_rate_is_unchanged():
    pcm = _pcm([0, 100, -100])
    assert resample_pcm16(pcm, 1, 24000, 24000) == pcm


def test_doubling_the_rate_interpolates_between_samples():
    out = _values(resample_pcm16(_pcm([0, 100, 200]), 1, 24000, 48000))
    assert len(out) == 6
    assert out[:5] == [0, 50, 100, 150, 200]


def test_stereo_channels_are_resampled_separately():
    # Left channel counts up, right channel stays at -50.
    out = _values(resample_pcm16(_pcm([0, -50, 100, -50]), 2, 24000, 48000))
    assert out[1::2] == [-50] * (len(out) // 2)
    assert out[0::2][:3] == [0, 50, 100]


# Thinking chime, generated in memory


def test_thinking_tone_is_a_short_quiet_wav():
    audio = decode_wav(thinking_tone_wav())
    assert audio.channels == 1 and audio.sample_width == 2
    seconds = len(audio.pcm) / 2 / audio.sample_rate
    assert 0.1 < seconds < 0.6
    assert max(abs(v) for v in _values(audio.pcm)) < 32767 // 3


async def test_thinking_cue_never_raises_and_does_not_wait():
    started = asyncio.Event()

    async def failing_player(wav):
        started.set()
        raise SpeechError("no output device")

    await play_thinking_cue(failing_player)
    await asyncio.wait_for(started.wait(), 1)
    await asyncio.sleep(0)  # Let the failed task finish; nothing should propagate.


# Backup voice


class FakeProcess:
    def __init__(self, returncode=0):
        self.returncode = returncode
        self.stdin_data = None

    async def communicate(self, data=None):
        self.stdin_data = data
        return b"", b""


@pytest.fixture
def spawned(monkeypatch):
    state = {"calls": [], "process": FakeProcess(), "exc": None}

    async def fake_exec(*args, **kwargs):
        state["calls"].append(args)
        if state["exc"]:
            raise state["exc"]
        return state["process"]

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)
    return state


async def test_espeak_reads_text_from_stdin_not_arguments(spawned):
    await EspeakSpeaker(voice="en-us", rate=150).speak("-v bad --help hello")
    [args] = spawned["calls"]
    assert args == ("espeak-ng", "-v", "en-us", "-s", "150", "--stdin")
    assert spawned["process"].stdin_data == b"-v bad --help hello"


async def test_espeak_failures_are_speech_errors(spawned):
    spawned["process"] = FakeProcess(returncode=1)
    with pytest.raises(SpeechError, match="exit 1"):
        await EspeakSpeaker().speak("hi")
    spawned["exc"] = FileNotFoundError("espeak-ng")
    with pytest.raises(SpeechError):
        await EspeakSpeaker().speak("hi")


def test_backup_voice_is_say_on_macos(monkeypatch):
    from backend.speech.macos_say import MacSaySpeaker

    monkeypatch.setattr("sys.platform", "darwin")
    assert isinstance(backup_speaker(), MacSaySpeaker)


def test_backup_voice_is_espeak_on_linux_when_installed(monkeypatch):
    monkeypatch.setattr("sys.platform", "linux")
    monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/espeak-ng")
    assert isinstance(backup_speaker(), EspeakSpeaker)


async def test_without_a_backup_voice_speaking_is_an_error(monkeypatch):
    monkeypatch.setattr("sys.platform", "linux")
    monkeypatch.setattr("shutil.which", lambda name: None)
    with pytest.raises(SpeechError, match="no backup voice"):
        await backup_speaker().speak("hi")


def test_mono_wav_helper_still_round_trips():
    from device.audio.microphone import pcm_to_wav

    with wave.open(BytesIO(pcm_to_wav(_pcm([1, 2, 3]), 48000))) as w:
        assert w.getframerate() == 48000
