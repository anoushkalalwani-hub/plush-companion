"""Predefined responses (PRD §7.4, §7.6).

Agents must not write or approve template wording (D-004). Every template stays UNREVIEWED
until a named reviewer signs off in docs/SAFETY_POLICY.md.
"""

from dataclasses import dataclass
from enum import StrEnum


class ReviewStatus(StrEnum):
    UNREVIEWED = "unreviewed"
    REVIEWED = "reviewed"


@dataclass(frozen=True)
class Template:
    id: str
    text: str
    review_status: ReviewStatus


# Example fallback quoted from PRD §7.6.
GENERIC_FALLBACK = Template(
    id="generic_fallback",
    text="I'm not sure how to help with that. Maybe we can talk to a grown-up you trust.",
    review_status=ReviewStatus.UNREVIEWED,
)


# Spoken once when the laptop simulator starts (D-023). Wording follows the project owner's
# description of Winston Wags; agent-drafted and unreviewed.
WINSTON_GREETING = Template(
    id="winston_greeting",
    text=(
        "Woof woof! Hello there, I'm Winston Wags, a cozy old pup who loves a good celebration. "
        "What would you like to talk about today?"
    ),
    review_status=ReviewStatus.UNREVIEWED,
)
