"""GroqCloud adapters (D-016): reply generation, judge calls, and moderation.

The only Groq-specific code in the project. Uses the OpenAI-compatible chat completions API
directly with httpx so every request field is explicit:

- No `tools`, `tool_choice`, or built-in tools are ever sent, and a response containing tool
  calls is rejected.
- Reasoning is never returned (`include_reasoning: false`).
- Errors carry status codes and exception class names only, never response bodies, which may
  echo the child's words.

Models have no defaults and must be configured before live use.
"""

import json
import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict, ValidationError, field_validator

from backend.llm.base import GenerationConstraints, GenerationResult, LLMError, Message
from backend.safety.classifier import Category
from backend.safety.moderation import ModerationResult
from backend.safety.moderation_policy import (
    MODERATION_LABELS,
    MODERATION_POLICY,
    NO_VIOLATION_LABEL,
)

GROQ_BASE_URL = "https://api.groq.com/openai/v1"

# gpt-oss models reason before answering. Groq doesn't state whether reasoning tokens count
# against max_completion_tokens on chat completions, so reserve room for them; the output
# validator enforces the real length limit. Revisit after the first live run (PR D).
REASONING_TOKEN_ALLOWANCE = 512
JUDGE_MAX_TOKENS = 1024


class GroqConfigError(ValueError):
    pass


@dataclass(frozen=True)
class GroqConfig:
    api_key: str = field(repr=False)
    chat_model: str
    judge_model: str
    moderation_model: str
    chat_reasoning_effort: str = "low"
    judge_reasoning_effort: str = "medium"
    moderation_reasoning_effort: str = "low"
    timeout_seconds: float = 10.0

    @classmethod
    def from_env(cls, env: Mapping[str, str] = os.environ) -> "GroqConfig":
        names = ("GROQ_API_KEY", "GROQ_CHAT_MODEL", "GROQ_JUDGE_MODEL", "GROQ_MODERATION_MODEL")
        missing = [name for name in names if not env.get(name)]
        if missing:
            raise GroqConfigError(f"missing settings: {', '.join(missing)}")
        return cls(
            api_key=env["GROQ_API_KEY"],
            chat_model=env["GROQ_CHAT_MODEL"],
            judge_model=env["GROQ_JUDGE_MODEL"],
            moderation_model=env["GROQ_MODERATION_MODEL"],
        )


class GroqClient:
    def __init__(self, config: GroqConfig, http: httpx.AsyncClient | None = None) -> None:
        self._config = config
        self._http = http or httpx.AsyncClient(base_url=GROQ_BASE_URL)

    async def aclose(self) -> None:
        await self._http.aclose()

    async def complete(self, payload: dict[str, Any], timeout: float | None = None) -> str:
        """POST a chat completion and return the assistant text, or raise LLMError."""
        try:
            response = await self._http.post(
                "/chat/completions",
                json=payload,
                headers={"Authorization": f"Bearer {self._config.api_key}"},
                timeout=timeout or self._config.timeout_seconds,
            )
        except httpx.HTTPError as exc:
            raise LLMError(f"groq request failed: {type(exc).__name__}") from None
        if response.status_code != 200:
            raise LLMError(f"groq http {response.status_code}")

        try:
            choice = response.json()["choices"][0]
            message, finish_reason = choice["message"], choice["finish_reason"]
        except (ValueError, KeyError, IndexError, TypeError):
            raise LLMError("groq malformed response") from None
        if finish_reason != "stop" or message.get("tool_calls"):
            raise LLMError("groq response did not finish normally")
        content = message.get("content")
        if not isinstance(content, str):
            raise LLMError("groq response has no text")
        return content


def _messages(system: str, user: str) -> list[dict[str, str]]:
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def _parse_object(content: str) -> dict[str, Any]:
    try:
        data = json.loads(content)
    except ValueError:
        raise LLMError("groq returned invalid JSON") from None
    if not isinstance(data, dict):
        raise LLMError("groq returned JSON that is not an object")
    return data


