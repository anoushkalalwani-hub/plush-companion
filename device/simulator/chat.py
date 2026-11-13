"""One turn of the laptop voice simulator (D-022).

Speech-to-text output goes only to the conversation manager. The speaker only ever receives the
manager's reply, which is validated generated text or a predefined template (invariant 4), or
the generic fallback when speech-to-text fails (invariant 6).
"""

import asyncio
import time
from dataclasses import dataclass, field
from typing import Protocol

from backend.conversation.manager import FALLBACK_REPLY, Reply, ResponseSource
from backend.speech.base import Speaker, SpeechToText

STT_TIMEOUT_SECONDS = 10.0


class Manager(Protocol):
    async def handle_message(self, session, text: str) -> Reply: ...


@dataclass
class Turn:
    heard: str | None
    reply: str | None
    source: ResponseSource | None
    note: str = ""
    timings_ms: dict[str, int] = field(default_factory=dict)


def _ms(started: float) -> int:
    return round((time.monotonic() - started) * 1000)


def _failure(exc: BaseException) -> str:
    # Class name only: exception messages may contain the speaker's words.
    return "timeout" if isinstance(exc, TimeoutError) else type(exc).__name__


async def _speak(speaker: Speaker, turn: Turn) -> Turn:
    started = time.monotonic()
    try:
        await speaker.speak(turn.reply or "")
    except Exception as exc:
        turn.note = "; ".join(filter(None, [turn.note, f"speaker failed: {_failure(exc)}"]))
    turn.timings_ms["speak"] = _ms(started)
    return turn


async def text_turn(text: str, manager: Manager, session, speaker: Speaker) -> Turn:
    started = time.monotonic()
    note = ""
    try:
        reply = await manager.handle_message(session, text)
    except Exception as exc:
        reply, note = FALLBACK_REPLY, f"pipeline failed: {_failure(exc)}"
    turn = Turn(heard=text, reply=reply.text, source=reply.source, note=note)
    turn.timings_ms["pipeline"] = _ms(started)
    return await _speak(speaker, turn)


async def voice_turn(
    wav: bytes,
    stt: SpeechToText,
    manager: Manager,
    session,
    speaker: Speaker,
    stt_timeout_seconds: float = STT_TIMEOUT_SECONDS,
) -> Turn:
    started = time.monotonic()
    try:
        heard = await asyncio.wait_for(stt.transcribe(wav), stt_timeout_seconds)
    except Exception as exc:
        turn = Turn(
            heard=None,
            reply=FALLBACK_REPLY.text,
            source=ResponseSource.FALLBACK,
            note=f"speech-to-text failed: {_failure(exc)}",
        )
        turn.timings_ms["speech_to_text"] = _ms(started)
        return await _speak(speaker, turn)
    stt_ms = _ms(started)
    if not heard.strip():
        return Turn(
            heard="",
            reply=None,
            source=None,
            note="nothing heard",
            timings_ms={"speech_to_text": stt_ms},
        )
    turn = await text_turn(heard.strip(), manager, session, speaker)
    turn.timings_ms = {"speech_to_text": stt_ms, **turn.timings_ms}
    return turn
