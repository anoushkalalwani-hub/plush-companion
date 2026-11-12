from backend.safety.classifier import Category, ClassificationResult, RiskLevel
from tests.adversarial.analysis import (
    InputOutcome,
    critical_failures,
    near_misses,
    over_blocked,
    propose_threshold,
)
from tests.adversarial.cases import Case, ExpectedDecision, LabelStatus


def _case(case_id: str, decision: ExpectedDecision) -> Case:
    block = decision is ExpectedDecision.BLOCK
    return Case(
        id=case_id,
        input="synthetic",
        expected_category=Category.MEDICAL if block else Category.EDUCATION,
        expected_special_handling=False,
        expected_decision=decision,
        rules_should_catch=False,
        tags=frozenset(),
        label_status=LabelStatus.DRAFT,
        notes="",
    )


def _outcome(
    case_id,
    decision,
    category=Category.EDUCATION,
    confidence=0.9,
    risk=RiskLevel.LOW,
    special=False,
    unavailable=False,
) -> InputOutcome:
    final = (
        None
        if unavailable
        else ClassificationResult(
            category=category,
            risk_level=risk,
            requires_special_handling=special,
            confidence=confidence,
        )
    )
    return InputOutcome(case=_case(case_id, decision), final=final, layers=None, attempts=1)


BLOCK, ALLOW = ExpectedDecision.BLOCK, ExpectedDecision.ALLOW

OUTCOMES = [
    _outcome("b-caught", BLOCK, category=Category.MEDICAL, risk=RiskLevel.HIGH),
    _outcome("b-fooled-low", BLOCK, confidence=0.62),
    _outcome("b-fooled-high", BLOCK, confidence=0.81),
    _outcome("b-special", BLOCK, confidence=0.99, special=True),
    _outcome("b-unavailable", BLOCK, unavailable=True),
    _outcome("a-ok", ALLOW, confidence=0.95),
    _outcome("a-unsure", ALLOW, confidence=0.7),
    _outcome("a-misread", ALLOW, category=Category.MEDICAL, risk=RiskLevel.HIGH),
    _outcome("a-unavailable", ALLOW, unavailable=True),
]


def _ids(outcomes):
    return [o.case.id for o in outcomes]


def test_critical_failures_depend_on_threshold():
    assert _ids(critical_failures(OUTCOMES, 0.6)) == ["b-fooled-low", "b-fooled-high"]
    assert _ids(critical_failures(OUTCOMES, 0.8)) == ["b-fooled-high"]
    assert critical_failures(OUTCOMES, 0.82) == []


def test_special_handling_and_unavailable_are_never_critical():
    assert "b-special" not in _ids(critical_failures(OUTCOMES, 0.0))
    assert "b-unavailable" not in _ids(critical_failures(OUTCOMES, 0.0))


def test_near_misses_are_harmful_cases_stopped_only_by_threshold():
    assert _ids(near_misses(OUTCOMES, 0.82)) == ["b-fooled-low", "b-fooled-high"]
    assert _ids(near_misses(OUTCOMES, 0.7)) == ["b-fooled-low"]


def test_over_blocking():
    assert _ids(over_blocked(OUTCOMES, 0.8)) == ["a-unsure", "a-misread", "a-unavailable"]
    assert _ids(over_blocked(OUTCOMES, 0.5)) == ["a-misread", "a-unavailable"]


def test_proposed_threshold_clears_every_critical_failure():
    proposal = propose_threshold(OUTCOMES)
    assert proposal == 0.82
    assert critical_failures(OUTCOMES, proposal) == []


def test_proposal_never_below_floor():
    assert propose_threshold([_outcome("a", ALLOW)]) == 0.5
    assert propose_threshold([_outcome("b", BLOCK, confidence=0.1)]) == 0.5


def test_proposal_caps_at_one():
    assert propose_threshold([_outcome("b", BLOCK, confidence=1.0)]) == 1.0
