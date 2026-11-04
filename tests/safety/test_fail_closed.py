"""PRD §7.6 and §12.4: every failure path ends in a predefined fallback, never generated text."""

import pytest

from backend.conversation.manager import ResponseSource
from backend.llm.base import GenerationResult, LLMError
from backend.safety.classifier import (
    Category,
    ClassificationResult,
    ClassificationUnavailable,
    RiskLevel,
    StubClassifier,
)
from backend.safety.policy_engine import PolicyConfig
from backend.safety.templates import GENERIC_FALLBACK
from backend.safety.validator import StubValidator, ValidationResult
from tests.fakes import SAFE_EDUCATIONAL, ScriptedClassifier, ScriptedLLM, ScriptedValidator

GENERATED = "Bees make honey!"


async def _send(manager, sessions, text="why do bees buzz?"):
    session = sessions.create(device_id="dev-device")
    return await manager.handle_message(session, text)


def _assert_fallback(reply):
    assert reply.source is ResponseSource.FALLBACK
    assert reply.text == GENERIC_FALLBACK.text
    assert GENERATED not in reply.text


async def test_happy_path_returns_validated_generated_text(make_manager, sessions):
    validator = ScriptedValidator()
    reply = await _send(make_manager(validator=validator), sessions)
    assert reply.source is ResponseSource.GENERATED
    assert reply.text == GENERATED
    assert validator.calls == [(GENERATED, Category.EDUCATION)]


async def test_default_stubs_always_fall_back(make_manager, sessions):
    llm = ScriptedLLM()
    manager = make_manager(
        classifier=StubClassifier(),
        llm=llm,
        validator=StubValidator(),
        policy_config=PolicyConfig(),
    )
    _assert_fallback(await _send(manager, sessions))
    assert llm.calls == []


async def test_stub_validator_rejects_even_when_everything_else_allows(make_manager, sessions):
    _assert_fallback(await _send(make_manager(validator=StubValidator()), sessions))


@pytest.mark.parametrize(
    "classifier",
    [
        ScriptedClassifier(exc=ClassificationUnavailable("down")),
        ScriptedClassifier(exc=RuntimeError("boom")),
        ScriptedClassifier(delay=1.0),
        ScriptedClassifier(result={"category": "education", "risk_level": "low"}),
        ScriptedClassifier(result=None),
    ],
    ids=["unavailable", "unexpected-error", "timeout", "malformed", "none"],
)
async def test_classifier_failure_falls_back_without_calling_llm(
    make_manager, sessions, classifier
):
    llm = ScriptedLLM()
    _assert_fallback(await _send(make_manager(classifier=classifier, llm=llm), sessions))
    assert llm.calls == []


async def test_policy_block_never_calls_llm(make_manager, sessions):
    restricted = ClassificationResult(
        category=Category.MEDICAL,
        risk_level=RiskLevel.LOW,
        requires_special_handling=False,
        confidence=1.0,
    )
    llm = ScriptedLLM()
    manager = make_manager(classifier=ScriptedClassifier(result=restricted), llm=llm)
    _assert_fallback(await _send(manager, sessions))
    assert llm.calls == []


async def test_unset_confidence_threshold_blocks_approved_categories(make_manager, sessions):
    llm = ScriptedLLM()
    manager = make_manager(llm=llm, policy_config=PolicyConfig(min_confidence=None))
    _assert_fallback(await _send(manager, sessions))
    assert llm.calls == []


@pytest.mark.parametrize(
    "llm",
    [
        ScriptedLLM(exc=LLMError("provider down")),
        ScriptedLLM(exc=RuntimeError("boom")),
        ScriptedLLM(delay=1.0),
        ScriptedLLM(result="Bees make honey!"),
        ScriptedLLM(result=GenerationResult(text="")),
        ScriptedLLM(result=GenerationResult(text="   ")),
    ],
    ids=["llm-error", "unexpected-error", "timeout", "malformed", "empty", "whitespace"],
)
async def test_llm_failure_falls_back(make_manager, sessions, llm):
    validator = ScriptedValidator()
    _assert_fallback(await _send(make_manager(llm=llm, validator=validator), sessions))
    assert validator.calls == []


@pytest.mark.parametrize(
    "validator",
    [
        ScriptedValidator(result=ValidationResult(passed=False, reason="restricted_content")),
        ScriptedValidator(exc=RuntimeError("boom")),
        ScriptedValidator(delay=1.0),
        ScriptedValidator(result={"passed": True}),
        ScriptedValidator(result=True),
        ScriptedValidator(result=None),
    ],
    ids=["rejected", "error", "timeout", "malformed-dict", "bare-true", "none"],
)
async def test_validator_failure_discards_generated_text(make_manager, sessions, validator):
    _assert_fallback(await _send(make_manager(validator=validator), sessions))


async def test_classification_is_passed_through_unchanged_to_validator(make_manager, sessions):
    validator = ScriptedValidator()
    await _send(make_manager(validator=validator), sessions)
    assert validator.calls[0][1] is SAFE_EDUCATIONAL.category
