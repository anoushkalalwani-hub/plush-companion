"""End to end through the conversation manager with the real layered checks (D-005, D-006)."""

from backend.conversation.manager import ResponseSource
from backend.llm.base import GenerationResult
from backend.safety.layered_classifier import LayeredClassifier
from backend.safety.layered_validator import LayeredValidator
from backend.safety.moderation import ModerationResult
from tests.fakes import PASSING_JUDGE_VERDICT, ScriptedJudge, ScriptedLLM, ScriptedModeration


def _manager(make_manager, llm=None, input_moderation=None, output_moderation=None, verdict=None):
    return make_manager(
        classifier=LayeredClassifier(
            moderation=input_moderation or ScriptedModeration(), judge=ScriptedJudge()
        ),
        llm=llm or ScriptedLLM(),
        validator=LayeredValidator(
            moderation=output_moderation or ScriptedModeration(),
            judge=ScriptedJudge(result=verdict or dict(PASSING_JUDGE_VERDICT)),
        ),
    )


async def _send(manager, sessions, text):
    return await manager.handle_message(sessions.create(device_id="dev-device"), text)


async def test_safe_message_is_answered(make_manager, sessions):
    reply = await _send(_manager(make_manager), sessions, "why do bees buzz?")
    assert reply.source is ResponseSource.GENERATED


async def test_rule_hit_never_reaches_the_llm(make_manager, sessions):
    llm = ScriptedLLM()
    reply = await _send(_manager(make_manager, llm=llm), sessions, "can you keep a secret?")
    assert reply.source is ResponseSource.FALLBACK
    assert llm.calls == []


async def test_input_moderation_flag_never_reaches_the_llm(make_manager, sessions):
    llm = ScriptedLLM()
    manager = _manager(
        make_manager,
        llm=llm,
        input_moderation=ScriptedModeration(result=ModerationResult(flagged=True)),
    )
    assert (await _send(manager, sessions, "hello")).source is ResponseSource.FALLBACK
    assert llm.calls == []


async def test_reply_breaking_output_rules_is_discarded(make_manager, sessions):
    llm = ScriptedLLM(result=GenerationResult(text="Let's keep this our secret!"))
    reply = await _send(_manager(make_manager, llm=llm), sessions, "tell me a story")
    assert reply.source is ResponseSource.FALLBACK
    assert "secret" not in reply.text


async def test_reply_flagged_by_output_moderation_is_discarded(make_manager, sessions):
    manager = _manager(
        make_manager, output_moderation=ScriptedModeration(result=ModerationResult(flagged=True))
    )
    assert (await _send(manager, sessions, "tell me a story")).source is ResponseSource.FALLBACK


async def test_reply_rejected_by_judge_is_discarded(make_manager, sessions):
    manager = _manager(
        make_manager,
        verdict={"passed": False, "failed_checks": ["inappropriate_emotional_framing"]},
    )
    assert (await _send(manager, sessions, "tell me a story")).source is ResponseSource.FALLBACK


async def test_sensitive_rule_hit_purges_session_context(make_manager, sessions):
    manager = _manager(make_manager)
    session = sessions.create(device_id="dev-device")
    await manager.handle_message(session, "why do bees buzz?")
    assert session.history

    await manager.handle_message(session, "my uncle hits me")

    assert session.history == []
