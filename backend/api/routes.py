"""Device-facing conversation endpoints (PRD §11, docs/API_SPEC.md).

Clients can only send a message. They cannot set prompts, models, tools, or generation
parameters, so there is no direct path to the LLM.
"""

import secrets
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field

from backend.conversation.manager import ConversationManager, ResponseSource
from backend.sessions.store import Session, SessionNotFound, SessionStore

router = APIRouter(prefix="/api/v1")

# Single development device until real credentials land in M5 (D-010).
DEV_DEVICE_ID = "dev-device"
MAX_MESSAGE_CHARS = 500


class MessageIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=MAX_MESSAGE_CHARS)


class MessageOut(BaseModel):
    text: str
    source: ResponseSource


class SessionOut(BaseModel):
    session_id: str


def require_device(request: Request, authorization: Annotated[str | None, Header()] = None) -> str:
    expected = request.app.state.settings.dev_device_token
    scheme, _, token = (authorization or "").partition(" ")
    if not expected or scheme != "Bearer" or not secrets.compare_digest(token, expected):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED)
    return DEV_DEVICE_ID


def get_sessions(request: Request) -> SessionStore:
    return request.app.state.sessions


def get_manager(request: Request) -> ConversationManager:
    return request.app.state.manager


DeviceId = Annotated[str, Depends(require_device)]
Sessions = Annotated[SessionStore, Depends(get_sessions)]


def _get_session(sessions: SessionStore, session_id: str, device_id: str) -> Session:
    try:
        return sessions.get(session_id, device_id)
    except SessionNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND) from None


@router.post("/sessions", status_code=status.HTTP_201_CREATED)
def create_session(device_id: DeviceId, sessions: Sessions) -> SessionOut:
    return SessionOut(session_id=sessions.create(device_id).id)


@router.post("/sessions/{session_id}/message")
async def send_message(
    session_id: str,
    body: MessageIn,
    device_id: DeviceId,
    sessions: Sessions,
    manager: Annotated[ConversationManager, Depends(get_manager)],
) -> MessageOut:
    session = _get_session(sessions, session_id, device_id)
    reply = await manager.handle_message(session, body.text)
    return MessageOut(text=reply.text, source=reply.source)


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def end_session(session_id: str, device_id: DeviceId, sessions: Sessions) -> None:
    try:
        sessions.delete(session_id, device_id)
    except SessionNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND) from None
