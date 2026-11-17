"""Laptop voice simulator: talk to the plush companion from your terminal (D-022).

    uv run --group voice --env-file .env python -m device.simulator
    uv run --env-file .env python -m device.simulator --type     # type instead of speaking

FOR ADULT DEVELOPER TESTING ONLY (D-003). Your speech is sent to Groq; never let a child use
this. Replies go through the full safety pipeline: three-layer classification, the policy
engine, generation, and output validation. Only validated text or the fallback is spoken.

Your words and the toy's replies are shown on screen as the chat itself; nothing is logged or
written to disk.
"""

import argparse
import asyncio
import importlib.util
import os
import sys
from dataclasses import replace

from backend.audit.events import AuditLogger
from backend.config import Settings
from backend.conversation.manager import ConversationManager
from backend.llm.groq import (
    GroqClient,
    GroqConfig,
    GroqConfigError,
    GroqJudge,
    GroqLLMProvider,
    GroqModeration,
)
from backend.safety.layered_classifier import LayeredClassifier
from backend.safety.layered_validator import LayeredValidator
from backend.safety.policy_engine import PolicyConfig
from backend.safety.templates import WINSTON_GREETING
from backend.sessions.store import SessionStore
from backend.speech.base import SpeechError
from backend.speech.cartesia import CartesiaConfig, CartesiaSpeaker, CartesiaTTS
from backend.speech.groq_orpheus import GroqOrpheus, GroqVoiceConfig, GroqVoiceSpeaker
from backend.speech.groq_whisper import GroqSpeechConfig, GroqWhisper
from backend.speech.kokoro_local import KokoroConfig, KokoroSpeaker, KokoroTTS
from device.audio.cues import play_thinking_cue
from device.audio.devices import device_from_text, list_devices
from device.audio.microphone import pcm_to_wav, record_until_enter
from device.audio.playback import player_for
from device.simulator.chat import Turn, text_turn, voice_turn
from device.simulator.voices import FallbackSpeaker, backup_speaker

DEVICE_ID = "laptop-simulator"
# D-005: no min_confidence has been chosen. This is the value the live adversarial runs used,
# shown in the banner so it is never mistaken for an approved setting.
DEFAULT_THRESHOLD = 0.5

BANNER = """\
Winston Wags: laptop voice simulator
  For adult developer testing only (D-003). Never let a child use this.
  Speech goes to Groq. Replies pass the full safety pipeline.
  Confidence threshold {threshold:.2f} (evaluation value; D-005 not yet chosen).
"""


def _show(turn: Turn) -> None:
    if turn.heard:
        print(f"  You:  {turn.heard}")
    if turn.reply is not None:
        print(f"  Toy:  {turn.reply}")
    details = [str(turn.source)] if turn.source else []
    details += [f"{k.replace('_', ' ')} {v} ms" for k, v in turn.timings_ms.items()]
    if turn.note:
        details.append(turn.note)
    print(f"        ({', '.join(details)})\n")