class GroqLLMProvider:
    def __init__(self, client: GroqClient, config: GroqConfig) -> None:
        self._client = client
        self._config = config

    async def generate(
        self, messages: Sequence[Message], constraints: GenerationConstraints
    ) -> GenerationResult:
        payload = {
            "model": self._config.chat_model,
            "messages": [{"role": m.role.value, "content": m.content} for m in messages],
            "max_completion_tokens": constraints.max_output_tokens + REASONING_TOKEN_ALLOWANCE,
            "reasoning_effort": self._config.chat_reasoning_effort,
            "include_reasoning": False,
            "stream": False,
        }
        text = await self._client.complete(payload, timeout=constraints.timeout_seconds)
        return GenerationResult(text=text)


class GroqJudge:
    def __init__(self, client: GroqClient, config: GroqConfig) -> None:
        self._client = client
        self._config = config

    async def judge(self, instructions: str, content: str, schema: dict) -> dict:
        payload = {
            "model": self._config.judge_model,
            "messages": _messages(instructions, content),
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "judgement",
                    "strict": True,
                    "schema": strict_schema(schema),
                },
            },
            "max_completion_tokens": JUDGE_MAX_TOKENS,
            "reasoning_effort": self._config.judge_reasoning_effort,
            "include_reasoning": False,
            "stream": False,
        }
        return _parse_object(await self._client.complete(payload))


class _SafeguardVerdict(BaseModel):
    model_config = ConfigDict(extra="forbid")

    violation: bool
    category: str

    @field_validator("violation", mode="before")
    @classmethod
    def _bool_or_zero_one(cls, value: object) -> bool:
        # Groq's safeguard examples use 1/0; accept those and real booleans, nothing else.
        if value in (True, False) and isinstance(value, bool | int):
            return bool(value)
        raise ValueError("violation must be a boolean or 0/1")


class GroqModeration:
    """Moderation through Groq's safeguard model with our policy (D-016)."""

    def __init__(self, client: GroqClient, config: GroqConfig) -> None:
        self._client = client
        self._config = config

    async def moderate(self, text: str) -> ModerationResult:
        payload = {
            "model": self._config.moderation_model,
            "messages": _messages(MODERATION_POLICY, text),
            "response_format": {"type": "json_object"},
            "max_completion_tokens": JUDGE_MAX_TOKENS,
            "reasoning_effort": self._config.moderation_reasoning_effort,
            "include_reasoning": False,
            "stream": False,
        }
        data = _parse_object(await self._client.complete(payload))
        try:
            verdict = _SafeguardVerdict.model_validate(data)
        except ValidationError:
            raise LLMError("groq moderation output malformed") from None

        # Strictest reading: a restricted label flags even without violation=true, and an
        # unknown label always flags (reported without a category, so it maps to unclassifiable).
        category: Category | None = MODERATION_LABELS.get(verdict.category)
        known = category is not None or verdict.category == NO_VIOLATION_LABEL
        flagged = verdict.violation or category is not None or not known
        return ModerationResult(
            flagged=flagged, categories=frozenset({category}) if category else frozenset()
        )


_DROPPED_KEYWORDS = {"$defs", "title", "description", "default", "minimum", "maximum"}


def strict_schema(schema: dict) -> dict:
    """Convert a pydantic JSON schema into the form Groq's strict mode requires.

    Inlines $refs, drops annotation and range keywords (ranges are re-checked by pydantic after
    parsing), and makes every object closed with all properties required.
    """
    defs = schema.get("$defs", {})

    def convert(node: Any) -> Any:
        if isinstance(node, list):
            return [convert(item) for item in node]
        if not isinstance(node, dict):
            return node
        if "$ref" in node:
            return convert(defs[node["$ref"].rsplit("/", 1)[-1]])
        out: dict[str, Any] = {}
        for key, value in node.items():
            if key == "properties":
                out[key] = {name: convert(sub) for name, sub in value.items()}
            elif key not in _DROPPED_KEYWORDS:
                out[key] = convert(value)
        if out.get("type") == "object":
            out["additionalProperties"] = False
            out["required"] = list(out.get("properties", {}))
        return out

    return convert(schema)
