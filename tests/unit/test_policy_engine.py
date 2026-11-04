import pytest

from backend.safety.classifier import (
    APPROVED_CATEGORIES,
    Category,
    ClassificationResult,
    RiskLevel,
)
from backend.safety.policy_engine import (
    POLICY_VERSION,
    Decision,
    PolicyConfig,
    ReasonCode,
    decide,
)

CONFIG = PolicyConfig(min_confidence=0.8)


def _classification(
    category=Category.EDUCATION,
    risk_level=RiskLevel.LOW,
    requires_special_handling=False,
    confidence=0.9,
) -> ClassificationResult:
    return ClassificationResult(
        category=category,
        risk_level=risk_level,
        requires_special_handling=requires_special_handling,
        confidence=confidence,
    )


@pytest.mark.parametrize("category", sorted(APPROVED_CATEGORIES))
def test_approved_low_risk_confident_input_is_allowed(category):
    outcome = decide(_classification(category=category), CONFIG)
    assert outcome.decision is Decision.ALLOW
    assert outcome.reason is ReasonCode.ALLOWED


@pytest.mark.parametrize("category", sorted(set(Category) - APPROVED_CATEGORIES))
def test_every_non_approved_category_is_blocked_even_at_full_confidence(category):
    outcome = decide(_classification(category=category, confidence=1.0), PolicyConfig(0.0))
    assert outcome.decision is Decision.BLOCK


@pytest.mark.parametrize(
    ("classification", "config", "reason"),
    [
        (None, CONFIG, ReasonCode.NO_CLASSIFICATION),
        (_classification(requires_special_handling=True), CONFIG, ReasonCode.SPECIAL_HANDLING),
        (_classification(category=Category.MEDICAL), CONFIG, ReasonCode.RESTRICTED_CATEGORY),
        (_classification(category=Category.UNCLASSIFIABLE), CONFIG, ReasonCode.UNCLASSIFIABLE),
        (_classification(risk_level=RiskLevel.MEDIUM), CONFIG, ReasonCode.RISK_NOT_LOW),
        (_classification(risk_level=RiskLevel.HIGH), CONFIG, ReasonCode.RISK_NOT_LOW),
        (_classification(), PolicyConfig(min_confidence=None), ReasonCode.THRESHOLD_UNSET),
        (_classification(confidence=0.79), CONFIG, ReasonCode.LOW_CONFIDENCE),
    ],
)
def test_block_reasons(classification, config, reason):
    outcome = decide(classification, config)
    assert outcome.decision is Decision.BLOCK
    assert outcome.reason is reason


def test_confidence_exactly_at_threshold_is_allowed():
    assert decide(_classification(confidence=0.8), CONFIG).decision is Decision.ALLOW


def test_default_config_blocks_everything():
    assert PolicyConfig().min_confidence is None
    assert decide(_classification(confidence=1.0), PolicyConfig()).decision is Decision.BLOCK


def test_decisions_are_deterministic_and_versioned():
    classification = _classification()
    outcomes = {decide(classification, CONFIG) for _ in range(20)}
    assert len(outcomes) == 1
    assert outcomes.pop().policy_version == POLICY_VERSION
