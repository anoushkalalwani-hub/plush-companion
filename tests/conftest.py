import pytest

from backend.audit.events import AuditLogger
from backend.config import Settings
from backend.conversation.manager import ConversationManager
from backend.safety.policy_engine import PolicyConfig
from backend.sessions.store import SessionStore
from tests.fakes import ScriptedClassifier, ScriptedLLM, ScriptedValidator


@pytest.fixture
def settings() -> Settings:
    return Settings(
        classifier_timeout_seconds=0.05,
        llm_timeout_seconds=0.05,
        validator_timeout_seconds=0.05,
        dev_device_token="test-token",
    )


@pytest.fixture
def sessions(settings: Settings) -> SessionStore:
    return SessionStore(
        max_turns=settings.session_max_turns,
        idle_timeout_seconds=settings.session_idle_timeout_seconds,
    )


@pytest.fixture
def make_manager(settings: Settings, sessions: SessionStore):
    """Build a manager where every stage allows by default; override one stage per test."""

    def _make(
        classifier=None,
        llm=None,
        validator=None,
        policy_config: PolicyConfig | None = None,
    ) -> ConversationManager:
        return ConversationManager(
            classifier=classifier or ScriptedClassifier(),
            llm=llm or ScriptedLLM(),
            validator=validator or ScriptedValidator(),
            sessions=sessions,
            audit=AuditLogger(),
            settings=settings,
            policy_config=policy_config or PolicyConfig(min_confidence=0.5),
        )

    return _make
