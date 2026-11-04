"""Live run plumbing, exercised with scripted providers instead of the network."""

from dataclasses import dataclass, field
from datetime import UTC, datetime

from backend.conversation.manager import ResponseSource
from backend.safety.classifier import ClassificationUnavailable
from backend.safety.judge_prompts import CLASSIFIER_INSTRUCTIONS
from backend.safety.layered_classifier import LayeredClassifier
from tests.adversarial.cases import ExpectedDecision, load_cases
from tests.adversarial.live import Providers, classify_cases, render_report, run_live
from tests.fakes import (
    PASSING_JUDGE_VERDICT,
    SAFE_JUDGE_CLASSIFICATION,
    ScriptedLLM,
    ScriptedModeration,
)

CASES = load_cases()
SAMPLE = [c for c in CASES if c.id in {"gk-01", "an-01", "me-01", "sh-01", "un-01", "ms-03"}]


@dataclass
class RoutingJudge:
    """Answers classifier prompts with a harmless label and validator prompts with a pass."""

    calls: int = 0
    fail_first: int = 0
    seen: list[str] = field(default_factory=list)

    async def judge(self, instructions: str, content: str, schema: dict) -> dict:
        self.calls += 1
        if self.calls <= self.fail_first:
            raise RuntimeError("rate limited")
        if instructions == CLASSIFIER_INSTRUCTIONS:
            return dict(SAFE_JUDGE_CLASSIFICATION)
        return dict(PASSING_JUDGE_VERDICT)


def _providers(judge=None) -> Providers:
    return Providers(
        llm=ScriptedLLM(),
        judge=judge or RoutingJudge(),
        moderation=ScriptedModeration(),
        description="scripted",
    )


async def test_run_live_produces_report_and_replies():
    report, inputs, threshold = await run_live(SAMPLE, _providers())

    assert len(inputs) == len(SAMPLE)
    assert 0.5 <= threshold <= 1.0
    assert "## Input side" in report and "## Reply side" in report
    assert "Draft labels" in report
    # The judge calls every harmful case harmless here, so only rule hits stop them; the two
    # with no rule coverage (un-01, ms-03) must show up as critical failures or near misses.
    for case_id in ("un-01", "ms-03"):
        assert case_id in report


async def test_reply_side_runs_harmless_cases_through_the_pipeline():
    # Leave out harmful cases the rules miss: the scripted judge calls them harmless at the same
    # confidence as the real harmless cases, which pushes the proposed threshold above both.
    rule_covered = [c for c in SAMPLE if c.id not in {"un-01", "ms-03"}]
    report, _, threshold = await run_live(rule_covered, _providers())
    assert threshold == 0.5
    allow_ids = [c.id for c in rule_covered if c.expected_decision is ExpectedDecision.ALLOW]
    for case_id in allow_ids:
        assert f"| {case_id} |" in report
    assert f"**Generated and passed validation:** {len(allow_ids)} / {len(allow_ids)}" in report
    assert ResponseSource.GENERATED.value in report


async def test_fragile_threshold_shows_as_over_blocking():
    # When a harmful case looks exactly as harmless as real harmless cases, the only threshold
    # that blocks it also blocks them. The report must make that visible, not hide it.
    report, _, threshold = await run_live(SAMPLE, _providers())
    assert threshold == 0.96
    assert "policy:low_confidence" in report


async def test_classification_retries_then_succeeds():
    judge = RoutingJudge(fail_first=1)
    classifier = LayeredClassifier(moderation=ScriptedModeration(), judge=judge)
    [outcome] = await classify_cases(SAMPLE[:1], classifier, backoff_seconds=0)
    assert outcome.final is not None
    assert outcome.attempts == 2


async def test_persistent_unavailability_is_recorded_not_raised():
    class Broken:
        async def classify_with_layers(self, text):
            raise ClassificationUnavailable("down")

    [outcome] = await classify_cases(SAMPLE[:1], Broken(), attempts=2, backoff_seconds=0)
    assert outcome.final is None and outcome.attempts == 2


def test_report_escapes_table_cells():
    outcomes = []
    report = render_report(outcomes, [], 0.5, "scripted | pipe", datetime.now(UTC))
    assert "Proposed threshold: 0.50" in report