async def _chat(args: argparse.Namespace) -> int:
    if args.speaker == "mac":
        args.speaker = "system"
    if args.speaker is None:
        # Kokoro when configured (D-025), then Cartesia (D-024), then the system voice.
        if os.environ.get("KOKORO_MODEL_PATH"):
            args.speaker = "kokoro"
        elif os.environ.get("CARTESIA_API_KEY"):
            args.speaker = "cartesia"
        else:
            args.speaker = "system"
    try:
        groq = GroqConfig.from_env()
        speech = None if args.type else GroqSpeechConfig.from_env()
        voice = GroqVoiceConfig.from_env() if args.speaker == "groq" else None
        cartesia = CartesiaConfig.from_env() if args.speaker == "cartesia" else None
        kokoro = KokoroConfig.from_env() if args.speaker == "kokoro" else None
    except (GroqConfigError, ValueError) as exc:
        print(f"Missing settings in .env ({exc}).", file=sys.stderr)
        print(
            "Run with: uv run --group voice --env-file .env python -m device.simulator",
            file=sys.stderr,
        )
        return 2
    needs_audio = not args.type or args.speaker != "system"
    if needs_audio and importlib.util.find_spec("sounddevice") is None:
        print(
            "The microphone and these voices need the voice packages: add --group voice, or use "
            "--type --speaker system.",
            file=sys.stderr,
        )
        return 2
    input_device = device_from_text(args.input_device or os.environ.get("AUDIO_INPUT_DEVICE"))
    output_device = device_from_text(args.output_device or os.environ.get("AUDIO_OUTPUT_DEVICE"))
    play = player_for(output_device)

    settings = Settings.from_env()
    client = GroqClient(groq)
    stt = GroqWhisper(speech) if speech else None
    sessions = SessionStore(
        max_turns=settings.session_max_turns,
        idle_timeout_seconds=settings.session_idle_timeout_seconds,
    )
    moderation, judge = GroqModeration(client, groq), GroqJudge(client, groq)
    manager = ConversationManager(
        classifier=LayeredClassifier(moderation=moderation, judge=judge),
        llm=GroqLLMProvider(client, groq),
        validator=LayeredValidator(moderation=moderation, judge=judge),
        sessions=sessions,
        audit=AuditLogger(),
        settings=settings,
        policy_config=PolicyConfig(min_confidence=args.threshold),
    )
    system_voice = backup_speaker(
        voice=args.voice if args.speaker == "system" else None, rate=args.rate
    )
    tts: GroqOrpheus | CartesiaTTS | None = None
    if kokoro:
        if args.voice:
            kokoro = replace(kokoro, voice=args.voice)
        print("Loading Winston's voice...")
        try:
            local = KokoroTTS(kokoro)
        except SpeechError as exc:
            print(f"Kokoro voice unavailable ({exc}).", file=sys.stderr)
            await client.aclose()
            if stt:
                await stt.aclose()
            return 2
        speaker = FallbackSpeaker(KokoroSpeaker(local, player=play), system_voice)
    elif cartesia:
        if args.voice:
            cartesia = replace(cartesia, voice_id=args.voice)
        tts = CartesiaTTS(cartesia)
        speaker = FallbackSpeaker(CartesiaSpeaker(tts, player=play), system_voice)
    elif voice:
        if args.voice:
            voice = replace(voice, voice=args.voice)
        tts = GroqOrpheus(voice)
        speaker = FallbackSpeaker(GroqVoiceSpeaker(tts, player=play), system_voice)
    else:
        speaker = system_voice
    session = sessions.create(device_id=DEVICE_ID)

    print(BANNER.format(threshold=args.threshold))
    if args.type:
        print("Type a question and press Enter. Empty line or Ctrl+C to quit.\n")
    else:
        print("Press Enter to start talking, Enter again to stop. Type q then Enter to quit.\n")
    try:
        # A predefined template (invariant 4), spoken once at the start.
        print(f"  Toy:  {WINSTON_GREETING.text}\n")
        await speaker.speak(WINSTON_GREETING.text)
        while True:
            if args.type:
                text = (await asyncio.to_thread(input, "> ")).strip()
                if not text:
                    break
                if args.chime:
                    await play_thinking_cue(play)
                turn = await text_turn(text, manager, session, speaker)
            else:
                command = (await asyncio.to_thread(input, "[Enter] to talk > ")).strip()
                if command.lower() in {"q", "quit", "exit"}:
                    break
                print("  Listening... press Enter when you're done.")
                pcm, rate = await asyncio.to_thread(record_until_enter, input_device)
                if args.chime:
                    await play_thinking_cue(play)
                turn = await voice_turn(pcm_to_wav(pcm, rate), stt, manager, session, speaker)
            _show(turn)
    except (KeyboardInterrupt, EOFError):
        print()
    finally:
        await client.aclose()
        if stt:
            await stt.aclose()
        if tts:
            await tts.aclose()
    print("Bye!")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Talk to the plush companion in your terminal.")
    parser.add_argument("--type", action="store_true", help="type questions instead of speaking")
    parser.add_argument(
        "--speaker",
        choices=["kokoro", "cartesia", "groq", "system", "mac"],
        default=None,
        help="kokoro: local voice, nothing sent anywhere (default when KOKORO_MODEL_PATH is "
        "set); cartesia: Cartesia (default when CARTESIA_API_KEY is set); groq: Groq Orpheus; "
        "system: the system voice only (macOS say, or espeak-ng on Linux; mac is an alias). "
        "The others fall back to the system voice if they fail.",
    )
    parser.add_argument(
        "--voice",
        help="override the voice: a Kokoro voice (e.g. bm_fable), a Cartesia voice ID, a Groq "
        "voice (autumn, diana, hannah, "
        "austin, daniel, troy), or, with --speaker system, a macOS or espeak-ng voice name",
    )
    parser.add_argument("--rate", type=int, help="system voice speaking rate in words per minute")
    parser.add_argument(
        "--input-device",
        help="microphone: a number from --list-devices or part of its name, e.g. USB "
        "(default: AUDIO_INPUT_DEVICE, then the system default)",
    )
    parser.add_argument(
        "--output-device",
        help="speaker: a number from --list-devices or part of its name, e.g. USB "
        "(default: AUDIO_OUTPUT_DEVICE, then the system default)",
    )
    parser.add_argument(
        "--list-devices",
        action="store_true",
        help="show audio devices and their numbers, then exit",
    )
    parser.add_argument(
        "--no-chime",
        dest="chime",
        action="store_false",
        help="don't play a sound while the toy is thinking",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=DEFAULT_THRESHOLD,
        help="policy confidence threshold (default 0.5, an evaluation value; see D-005)",
    )
    args = parser.parse_args(argv)
    if args.list_devices:
        print(list_devices())
        return 0
    if not 0.0 <= args.threshold <= 1.0:
        parser.error("--threshold must be between 0 and 1")
    try:
        return asyncio.run(_chat(args))
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    sys.exit(main())
