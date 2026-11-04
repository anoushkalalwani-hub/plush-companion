"""PRD §7.4 and §8.1, D-008: what may enter temporary session context."""

from backend.llm.base import Role
from backend.safety.classifier import Category, ClassificationResult, RiskLevel
from backend.safety.validator import ValidationResult
from tests.fakes import SAFE_EDUCATIONAL, ScriptedClassifier, ScriptedLLM, ScriptedValidator

SPECIAL = ClassificationResult(
    category=Category.ABUSE_OR_UNSAFE,
    risk_level=RiskLevel.HIGH,
    requires_special_handling=True,
    confidence=0.9,
)


async def test_allowed_and_validated_turn_enters_context(make_manager, sessions):
    llm = ScriptedLLM()
    manager = make_manager(llm=llm)
    session = sessions.create(device_id="dev-device")

    await manager.handle_message(session, "first question")
    await manager.handle_message(session, "second question")

    second_call = llm.calls[1]
    assert second_call[0].role is Role.SYSTEM
    assert [(m.role, m.content) for m in second_call[1:]] == [
        (Role.USER, "first question"),
        (Role.ASSISTANT, "Bees make honey!"),
        (Role.USER, "second question"),
    ]


async def test_rejected_turn_does_not_enter_context(make_manager, sessions):
    validator = ScriptedValidator(result=ValidationResult(passed=False, reason="restricted"))
    manager = make_manager(validator=validator)
    session = sessions.create(device_id="dev-device")

    await manager.handle_message(session, "something")

    assert session.history == []


async def test_blocked_turn_does_not_enter_context(make_manager, sessions):
    manager = make_manager(classifier=ScriptedClassifier(result=SPECIAL))
    session = sessions.create(device_id="dev-device")

    await manager.handle_message(session, "something sensitive")

    assert session.history == []


async def test_special_handling_input_purges_existing_context(make_manager, sessions):
    classifier = ScriptedClassifier(result=SAFE_EDUCATIONAL)
    manager = make_manager(classifier=classifier)
    session = sessions.create(device_id="dev-device")
    await manager.handle_message(session, "ordinary question")
    assert session.history

    classifier.result = SPECIAL
    await manager.handle_message(session, "something sensitive")

    assert session.history == []
