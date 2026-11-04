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
