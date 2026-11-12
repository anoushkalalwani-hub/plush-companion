"""Structural checks for the invariants in docs/ARCHITECTURE.md."""

import ast
import dataclasses
from pathlib import Path

from backend.audit.events import SafetyEvent

BACKEND = Path(__file__).resolve().parents[2] / "backend"

# Invariant 3: only the conversation manager may call LLMProvider.generate.
GENERATE_CALLERS_ALLOWED = {BACKEND / "conversation" / "manager.py"}

# Judge output is parsed into labels and never spoken, so only the two layered checks may call it.
JUDGE_CALLERS_ALLOWED = {
    BACKEND / "safety" / "layered_classifier.py",
    BACKEND / "safety" / "layered_validator.py",
}


def _call_sites(method: str) -> set[Path]:
    callers = set()
    for path in BACKEND.rglob("*.py"):
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == method
            ):
                callers.add(path)
    return callers


def test_only_conversation_manager_calls_generate():
    # Equality, not subset: also guards against passing vacuously after a rename.
    assert _call_sites("generate") == GENERATE_CALLERS_ALLOWED


def test_only_layered_checks_call_judge():
    assert _call_sites("judge") == JUDGE_CALLERS_ALLOWED


def test_safety_event_has_no_content_fields():
    # Invariant 7 / D-009: the audit event type cannot carry text.
    fields = {f.name for f in dataclasses.fields(SafetyEvent)}
    assert fields.isdisjoint({"text", "transcript", "response", "message", "content", "audio"})
