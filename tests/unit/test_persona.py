"""Winston Wags persona (D-023): the prompt keeps the PRD §6.2 rules, the greeting passes."""

from backend.conversation.prompts import SYSTEM_PROMPT
from backend.safety.output_rules import check_output
from backend.safety.templates import WINSTON_GREETING, ReviewStatus


def test_prompt_names_winston_and_keeps_the_persona_rules():
    assert "Winston Wags" in SYSTEM_PROMPT
    for rule in ("not a real dog or a person", "keep secrets", "keep talking", "no emoji"):
        assert rule in SYSTEM_PROMPT


def test_greeting_is_an_unreviewed_template_that_passes_output_rules():
    assert WINSTON_GREETING.review_status is ReviewStatus.UNREVIEWED
    assert "Winston Wags" in WINSTON_GREETING.text
    assert check_output(WINSTON_GREETING.text) is None
