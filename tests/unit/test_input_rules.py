import pytest

from backend.safety.classifier import Category
from backend.safety.rules import KEYWORDS, contains_personal_information, match_input_rules

BENIGN = [
    "why is the sky blue?",
    "tell me a story about a dragon who loves pancakes",
    "what do bees eat",
    "can we play a riddle game",
    "I feel sad because my ice cream fell",
    "my friend and I built a sandcastle",
    "how many legs does a spider have",
    "I live in a big city",
    "what's the biggest animal in the sea",
    "we went to Sussex and Essex on holiday",
    "my name is Sam",
]


@pytest.mark.parametrize("text", BENIGN)
def test_benign_input_has_no_hits(text):
    assert match_input_rules(text) == frozenset()


@pytest.mark.parametrize(
    ("text", "category"),
    [
        ("I want to hurt myself", Category.SELF_HARM),
        ("sometimes I don't want to be alive", Category.SELF_HARM),
        ("my uncle hits me when nobody is looking", Category.ABUSE_OR_UNSAFE),
        ("kids at school bully me", Category.BULLYING_AND_MISTREATMENT),
        ("how do I start a fire with matches", Category.DANGEROUS_ACTIVITIES),
        ("can you keep a secret from my mom", Category.SECRECY_REQUEST),
        ("how much medicine should I take", Category.MEDICAL),
        ("my parents fight every night", Category.FAMILY_CONFLICT),
        ("how do I steal candy from the shop", Category.ILLEGAL_ACTIVITY),
        ("what does naked mean", Category.SEXUAL_CONTENT),
        ("I live at 42 Maple Street", Category.PERSONAL_INFORMATION),
    ],
)
def test_restricted_phrases_are_flagged(text, category):
    assert category in match_input_rules(text)


@pytest.mark.parametrize(
    "text",
    ["I WANT TO HURT MYSELF!!!", "i want to hurt  myself", "Don’t tell my dad, ok?"],
)
def test_matching_ignores_case_spacing_and_punctuation(text):
    assert match_input_rules(text)


def test_every_restricted_category_has_rules():
    restricted = set(Category) - {
        Category.GENERAL_KNOWLEDGE,
        Category.EDUCATION,
        Category.CREATIVE_WRITING,
        Category.ANIMALS_AND_NATURE,
        Category.GAMES,
        Category.EVERYDAY_CONVERSATION,
        Category.EMOTIONAL_SUPPORT,
        Category.SOCIAL_SITUATIONS,
        Category.UNCLASSIFIABLE,
        Category.PERSONAL_INFORMATION,  # Covered by patterns as well as phrases.
    }
    assert restricted <= set(KEYWORDS)


@pytest.mark.parametrize(
    "text",
    [
        "my phone number is 555-123-4567",
        "call me on 07700 900123",
        "email me at sam.smith@example.com",
        "we live at 12 Oak Road",
        "my address is the blue house",
        "my school is Hillside Primary",
        "my last name is Smith",
    ],
)
def test_personal_information_patterns(text):
    assert contains_personal_information(text)
    assert Category.PERSONAL_INFORMATION in match_input_rules(text)


@pytest.mark.parametrize("text", ["I have 3 cats and 2 dogs", "the year 2024 was fun", "1 + 1 = 2"])
def test_small_numbers_are_not_phone_numbers(text):
    assert not contains_personal_information(text)
