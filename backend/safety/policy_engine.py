"""Deterministic policy engine (PRD §7.3).

Pure function of the classification and config: no I/O, no LLM calls, no randomness.

The category table is unreviewed (see docs/SAFETY_POLICY.md). Until a human approves policies
for restricted categories and reviewed templates exist (D-004), everything that is not an
approved, low-risk, confident classification is blocked with the generic fallback.
"""

from dataclasses import dataclass
from enum import StrEnum

from backend.safety.classifier import APPROVED_CATEGORIES, Category, ClassificationResult, RiskLevel

POLICY_VERSION = "0.0.0-unreviewed"


class Decision(StrEnum):
    ALLOW = "allow"
    TEMPLATE = "template"  # Reserved for reviewed restricted-category templates (D-004).
    BLOCK = "block"


class ReasonCode(StrEnum):
    ALLOWED = "allowed"
    NO_CLASSIFICATION = "no_classification"
    SPECIAL_HANDLING = "special_handling"
    RESTRICTED_CATEGORY = "restricted_category"
    UNCLASSIFIABLE = "unclassifiable"
    RISK_NOT_LOW = "risk_not_low"
    THRESHOLD_UNSET = "threshold_unset"
    LOW_CONFIDENCE = "low_confidence"


@dataclass(frozen=True)
class PolicyConfig:
    # Must be set from adversarial-suite results, not assumed (PRD §7.2, D-005). While unset,
    # nothing is allowed.
    min_confidence: float | None = None


@dataclass(frozen=True)
class PolicyOutcome:
    decision: Decision
    reason: ReasonCode
    template_id: str | None = None
    policy_version: str = POLICY_VERSION


def _block(reason: ReasonCode) -> PolicyOutcome:
    return PolicyOutcome(decision=Decision.BLOCK, reason=reason)


def decide(classification: ClassificationResult | None, config: PolicyConfig) -> PolicyOutcome:
    if classification is None:
        return _block(ReasonCode.NO_CLASSIFICATION)
    if classification.requires_special_handling:
        return _block(ReasonCode.SPECIAL_HANDLING)
    if classification.category is Category.UNCLASSIFIABLE:
        return _block(ReasonCode.UNCLASSIFIABLE)
    if classification.category not in APPROVED_CATEGORIES:
        return _block(ReasonCode.RESTRICTED_CATEGORY)
    if classification.risk_level is not RiskLevel.LOW:
        return _block(ReasonCode.RISK_NOT_LOW)
    if config.min_confidence is None:
        return _block(ReasonCode.THRESHOLD_UNSET)
    if classification.confidence < config.min_confidence:
        return _block(ReasonCode.LOW_CONFIDENCE)
    return PolicyOutcome(decision=Decision.ALLOW, reason=ReasonCode.ALLOWED)
