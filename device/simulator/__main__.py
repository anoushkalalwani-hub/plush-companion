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
import sys

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
from backend.sessions.store import SessionStore
from backend.speech.groq_whisper import GroqSpeechConfig, GroqWhisper
from backend.speech.macos_say import MacSaySpeaker
from device.audio.microphone import pcm_to_wav, record_until_enter
from device.simulator.chat import Turn, text_turn, voice_turn

DEVICE_ID = "laptop-simulator"
# D-005: no min_confidence has been chosen. This is the value the live adversarial runs used,
# shown in the banner so it is never mistaken for an approved setting.
DEFAULT_THRESHOLD = 0.5

BANNER = """\
Plush companion: laptop voice simulator
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
    try:
        groq = GroqConfig.from_env()
        speech = None if args.type else GroqSpeechConfig.from_env()
    except (GroqConfigError, ValueError) as exc:
        print(f"Missing Groq settings in .env ({exc}).", file=sys.stderr)
        print(
            "Run with: uv run --group voice --env-file .env python -m device.simulator",
            file=sys.stderr,
        )
        return 2
    if not args.type and importlib.util.find_spec("sounddevice") is None:
        print(
            "Spoken input needs the voice packages: add --group voice, or use --type.",
            file=sys.stderr,
        )
        return 2

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
    speaker = MacSaySpeaker(voice=args.voice, rate=args.rate)
    session = sessions.create(device_id=DEVICE_ID)

    print(BANNER.format(threshold=args.threshold))
    if args.type:
        print("Type a question and press Enter. Empty line or Ctrl+C to quit.\n")
    else:
        print("Press Enter to start talking, Enter again to stop. Type q then Enter to quit.\n")
    try:
        while True:
            if args.type:
                text = (await asyncio.to_thread(input, "> ")).strip()
                if not text:
                    break
                turn = await text_turn(text, manager, session, speaker)
            else:
                command = (await asyncio.to_thread(input, "[Enter] to talk > ")).strip()
                if command.lower() in {"q", "quit", "exit"}:
                    break
                print("  Listening... press Enter when you're done.")
                pcm = await asyncio.to_thread(record_until_enter)
                turn = await voice_turn(pcm_to_wav(pcm), stt, manager, session, speaker)
            _show(turn)
    except (KeyboardInterrupt, EOFError):
        print()
    finally:
        await client.aclose()
        if stt:
            await stt.aclose()
    print("Bye!")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Talk to the plush companion in your terminal.")
    parser.add_argument("--type", action="store_true", help="type questions instead of speaking")
    parser.add_argument("--voice", help="macOS voice name (see: say -v '?')")
    parser.add_argument("--rate", type=int, help="speaking rate in words per minute")
    parser.add_argument(
        "--threshold",
        type=float,
        default=DEFAULT_THRESHOLD,
        help="policy confidence threshold (default 0.5, an evaluation value; see D-005)",
    )
    args = parser.parse_args(argv)
    if not 0.0 <= args.threshold <= 1.0:
        parser.error("--threshold must be between 0 and 1")
    try:
        return asyncio.run(_chat(args))
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    sys.exit(main())
