import pytest

from backend.llm.base import Role
from backend.sessions.store import SessionNotFound, SessionStore


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def store(clock: Clock) -> SessionStore:
    return SessionStore(max_turns=2, idle_timeout_seconds=60, clock=clock)


def test_create_and_get(store):
    session = store.create(device_id="d1")
    assert store.get(session.id, device_id="d1") is session


def test_session_ids_are_unique(store):
    assert store.create(device_id="d1").id != store.create(device_id="d1").id


def test_other_device_cannot_access_session(store):
    session = store.create(device_id="d1")
    with pytest.raises(SessionNotFound):
        store.get(session.id, device_id="d2")


def test_unknown_session(store):
    with pytest.raises(SessionNotFound):
        store.get("nope", device_id="d1")


def test_history_keeps_only_last_max_turns_exchanges(store):
    session = store.create(device_id="d1")
    for i in range(3):
        store.append_exchange(session, f"q{i}", f"a{i}")
    assert [(m.role, m.content) for m in session.history] == [
        (Role.USER, "q1"),
        (Role.ASSISTANT, "a1"),
        (Role.USER, "q2"),
        (Role.ASSISTANT, "a2"),
    ]


def test_idle_session_expires(store, clock):
    session = store.create(device_id="d1")
    clock.now += 61
    with pytest.raises(SessionNotFound):
        store.get(session.id, device_id="d1")


def test_activity_extends_session(store, clock):
    session = store.create(device_id="d1")
    clock.now += 50
    store.get(session.id, device_id="d1")
    clock.now += 50
    assert store.get(session.id, device_id="d1") is session


def test_expired_sessions_are_evicted_from_memory(store, clock):
    store.create(device_id="d1")
    clock.now += 61
    store.create(device_id="d1")
    assert len(store) == 1


def test_purge_context(store):
    session = store.create(device_id="d1")
    store.append_exchange(session, "q", "a")
    store.purge_context(session)
    assert session.history == []


def test_delete(store):
    session = store.create(device_id="d1")
    store.delete(session.id, device_id="d1")
    with pytest.raises(SessionNotFound):
        store.get(session.id, device_id="d1")


def test_delete_other_devices_session_is_not_found(store):
    session = store.create(device_id="d1")
    with pytest.raises(SessionNotFound):
        store.delete(session.id, device_id="d2")
    assert store.get(session.id, device_id="d1") is session
