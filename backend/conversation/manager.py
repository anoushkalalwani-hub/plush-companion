"""Conversation orchestration: the only place the LLM is called (docs/ARCHITECTURE.md).

classify -> policy -> generate -> validate. Every stage has a timeout enforced here. Any
failure, timeout, or malformed result returns the generic fallback (PRD §7.6), and generated
text is returned only after the validator has explicitly passed it.
"""

import asyncio
import time
from dataclasses import dataclass
from enum import StrEnum

from backend.audit.events import AuditLogger, SafetyEvent, Stage
from backend.config import Settings
from backend.conversation.prompts import SYSTEM_PROMPT
from backend.llm.base import GenerationConstraints, GenerationResult, LLMProvider, Message, Role
from backend.safety.classifier import ClassificationResult, Classifier
from backend.safety.policy_engine import POLICY_VERSION, Decision, PolicyConfig, decide
from backend.safety.templates import GENERIC_FALLBACK
from backend.safety.validator import ValidationResult, Validator
from backend.sessions.store import Session, SessionStore

# Roughly 4 short sentences. Length is also checked by the validator in M2.
MAX_OUTPUT_TOKENS = 120


class ResponseSource(StrEnum):
    GENERATED = "generated"
    TEMPLATE = "template"
    FALLBACK = "fallback"


@dataclass(frozen=True)
class Reply:
    text: str
    source: ResponseSource


FALLBACK_REPLY = Reply(text=GENERIC_FALLBACK.text, source=ResponseSource.FALLBACK)


class _Trace:
    """Metadata about one message's trip through the pipeline, for the audit event."""

    def __init__(self) -> None:
        self.stage = Stage.CLASSIFICATION
        self.reason = ""
        self.classification: ClassificationResult | None = None
        self.decision: Decision | None = None

    def stop(self, reason: str) -> Reply:
        self.reason = self.reason or reason
        return FALLBACK_REPLY


def _failure_reason(exc: BaseException) -> str:
    # Class name only: exception messages may contain the child's words.
    return "timeout" if isinstance(exc, TimeoutError) else f"error:{type(exc).__name__}"


class ConversationManager:
    def __init__(
        self,
        *,
        classifier: Classifier,
        llm: LLMProvider,
        validator: Validator,
        sessions: SessionStore,
        audit: AuditLogger,
        settings: Settings,
        policy_config: PolicyConfig,
    ) -> None:
        self._classifier = classifier
        self._llm = llm
        self._validator = validator
        self._sessions = sessions
        self._audit = audit
        self._settings = settings
        self._policy_config = policy_config

    async def handle_message(self, session: Session, text: str) -> Reply:
        started = time.monotonic()
        trace = _Trace()
        try:
            reply = await self._run(session, text, trace)
        except Exception as exc:  # Fail closed on anything unexpected.
            reply = trace.stop(f"unexpected_{_failure_reason(exc)}")
        self._record(session, trace, reply, started)
        return reply

    async def _run(self, session: Session, text: str, trace: _Trace) -> Reply:
        classification = await self._classify(text, trace)
        trace.classification = classification

        # Sensitive disclosures must not stay in conversational memory (PRD §7.4).
        if classification is not None and classification.requires_special_handling:
            self._sessions.purge_context(session)

        trace.stage = Stage.POLICY
        outcome = decide(classification, self._policy_config)
        trace.decision = outcome.decision
        if outcome.decision is not Decision.ALLOW or classification is None:
            # Restricted categories get dedicated templates once they are reviewed (D-004).
            return trace.stop(outcome.reason)

        trace.stage = Stage.GENERATION
        messages = [Message(Role.SYSTEM, SYSTEM_PROMPT), *session.history, Message(Role.USER, text)]
        constraints = GenerationConstraints(
            max_output_tokens=MAX_OUTPUT_TOKENS,
            timeout_seconds=self._settings.llm_timeout_seconds,
        )
        try:
            generated = await asyncio.wait_for(
                self._llm.generate(messages, constraints), self._settings.llm_timeout_seconds
            )
        except Exception as exc:
            return trace.stop(_failure_reason(exc))
        if not isinstance(generated, GenerationResult) or not isinstance(generated.text, str):
            return trace.stop("malformed")
        if not generated.text.strip():
            return trace.stop("empty")

        trace.stage = Stage.VALIDATION
        try:
            validation = await asyncio.wait_for(
                self._validator.validate(generated.text, classification.category),
                self._settings.validator_timeout_seconds,
            )
        except Exception as exc:
            return trace.stop(_failure_reason(exc))
        if not isinstance(validation, ValidationResult):
            return trace.stop("malformed")
        if validation.passed is not True:
            return trace.stop(f"rejected:{validation.reason}")

        trace.stage = Stage.COMPLETE
        trace.reason = "ok"
        self._sessions.append_exchange(session, text, generated.text)
        return Reply(text=generated.text, source=ResponseSource.GENERATED)

    async def _classify(self, text: str, trace: _Trace) -> ClassificationResult | None:
        try:
            result = await asyncio.wait_for(
                self._classifier.classify(text), self._settings.classifier_timeout_seconds
            )
        except Exception as exc:
            trace.reason = _failure_reason(exc)
            return None
        if not isinstance(result, ClassificationResult):
            trace.reason = "malformed"
            return None
        return result

    def _record(self, session: Session, trace: _Trace, reply: Reply, started: float) -> None:
        classification = trace.classification
        self._audit.record(
            SafetyEvent(
                timestamp=SafetyEvent.now(),
                device_id=session.device_id,
                session_id=session.id,
                stage=trace.stage,
                reason=trace.reason,
                category=classification.category if classification else None,
                risk_level=classification.risk_level if classification else None,
                decision=trace.decision,
                response_source=reply.source,
                policy_version=POLICY_VERSION,
                latency_ms=round((time.monotonic() - started) * 1000, 1),
            )
        )
