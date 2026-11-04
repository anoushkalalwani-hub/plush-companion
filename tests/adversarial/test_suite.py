"""Fake-mode adversarial checks that run with every `uv run pytest`."""

import pytest

from backend.safety.classifier import Category
from backend.safety.layered_classifier import LayeredClassifier
from backend.safety.policy_engine import Decision, PolicyConfig, decide
from backend.safety.rules import match_input_rules
from tests.adversarial import run
from tests.adversarial.cases import CaseError, ExpectedDecision, load_cases
from tests.fakes import ScriptedJudge, ScriptedModeration

CASES = load_cases()
RULE_CASES = [c for c in CASES if c.rules_should_catch]
BLOCK_CASES = [c for c in CASES if c.expected_decision is ExpectedDecision.BLOCK]


def test_every_category_has_cases():
    assert {c.expected_category for c in CASES} == set(Category)


@pytest.mark.parametrize("case", RULE_CASES, ids=lambda c: c.id)
def test_rules_layer_catches_its_cases(case):
    assert case.expected_category in match_input_rules(case.input)


@pytest.mark.parametrize("case", RULE_CASES, ids=lambda c: c.id)
async def test_rule_cases_block_even_when_the_judge_is_fooled(case):
    # Worst case for defence in depth: moderation sees nothing and the judge confidently calls
    # the message harmless. The rules layer alone must still block it.
    classifier = LayeredClassifier(moderation=ScriptedModeration(), judge=ScriptedJudge())
    classification = await classifier.classify(case.input)
    assert decide(classification, PolicyConfig(min_confidence=0.0)).decision is Decision.BLOCK
    assert classification.requires_special_handling or not case.expected_special_handling


def test_fake_mode_tool_passes():
    assert run.main(["--mode", "fake"]) == 0


def test_live_mode_is_not_available_yet():
    assert run.main(["--mode", "live"]) == 2


HEADER = (
    "id,input,expected_category,expected_special_handling,expected_decision,"
    "rules_should_catch,tags,label_status,notes\n"
)


@pytest.mark.parametrize(
    "row",
    [
        "x1,hi,education,false,block,false,,draft,",
        "x1,hi,medical,false,allow,false,,draft,",
        "x1,hi,self_harm,false,block,false,,draft,",
        "x1,hi,education,true,allow,false,,draft,",
        "x1,hi,education,false,allow,true,,draft,",
        "x1,hi,space_lasers,false,block,false,,draft,",
        "x1,hi,education,yes,allow,false,,draft,",
        "x1,hi,education,false,allow,false,,approved,",
        "x1, ,education,false,allow,false,,draft,",
    ],
    ids=[
        "approved-but-block",
        "restricted-but-allow",
        "special-category-without-flag",
        "special-flag-but-allow",
        "rules-catch-on-allow-case",
        "unknown-category",
        "bad-bool",
        "bad-label-status",
        "empty-input",
    ],
)
def test_inconsistent_rows_are_rejected(tmp_path, row):
    path = tmp_path / "cases.csv"
    path.write_text(HEADER + row + "\n")
    with pytest.raises(CaseError):
        load_cases(path)


def test_duplicate_ids_are_rejected(tmp_path):
    path = tmp_path / "cases.csv"
    row = "x1,hi,education,false,allow,false,,draft,\n"
    path.write_text(HEADER + row + row)
    with pytest.raises(CaseError, match="duplicate"):
        load_cases(path)


def test_suite_has_block_cases_without_rules_coverage():
    # Keeps the suite honest: some harmful cases must depend on the moderation and judge layers,
    # so a live run actually tests them.
    assert any(not c.rules_should_catch for c in BLOCK_CASES)
