"""In-memory session context (PRD §8.1, D-008). Never written to disk or the database."""

import secrets
import time
from collections.abc import Callable
from dataclasses import dataclass, field

from backend.llm.base import Message, Role


class SessionNotFound(Exception):
    """Unknown, expired, deleted, or owned by another device."""


@dataclass
class Session:
    id: str
    device_id: str
    last_active: float
    history: list[Message] = field(default_factory=list)


class SessionStore:
    def __init__(
        self,
        max_turns: int,
        idle_timeout_seconds: float,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._max_turns = max_turns
        self._idle_timeout = idle_timeout_seconds
        self._clock = clock
        self._sessions: dict[str, Session] = {}

    def __len__(self) -> int:
        return len(self._sessions)

    def create(self, device_id: str) -> Session:
        self._evict_expired()
        session = Session(
            id=secrets.token_urlsafe(16), device_id=device_id, last_active=self._clock()
        )
        self._sessions[session.id] = session
        return session

    def get(self, session_id: str, device_id: str) -> Session:
        session = self._sessions.get(session_id)
        if session is None or session.device_id != device_id:
            raise SessionNotFound
        if self._is_expired(session):
            del self._sessions[session_id]
            raise SessionNotFound
        session.last_active = self._clock()
        return session

    def delete(self, session_id: str, device_id: str) -> None:
        self.get(session_id, device_id)
        del self._sessions[session_id]

    def append_exchange(self, session: Session, user_text: str, reply_text: str) -> None:
        session.history.extend([Message(Role.USER, user_text), Message(Role.ASSISTANT, reply_text)])
        keep = 2 * self._max_turns
        session.history[:] = session.history[-keep:] if keep > 0 else []

    def purge_context(self, session: Session) -> None:
        session.history.clear()

    def _is_expired(self, session: Session) -> bool:
        return self._clock() - session.last_active > self._idle_timeout

    def _evict_expired(self) -> None:
        for session_id in [s.id for s in self._sessions.values() if self._is_expired(s)]:
            del self._sessions[session_id]
