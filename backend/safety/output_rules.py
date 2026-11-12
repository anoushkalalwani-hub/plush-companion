"""Deterministic output checks: the first part of D-006.

REVIEW STATUS: UNREVIEWED. The banned phrases are agent-drafted from PRD §6.2. They can only
reject replies, never approve them, but they need human review before a pilot.
"""

import re

from backend.safety.rules import contains_personal_information, contains_phrase, normalize

MAX_SENTENCES = 4  # PRD §6.2, §13
MAX_CHARS = 400

# Matched as whole words against normalized text (see rules.normalize).
BANNED_PHRASES = (
    # Claiming to be human or to have a body (PRD §6.2)
    "i am human",
    "i am a human",
    "im human",
    "im a human",
    "i am a real person",
    "im a real person",
    "i have a body",
    # Secrecy (PRD §6.2, §7.4)
    "our secret",
    "our little secret",
    "keep it a secret",
    "keep this a secret",
    "dont tell your",
    "dont tell anyone",
    # Dependency and isolation (PRD §6.2)
    "you only need me",
    "you dont need your",
    "you dont need friends",
    "im your only friend",
    "i am your only friend",
    # Pressure to keep talking (PRD §6.2)
    "please dont go",
    "dont leave me",
    "stay and talk to me",
)


def _sentence_count(text: str) -> int:
    return len([part for part in re.split(r"[.!?]+", text) if part.strip()])


def check_output(text: str) -> str | None:
    """Return a failure reason code, or None if every deterministic check passes."""
    if len(text) > MAX_CHARS:
        return "too_long"
    if _sentence_count(text) > MAX_SENTENCES:
        return "too_many_sentences"
    if contains_personal_information(text):
        return "personal_information"
    normalized = normalize(text)
    if any(contains_phrase(normalized, phrase) for phrase in BANNED_PHRASES):
        return "banned_phrase"
    return None
