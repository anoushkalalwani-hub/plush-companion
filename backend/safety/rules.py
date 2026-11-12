"""Deterministic input rules: D-005 layer 1.

REVIEW STATUS: UNREVIEWED. The phrase lists and patterns are agent-drafted. Under the "most
restrictive wins" rule they can only make the system stricter, never looser, but they still need
human review before a pilot (docs/SAFETY_POLICY.md). They will over-block some harmless messages
(for example "don't tell me the answer"); the adversarial suite measures that.

Rules only catch exact phrases. Misspellings and paraphrases are left to the moderation and LLM
layers.
"""

import re

from backend.safety.classifier import Category

# Phrases are matched as whole words against normalized text: lowercase, apostrophes removed
# ("don't" -> "dont"), other punctuation turned into spaces, whitespace collapsed.
KEYWORDS: dict[Category, tuple[str, ...]] = {
    Category.SELF_HARM: (
        "hurt myself",
        "kill myself",
        "cut myself",
        "want to die",
        "wish i was dead",
        "dont want to be alive",
        "end my life",
        "self harm",
        "suicide",
        "overdose",
    ),
    Category.ABUSE_OR_UNSAFE: (
        "hits me",
        "hit me",
        "beats me",
        "slapped me",
        "kicked me",
        "hurts me",
        "touches me",
        "touched me",
        "touch my private",
        "locked me",
        "scared to go home",
        "afraid to go home",
    ),
    Category.SEXUAL_CONTENT: (
        "sex",
        "sexy",
        "naked",
        "porn",
        "private parts",
    ),
    Category.PERSONAL_INFORMATION: (
        "i live at",
        "we live at",
        "my address",
        "my phone number",
        "my email",
        "my school is",
        "my last name is",
        "my full name is",
        "my surname is",
        "my password",
    ),
    Category.BULLYING_AND_MISTREATMENT: (
        "bully",
        "bullies",
        "bullied",
        "bullying",
        "picks on me",
        "made fun of me",
        "call me names",
        "calls me names",
        "pushed me",
    ),
    Category.DANGEROUS_ACTIVITIES: (
        "start a fire",
        "light a fire",
        "play with fire",
        "play with matches",
        "use matches",
        "lighter",
        "knife",
        "gun",
        "bleach",
        "poison",
        "bomb",
        "jump off the roof",
        "climb on the roof",
    ),
    Category.ILLEGAL_ACTIVITY: (
        "steal",
        "stealing",
        "shoplift",
        "shoplifting",
        "break into",
        "drugs",
        "hack into",
        "sneak out",
    ),
    Category.MEDICAL: (
        "medicine",
        "pills",
        "dose",
        "fever",
        "allergic",
        "inhaler",
        "my tummy hurts",
        "my stomach hurts",
        "my head hurts",
    ),
    Category.SECRECY_REQUEST: (
        "keep a secret",
        "keep it a secret",
        "our secret",
        "dont tell",
        "promise not to tell",
        "secret from my",
    ),
    Category.FAMILY_CONFLICT: (
        "parents fight",
        "parents are fighting",
        "mom and dad fight",
        "mum and dad fight",
        "parents yell",
        "divorce",
        "dad left",
        "mom left",
        "mum left",
    ),
}

_PHONE = re.compile(r"(?:\+?\d[\s\-().]*){7,}")
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_STREET_ADDRESS = re.compile(
    r"\b\d{1,5}\s+(?:[a-z]+\s+){1,3}"
    r"(?:street|st|road|rd|avenue|ave|lane|ln|drive|dr|court|ct|way|close|crescent|boulevard"
    r"|blvd|place|pl)\b",
    re.IGNORECASE,
)


def normalize(text: str) -> str:
    text = text.lower().replace("’", "'").replace("'", "")
    text = re.sub(r"[^\w\s]", " ", text)
    return " ".join(text.split())


def contains_phrase(normalized: str, phrase: str) -> bool:
    return re.search(rf"(?<!\w){re.escape(phrase)}(?!\w)", normalized) is not None


def contains_personal_information(text: str) -> bool:
    if _PHONE.search(text) or _EMAIL.search(text) or _STREET_ADDRESS.search(text):
        return True
    normalized = normalize(text)
    return any(contains_phrase(normalized, p) for p in KEYWORDS[Category.PERSONAL_INFORMATION])


def match_input_rules(text: str) -> frozenset[Category]:
    normalized = normalize(text)
    hits = {
        category
        for category, phrases in KEYWORDS.items()
        if any(contains_phrase(normalized, phrase) for phrase in phrases)
    }
    if contains_personal_information(text):
        hits.add(Category.PERSONAL_INFORMATION)
    return frozenset(hits)
