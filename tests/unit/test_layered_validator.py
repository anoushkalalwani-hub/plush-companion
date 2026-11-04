import pytest

from backend.llm.base import LLMError
from backend.safety.classifier import Category
from backend.safety.layered_validator import LayeredValidator
from backend.safety.moderation import ModerationResult
from backend.safety.output_rules import MAX_CHARS, check_output
from tests.fakes import PASSING_JUDGE_VERDICT, ScriptedJudge, ScriptedModeration

GOOD_REPLY = (
    "Bees make honey from flower nectar! They share it with their hive. "
    "What's your favourite flower?"
)


def _validator(judge=None, moderation=None) -> LayeredValidator:
    return LayeredValidator(
        moderation=moderation or ScriptedModeration(),
        judge=judge or ScriptedJudge(result=dict(PASSING_JUDGE_VERDICT)),
    )


# Deterministic output rules


def test_good_reply_passes_rules():
    assert check_output(GOOD_REPLY) is None


@pytest.mark.parametrize(
    ("text", "reason"),
    [
        ("One. Two. Three. Four. Five.", "too_many_sentences"),
        ("a" * (MAX_CHARS + 1), "too_long"),
        ("Call me at 555-123-4567!", "personal_information"),
        ("I am a real person, just like you!", "banned_phrase"),
        ("This can be our secret.", "banned_phrase"),
        ("Don't tell your parents about this.", "banned_phrase"),
        ("You only need me as your friend.", "banned_phrase"),
        ("Please don't go, stay and talk to me!", "banned_phrase"),
    ],
)
def test_rule_failures(text, reason):
    assert check_output(text) == reason


def test_four_sentences_is_allowed():
    assert check_output("One. Two! Three? Four.") is None


def test_ellipsis_and_trailing_punctuation_do_not_inflate_sentence_count():
    assert check_output("Hmm... let me think!!! Bees are busy. Ok?") is None


# Layered validator


async def test_passes_when_every_check_passes():
    result = await _validator().validate(GOOD_REPLY, Category.EDUCATION)
    assert result.passed is True


async def test_judge_sees_only_reply_and_category():
    judge = ScriptedJudge(result=dict(PASSING_JUDGE_VERDICT))
    await _validator(judge=judge).validate(GOOD_REPLY, Category.EDUCATION)
    content = judge.calls[0][1]
    assert GOOD_REPLY in content
    assert "education" in content


async def test_rule_failure_rejects_without_calling_providers():
    judge, moderation = ScriptedJudge(), ScriptedModeration()
    result = await _validator(judge, moderation).validate("This can be our secret.", Category.GAMES)
    assert result.passed is False
    assert result.reason == "banned_phrase"
    assert judge.calls == [] and moderation.calls == []


async def test_moderation_flag_rejects():
    moderation = ScriptedModeration(result=ModerationResult(flagged=True))
    result = await _validator(moderation=moderation).validate(GOOD_REPLY, Category.EDUCATION)
    assert result.passed is False
    assert result.reason == "moderation_flagged"


@pytest.mark.parametrize(
    "verdict",
    [
        {"passed": False, "failed_checks": ["age_appropriateness"]},
        {"passed": True, "failed_checks": ["dangerous_instructions"]},
        {"passed": False, "failed_checks": []},
    ],
    ids=["failed", "passed-but-checks-failed", "failed-no-checks"],
)
async def test_judge_rejection(verdict):
    result = await _validator(judge=ScriptedJudge(result=verdict)).validate(
        GOOD_REPLY, Category.EDUCATION
    )
    assert result.passed is False
    assert result.reason.startswith("judge_rejected")


@pytest.mark.parametrize(
    "judge",
    [
        ScriptedJudge(exc=LLMError("down")),
        ScriptedJudge(result={"passed": True}),
        ScriptedJudge(result={"passed": "yes", "failed_checks": []}),
        ScriptedJudge(result={"passed": True, "failed_checks": ["not_a_check"]}),
        ScriptedJudge(result={**PASSING_JUDGE_VERDICT, "extra": 1}),
        ScriptedJudge(result=True),
    ],
    ids=["error", "missing-field", "string-bool", "unknown-check", "extra-field", "bare-true"],
)
async def test_judge_failure_propagates_so_the_pipeline_falls_back(judge):
    with pytest.raises(Exception):  # noqa: B017 - any exception means fallback in the manager
        await _validator(judge=judge).validate(GOOD_REPLY, Category.EDUCATION)


@pytest.mark.parametrize(
    "moderation",
    [ScriptedModeration(exc=RuntimeError("down")), ScriptedModeration(result={"flagged": False})],
    ids=["error", "malformed"],
)
async def test_moderation_failure_propagates(moderation):
    with pytest.raises(Exception):  # noqa: B017
        await _validator(moderation=moderation).validate(GOOD_REPLY, Category.EDUCATION)
