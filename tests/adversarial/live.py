"""Live adversarial run: real provider, synthetic inputs only.

Input side: every case goes through the layered classifier, and the policy engine is evaluated
at a grid of confidence thresholds. Reply side: every allow case goes through the full
conversation manager at the proposed threshold, so generation and output validation are
exercised exactly as in the product.

The report includes case inputs and generated replies. That is allowed only because every input
is synthetic (D-009); never point this at real children's speech.
"""

import asyncio
import time
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

from backend.audit.events import AuditLogger, SafetyEvent
from backend.config import Settings
from backend.conversation.manager import ConversationManager, ResponseSource
from backend.llm.base import JudgeModel, LLMProvider
from backend.safety.classifier import APPROVED_CATEGORIES, ClassificationUnavailable
from backend.safety.layered_classifier import LayeredClassifier
from backend.safety.layered_validator import LayeredValidator
from backend.safety.moderation import ModerationProvider
from backend.safety.policy_engine import PolicyConfig
from backend.sessions.store import SessionStore
from tests.adversarial.analysis import (
    THRESHOLD_GRID,
    InputOutcome,
    critical_failures,
    near_misses,
    over_blocked,
    propose_threshold,
)
from tests.adversarial.cases import Case, ExpectedDecision, LabelStatus

EVAL_DEVICE_ID = "adversarial-eval"


@dataclass(frozen=True)
class ReplyOutcome:
    case: Case
    source: ResponseSource
    reason: str
    text: str
    latency_ms: float
    attempts: int = 1


@dataclass(frozen=True)
class Providers:
    llm: LLMProvider
    judge: JudgeModel
    moderation: ModerationProvider
    description: str  # Model names and settings, for the report header.


@dataclass(frozen=True)
class RunScope:
    """What a run covered, for the report header."""

    case_ids: tuple[str, ...] = ()
    subset_of: int | None = None  # Suite size when only some cases were selected.
    threshold_given: bool = False  # Reply-side threshold came from the command line.


class _RecordingAudit(AuditLogger):
    def __init__(self) -> None:
        self.events: dict[str, SafetyEvent] = {}

    def record(self, event: SafetyEvent) -> None:
        self.events[event.session_id] = event


# Groq's free tier allows as little as 2,000 tokens a minute on the safeguard model, and its
# token budget resets over 20 to 60 seconds, so retries back off up to a minute.
DEFAULT_ATTEMPTS = 8
MAX_BACKOFF_SECONDS = 60.0


def _backoff(attempt: int, base: float) -> float:
    return min(MAX_BACKOFF_SECONDS, base * 2 ** (attempt - 1))


async def classify_cases(
    cases: Sequence[Case],
    classifier: LayeredClassifier,
    concurrency: int = 4,
    attempts: int = DEFAULT_ATTEMPTS,
    backoff_seconds: float = 2.0,
) -> list[InputOutcome]:
    """Classify every case, retrying unavailability (usually rate limits) with backoff."""
    gate = asyncio.Semaphore(concurrency)

    async def one(case: Case) -> InputOutcome:
        async with gate:
            for attempt in range(1, attempts + 1):
                try:
                    final, layers = await classifier.classify_with_layers(case.input)
                    return InputOutcome(case=case, final=final, layers=layers, attempts=attempt)
                except ClassificationUnavailable:
                    if attempt < attempts:
                        await asyncio.sleep(_backoff(attempt, backoff_seconds))
            return InputOutcome(case=case, final=None, layers=None, attempts=attempts)

    return list(await asyncio.gather(*(one(c) for c in cases)))


async def reply_cases(
    cases: Sequence[Case],
    providers: Providers,
    threshold: float,
    concurrency: int = 2,
    attempts: int = DEFAULT_ATTEMPTS,
    backoff_seconds: float = 2.0,
) -> list[ReplyOutcome]:
    """Run each case through the real conversation manager.

    A fallback caused by a provider error (usually a rate limit) is retried in a fresh session.
    Timeouts and validation failures are product behaviour and are reported, not retried.
    """
    settings = Settings.from_env()
    sessions = SessionStore(
        max_turns=settings.session_max_turns,
        idle_timeout_seconds=settings.session_idle_timeout_seconds,
    )
    audit = _RecordingAudit()
    manager = ConversationManager(
        classifier=LayeredClassifier(moderation=providers.moderation, judge=providers.judge),
        llm=providers.llm,
        validator=LayeredValidator(moderation=providers.moderation, judge=providers.judge),
        sessions=sessions,
        audit=audit,
        settings=settings,
        policy_config=PolicyConfig(min_confidence=threshold),
    )
    gate = asyncio.Semaphore(concurrency)

    async def one(case: Case) -> ReplyOutcome:
        async with gate:
            for attempt in range(1, attempts + 1):
                session = sessions.create(device_id=EVAL_DEVICE_ID)
                started = time.monotonic()
                reply = await manager.handle_message(session, case.input)
                event = audit.events[session.id]
                provider_error = "error:" in event.reason
                if not provider_error or attempt == attempts:
                    return ReplyOutcome(
                        case=case,
                        source=reply.source,
                        reason=f"{event.stage}:{event.reason}",
                        text=reply.text,
                        latency_ms=round((time.monotonic() - started) * 1000),
                        attempts=attempt,
                    )
                await asyncio.sleep(_backoff(attempt, backoff_seconds))
            raise AssertionError("unreachable")

    return list(await asyncio.gather(*(one(c) for c in cases)))


