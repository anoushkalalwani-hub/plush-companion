"""Invariant 7 / D-009: logs carry metadata only, never what the child or the toy said."""

import logging

import pytest

from backend.llm.base import GenerationResult
from backend.safety.classifier import ClassificationUnavailable
from backend.safety.validator import ValidationResult
from tests.fakes import ScriptedClassifier, ScriptedLLM, ScriptedValidator

CHILD_TEXT = "my name is PURPLE-ELEPHANT-7731"
REPLY_TEXT = "Hello ORANGE-GIRAFFE-4412!"


@pytest.mark.parametrize(
    "overrides",
    [
        {},
        {"classifier": ScriptedClassifier(exc=ClassificationUnavailable(CHILD_TEXT))},
        {"classifier": ScriptedClassifier(exc=RuntimeError(CHILD_TEXT))},
        {"llm": ScriptedLLM(exc=RuntimeError(CHILD_TEXT))},
        {"validator": ScriptedValidator(exc=RuntimeError(REPLY_TEXT))},
        {"validator": ScriptedValidator(result=ValidationResult(passed=False, reason="x"))},
    ],
    ids=[
        "success",
        "classifier-unavailable",
        "classifier-error",
        "llm-error",
        "validator-error",
        "validator-rejects",
    ],
)
async def test_no_content_in_logs(make_manager, sessions, caplog, overrides):
    overrides.setdefault("llm", ScriptedLLM(result=GenerationResult(text=REPLY_TEXT)))
    manager = make_manager(**overrides)
    session = sessions.create(device_id="dev-device")

    with caplog.at_level(logging.DEBUG):
        await manager.handle_message(session, CHILD_TEXT)

    assert caplog.records, "expected a safety event to be logged"
    assert "PURPLE-ELEPHANT" not in caplog.text
    assert "ORANGE-GIRAFFE" not in caplog.text
