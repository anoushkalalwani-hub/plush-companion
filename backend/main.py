"""FastAPI app factory. Run with: uv run uvicorn backend.main:create_app --factory"""

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from backend.api.routes import router
from backend.audit.events import AuditLogger
from backend.config import Settings
from backend.conversation.manager import ConversationManager
from backend.llm.base import LLMProvider
from backend.llm.fake_provider import FakeLLMProvider
from backend.safety.classifier import Classifier, StubClassifier
from backend.safety.policy_engine import PolicyConfig
from backend.safety.validator import StubValidator, Validator
from backend.sessions.store import SessionStore


async def _validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    # FastAPI's default 422 body echoes the submitted input, which may be the child's words.
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content={"detail": "invalid request"},
    )


def create_app(
    settings: Settings | None = None,
    *,
    classifier: Classifier | None = None,
    llm: LLMProvider | None = None,
    validator: Validator | None = None,
    policy_config: PolicyConfig | None = None,
) -> FastAPI:
    settings = settings or Settings.from_env()
    if settings.llm_provider_mode != "fake":
        raise RuntimeError(
            f"LLM provider mode {settings.llm_provider_mode!r} is not available: live providers "
            "arrive in M2 and need D-003 answered first"
        )

    sessions = SessionStore(
        max_turns=settings.session_max_turns,
        idle_timeout_seconds=settings.session_idle_timeout_seconds,
    )
    app = FastAPI(title="Plush Companion")
    app.state.settings = settings
    app.state.sessions = sessions
    app.state.manager = ConversationManager(
        classifier=classifier or StubClassifier(),
        llm=llm or FakeLLMProvider(),
        validator=validator or StubValidator(),
        sessions=sessions,
        audit=AuditLogger(),
        settings=settings,
        policy_config=policy_config or PolicyConfig(),
    )
    app.add_exception_handler(RequestValidationError, _validation_error)
    app.include_router(router)
    return app