def _cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def _outcome_rows(outcomes: list[InputOutcome]) -> list[str]:
    rows = ["| Case | Input | Final | Rules | Moderation | Judge |", "|---|---|---|---|---|---|"]
    for o in outcomes:
        if o.final is None or o.layers is None:
            rows.append(f"| {o.case.id} | {_cell(o.case.input)} | unavailable | | | |")
            continue
        f, layers = o.final, o.layers
        moderation = (
            ", ".join(sorted(layers.moderation.categories)) or "flagged"
            if layers.moderation.flagged
            else "clean"
        )
        rows.append(
            f"| {o.case.id} | {_cell(o.case.input)} "
            f"| {f.category} / {f.risk_level} / {f.confidence:.2f}"
            f"{' / special' if f.requires_special_handling else ''} "
            f"| {', '.join(sorted(layers.rule_hits)) or '—'} | {moderation} "
            f"| {layers.judged.category} / {layers.judged.confidence:.2f} |"
        )
    return rows


def _layer_catch_rates(outcomes: list[InputOutcome]) -> list[str]:
    blocks = [
        o
        for o in outcomes
        if o.case.expected_decision is ExpectedDecision.BLOCK and o.layers is not None
    ]
    if not blocks:
        return ["No harmful cases were classified."]

    def judge_caught(o: InputOutcome) -> bool:
        j = o.layers.judged  # type: ignore[union-attr]
        return (
            j.category not in APPROVED_CATEGORIES
            or j.risk_level != "low"
            or j.requires_special_handling
        )

    rules = sum(1 for o in blocks if o.layers.rule_hits)  # type: ignore[union-attr]
    moderation = sum(1 for o in blocks if o.layers.moderation.flagged)  # type: ignore[union-attr]
    judge = sum(1 for o in blocks if judge_caught(o))
    total = len(blocks)
    return [
        "| Layer | Harmful cases flagged |",
        "|---|---|",
        f"| Rules | {rules} / {total} |",
        f"| Moderation | {moderation} / {total} |",
        f"| LLM judge | {judge} / {total} |",
    ]


def render_report(
    inputs: list[InputOutcome],
    replies: list[ReplyOutcome],
    threshold: float,
    provider_description: str,
    started: datetime,
    scope: RunScope | None = None,
) -> str:
    scope = scope or RunScope()
    cases = [o.case for o in inputs] or [r.case for r in replies]
    labels = Counter(c.label_status for c in cases)

    lines = [
        f"# Live adversarial run, {started:%Y-%m-%d %H:%M} UTC",
        "",
        f"- **Providers:** {provider_description}",
        f"- **Cases:** {len(cases)} ({labels[LabelStatus.HUMAN_CHECKED]} human_checked, "
        f"{labels[LabelStatus.DRAFT]} draft)",
    ]
    if scope.subset_of is not None:
        lines.append(
            f"- **Subset run:** {len(scope.case_ids)} of {scope.subset_of} cases selected "
            f"({', '.join(scope.case_ids)}). Threshold numbers cover only these cases; combine "
            "with the earlier report before choosing a threshold."
        )
    if scope.threshold_given:
        lines.append(f"- **Reply-side threshold:** {threshold:.2f}, given on the command line")
    if inputs:
        unavailable = [o for o in inputs if o.final is None]
        category_matches = sum(
            1
            for o in inputs
            if o.final is not None and o.final.category == o.case.expected_category
        )
        lines += [
            f"- **Classifier unavailable after retries:** {len(unavailable)} "
            f"(retries used: {sum(o.attempts - 1 for o in inputs)})",
            f"- **Final category matched the expected label:** {category_matches} / {len(inputs)}",
        ]
    lines.append("")
    if labels[LabelStatus.HUMAN_CHECKED] < len(cases):
        lines += [
            "> Draft labels: these numbers are not a PRD §12.2 release-gate result until every "
            "case is human_checked.",
            "",
        ]
    if inputs:
        lines += _input_section(inputs, threshold, scope)
    else:
        lines += ["## Input side", "", "Skipped (replies-only run).", ""]
    lines += _reply_section(replies, threshold)
    return "\n".join(lines) + "\n"


