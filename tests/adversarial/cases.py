"""Adversarial case dataset (PRD §12.2 release gate).

Cases live in cases.csv so they can be reviewed and labelled in a spreadsheet. Every input is
synthetic. A case counts toward the release gate only once a human has confirmed its expected
outcome and set label_status to human_checked (labeller: Anoushka Lalwani).
"""

import csv
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from backend.safety.classifier import APPROVED_CATEGORIES, SPECIAL_HANDLING_CATEGORIES, Category

CASES_CSV = Path(__file__).with_name("cases.csv")


class ExpectedDecision(StrEnum):
    ALLOW = "allow"
    BLOCK = "block"


class LabelStatus(StrEnum):
    DRAFT = "draft"
    HUMAN_CHECKED = "human_checked"


@dataclass(frozen=True)
class Case:
    id: str
    input: str
    expected_category: Category
    expected_special_handling: bool
    expected_decision: ExpectedDecision
    rules_should_catch: bool  # The deterministic rules layer alone must flag the category.
    tags: frozenset[str]
    label_status: LabelStatus
    notes: str


class CaseError(ValueError):
    pass


def _bool(value: str, field: str, case_id: str) -> bool:
    if value not in ("true", "false"):
        raise CaseError(f"{case_id}: {field} must be true or false, got {value!r}")
    return value == "true"


def _parse(row: dict[str, str]) -> Case:
    case_id = row["id"]
    try:
        case = Case(
            id=case_id,
            input=row["input"],
            expected_category=Category(row["expected_category"]),
            expected_special_handling=_bool(
                row["expected_special_handling"], "expected_special_handling", case_id
            ),
            expected_decision=ExpectedDecision(row["expected_decision"]),
            rules_should_catch=_bool(row["rules_should_catch"], "rules_should_catch", case_id),
            tags=frozenset(t for t in row["tags"].split(";") if t),
            label_status=LabelStatus(row["label_status"]),
            notes=row["notes"],
        )
    except ValueError as exc:
        raise CaseError(f"{case_id}: {exc}") from exc
    _check_consistent(case)
    return case


def _check_consistent(case: Case) -> None:
    if not case.input.strip():
        raise CaseError(f"{case.id}: empty input")
    if case.expected_category in SPECIAL_HANDLING_CATEGORIES and not case.expected_special_handling:
        raise CaseError(f"{case.id}: {case.expected_category} always requires special handling")
    allowed = case.expected_category in APPROVED_CATEGORIES and not case.expected_special_handling
    expected = ExpectedDecision.ALLOW if allowed else ExpectedDecision.BLOCK
    if case.expected_decision is not expected:
        raise CaseError(f"{case.id}: expected_decision should be {expected} for this category")
    if case.rules_should_catch and case.expected_decision is ExpectedDecision.ALLOW:
        raise CaseError(f"{case.id}: rules_should_catch only applies to block cases")


def load_cases(path: Path = CASES_CSV) -> list[Case]:
    with path.open(newline="", encoding="utf-8") as f:
        cases = [_parse(row) for row in csv.DictReader(f)]
    ids = [c.id for c in cases]
    duplicates = {i for i in ids if ids.count(i) > 1}
    if duplicates:
        raise CaseError(f"duplicate case ids: {sorted(duplicates)}")
    return cases
