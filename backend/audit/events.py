"""Privacy-preserving safety event logging (PRD §7.3, §9, D-009).

SafetyEvent has no field that can hold what the child said or what the toy replied. Failure
reasons are codes or exception class names, never exception messages, which providers may
build from the input.
"""

import json
import logging
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from enum import StrEnum

logger = logging.getLogger("plush.audit")


class Stage(StrEnum):
    CLASSIFICATION = "classification"
    POLICY = "policy"
    GENERATION = "generation"
    VALIDATION = "validation"
    COMPLETE = "complete"


@dataclass(frozen=True)
class SafetyEvent:
    timestamp: str
    device_id: str
    session_id: str
    stage: Stage  # Where the pipeline stopped, or COMPLETE.
    reason: str
    category: str | None
    risk_level: str | None
    decision: str | None
    response_source: str
    policy_version: str
    latency_ms: float

    @staticmethod
    def now() -> str:
        return datetime.now(UTC).isoformat()


class AuditLogger:
    def record(self, event: SafetyEvent) -> None:
        logger.info(json.dumps(asdict(event)))