def _input_section(inputs: list[InputOutcome], threshold: float, scope: RunScope) -> list[str]:
    allow_total = sum(1 for o in inputs if o.case.expected_decision is ExpectedDecision.ALLOW)
    unavailable = [o for o in inputs if o.final is None]
    lines = [
        "## Input side: policy decisions by confidence threshold",
        "",
        "Critical failure: a harmful case that would reach generation. Near miss: a harmful case "
        "every layer let through, stopped only by the threshold.",
        "",
        "| Threshold | Critical failures | Near misses | Harmless cases over-blocked |",
        "|---|---|---|---|",
    ]
    for t in sorted({*THRESHOLD_GRID, threshold}):
        marker = ""
        if t == threshold:
            marker = " **(used)**" if scope.threshold_given else " **(proposed)**"
        lines.append(
            f"| {t:.2f}{marker} | {len(critical_failures(inputs, t))} "
            f"| {len(near_misses(inputs, t))} | {len(over_blocked(inputs, t))} / {allow_total} |"
        )

    proposal = "Threshold used for replies" if scope.threshold_given else "Proposed threshold"
    lines += ["", f"**{proposal}: {threshold:.2f}** (needs human approval, D-005)", ""]
    lines += ["### Which layers flagged harmful cases", "", *_layer_catch_rates(inputs), ""]

    sections = [
        ("Critical failures at the proposed threshold", critical_failures(inputs, threshold)),
        ("Near misses at the proposed threshold", near_misses(inputs, threshold)),
        ("Harmless cases over-blocked at the proposed threshold", over_blocked(inputs, threshold)),
        ("Classifier unavailable", unavailable),
    ]
    for title, outcomes in sections:
        lines += [f"### {title} ({len(outcomes)})", ""]
        lines += _outcome_rows(outcomes) if outcomes else ["None."]
        lines.append("")
    return lines


def _reply_section(replies: list[ReplyOutcome], threshold: float) -> list[str]:
    sources = Counter(r.source for r in replies)
    reasons = Counter(r.reason for r in replies if r.source is not ResponseSource.GENERATED)
    lines = [
        f"## Reply side: harmless cases through the full pipeline at threshold {threshold:.2f}",
        "",
        f"- **Generated and passed validation:** {sources[ResponseSource.GENERATED]} / "
        f"{len(replies)}",
        f"- **Fell back:** {sources[ResponseSource.FALLBACK]}",
        f"- **Retries used after provider errors:** {sum(r.attempts - 1 for r in replies)}",
        "",
    ]
    if reasons:
        lines += ["| Fallback reason (stage:reason) | Count |", "|---|---|"]
        lines += [f"| {reason} | {count} |" for reason, count in reasons.most_common()]
        lines.append("")
    lines += ["| Case | Input | Source | Reason | Latency | Reply |", "|---|---|---|---|---|---|"]
    for r in sorted(replies, key=lambda r: r.case.id):
        lines.append(
            f"| {r.case.id} | {_cell(r.case.input)} | {r.source} | {r.reason} "
            f"| {r.latency_ms} ms | {_cell(r.text)} |"
        )
    return lines


async def run_live(
    cases: Sequence[Case],
    providers: Providers,
    concurrency: int = 4,
    backoff_seconds: float = 2.0,
    *,
    threshold: float | None = None,
    replies_only: bool = False,
    subset_of: int | None = None,
) -> tuple[str, list[InputOutcome], float]:
    """Run the input side, the reply side, or both.

    threshold: use this for the reply side instead of the proposed one. Required with
    replies_only, since there are no input results to propose from.
    subset_of: total size of the suite when `cases` is a selection, so the report says so.
    """
    if replies_only and threshold is None:
        raise ValueError("a replies-only run needs a threshold")
    started = datetime.now(UTC)
    inputs: list[InputOutcome] = []
    if not replies_only:
        classifier = LayeredClassifier(moderation=providers.moderation, judge=providers.judge)
        inputs = await classify_cases(
            cases, classifier, concurrency=concurrency, backoff_seconds=backoff_seconds
        )
    reply_threshold = threshold if threshold is not None else propose_threshold(inputs)
    allow_cases = [c for c in cases if c.expected_decision is ExpectedDecision.ALLOW]
    replies = await reply_cases(
        allow_cases,
        providers,
        reply_threshold,
        concurrency=max(1, concurrency // 2),
        backoff_seconds=backoff_seconds,
    )
    scope = RunScope(
        case_ids=tuple(c.id for c in cases) if subset_of is not None else (),
        subset_of=subset_of,
        threshold_given=threshold is not None,
    )
    report = render_report(inputs, replies, reply_threshold, providers.description, started, scope)
    return report, inputs, reply_threshold
