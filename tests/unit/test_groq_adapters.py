"""Groq adapters against simulated HTTP. No test here touches the network."""

import json

import httpx
import pytest

from backend.llm.base import GenerationConstraints, LLMError, Message, Role
from backend.llm.groq import (
    REASONING_TOKEN_ALLOWANCE,
    GroqClient,
    GroqConfig,
    GroqConfigError,
    GroqJudge,
    GroqLLMProvider,
    GroqModeration,
    strict_schema,
)
from backend.safety.classifier import Category, ClassificationResult
from backend.safety.judge_prompts import CLASSIFICATION_SCHEMA, VALIDATION_SCHEMA
from backend.safety.layered_classifier import LayeredClassifier
from backend.safety.moderation_policy import MODERATION_POLICY

CONFIG = GroqConfig(
    api_key="test-key",
    chat_model="chat-model",
    judge_model="judge-model",
    moderation_model="guard-model",
)
CONSTRAINTS = GenerationConstraints(max_output_tokens=120, timeout_seconds=5.0)


def _completion(content, finish_reason="stop", **message_extra):
    return {
        "choices": [
            {
                "message": {"role": "assistant", "content": content, **message_extra},
                "finish_reason": finish_reason,
            }
        ]
    }


class FakeGroq:
    """Records requests and replies with queued responses, keyed by model."""

    def __init__(self, responses=None, status=200, exc=None):
        self.responses = responses or {}
        self.status = status
        self.exc = exc
        self.requests: list[httpx.Request] = []

    def payloads(self) -> list[dict]:
        return [json.loads(r.content) for r in self.requests]

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self.exc:
            raise self.exc
        model = json.loads(request.content)["model"]
        body = self.responses.get(model, _completion("ok"))
        if isinstance(body, str):
            return httpx.Response(self.status, text=body)
        return httpx.Response(self.status, json=body)

    def client(self) -> GroqClient:
        http = httpx.AsyncClient(
            transport=httpx.MockTransport(self.handler), base_url="https://groq.test/openai/v1"
        )
        return GroqClient(CONFIG, http=http)


async def _generate(fake: FakeGroq):
    provider = GroqLLMProvider(fake.client(), CONFIG)
    messages = [Message(Role.SYSTEM, "be kind"), Message(Role.USER, "why is the sky blue?")]
    return await provider.generate(messages, CONSTRAINTS)


# Reply generation


async def test_generate_request_shape():
    fake = FakeGroq({"chat-model": _completion("Sunlight scatters!")})
    result = await _generate(fake)

    assert result.text == "Sunlight scatters!"
    request = fake.requests[0]
    assert request.url.path.endswith("/chat/completions")
    assert request.headers["authorization"] == "Bearer test-key"
    payload = fake.payloads()[0]
    assert payload == {
        "model": "chat-model",
        "messages": [
            {"role": "system", "content": "be kind"},
            {"role": "user", "content": "why is the sky blue?"},
        ],
        "max_completion_tokens": 120 + REASONING_TOKEN_ALLOWANCE,
        "reasoning_effort": "low",
        "include_reasoning": False,
        "stream": False,
    }


@pytest.mark.parametrize("key", ["tools", "tool_choice", "response_format"])
async def test_generate_never_sends_tools(key):
    fake = FakeGroq()
    await _generate(fake)
    assert key not in fake.payloads()[0]


@pytest.mark.parametrize(
    "fake",
    [
        FakeGroq({"chat-model": _completion("cut off", finish_reason="length")}),
        FakeGroq({"chat-model": _completion(None, finish_reason="tool_calls")}),
        FakeGroq({"chat-model": _completion("hi", tool_calls=[{"id": "1"}])}),
        FakeGroq({"chat-model": _completion(None)}),
        FakeGroq({"chat-model": {"choices": []}}),
        FakeGroq({"chat-model": {"unexpected": True}}),
        FakeGroq({"chat-model": "<html>not json</html>"}),
        FakeGroq(status=429),
        FakeGroq(status=500),
        FakeGroq(exc=httpx.ConnectError("no route")),
        FakeGroq(exc=httpx.ReadTimeout("slow")),
    ],
    ids=[
        "length",
        "tool-calls-finish",
        "tool-calls-present",
        "null-content",
        "no-choices",
        "wrong-shape",
        "not-json",
        "rate-limited",
        "server-error",
        "connect-error",
        "timeout",
    ],
)
async def test_generate_failures_raise_llm_error(fake):
    with pytest.raises(LLMError):
        await _generate(fake)


async def test_error_messages_never_include_response_body():
    body = {
        "error": {"message": "bad input: why is the sky blue?", "type": "invalid_request_error"}
    }
    fake = FakeGroq({"chat-model": body}, status=400)
    with pytest.raises(LLMError) as info:
        await _generate(fake)
    assert "sky" not in str(info.value)
    assert info.value.__cause__ is None


# Judge


async def test_judge_sends_strict_schema_and_parses_json():
    verdict = {
        "category": "education",
        "risk_level": "low",
        "requires_special_handling": False,
        "confidence": 0.9,
    }
    fake = FakeGroq({"judge-model": _completion(json.dumps(verdict))})
    judge = GroqJudge(fake.client(), CONFIG)

    result = await judge.judge("label it", "bees?", CLASSIFICATION_SCHEMA)

    assert result == verdict
    payload = fake.payloads()[0]
    assert payload["model"] == "judge-model"
    assert payload["messages"] == [
        {"role": "system", "content": "label it"},
        {"role": "user", "content": "bees?"},
    ]
    assert payload["response_format"] == {
        "type": "json_schema",
        "json_schema": {
            "name": "judgement",
            "strict": True,
            "schema": strict_schema(CLASSIFICATION_SCHEMA),
        },
    }
    assert payload["include_reasoning"] is False
    assert "tools" not in payload


@pytest.mark.parametrize("content", ["not json", "[1, 2]", '"education"'])
async def test_judge_rejects_non_object_output(content):
    fake = FakeGroq({"judge-model": _completion(content)})
    with pytest.raises(LLMError):
        await GroqJudge(fake.client(), CONFIG).judge("x", "y", VALIDATION_SCHEMA)


# Strict schema conversion


def _walk(node):
    yield node
    if isinstance(node, dict):
        for value in node.values():
            yield from _walk(value)
    elif isinstance(node, list):
        for value in node:
            yield from _walk(value)


@pytest.mark.parametrize("schema", [CLASSIFICATION_SCHEMA, VALIDATION_SCHEMA])
def test_strict_schema_meets_groq_strict_mode_rules(schema):
    strict = strict_schema(schema)
    for node in _walk(strict):
        if not isinstance(node, dict):
            continue
        assert "$ref" not in node and "$defs" not in node
        if node.get("type") == "object":
            assert node["additionalProperties"] is False
            assert set(node["required"]) == set(node["properties"])


def test_strict_schema_inlines_enums():
    strict = strict_schema(CLASSIFICATION_SCHEMA)
    assert strict["properties"]["category"]["enum"] == [c.value for c in Category]


def test_strict_schema_keeps_property_named_title():
    schema = {
        "type": "object",
        "title": "Book",
        "properties": {"title": {"type": "string", "title": "Title"}},
    }
    assert strict_schema(schema)["properties"] == {"title": {"type": "string"}}


# Moderation


async def _moderate(content):
    fake = FakeGroq({"guard-model": _completion(content)})
    result = await GroqModeration(fake.client(), CONFIG).moderate("some text")
    return result, fake.payloads()[0]


async def test_moderation_request_shape():
    _, payload = await _moderate('{"violation": false, "category": "none"}')
    assert payload["model"] == "guard-model"
    assert payload["messages"] == [
        {"role": "system", "content": MODERATION_POLICY},
        {"role": "user", "content": "some text"},
    ]
    assert payload["response_format"] == {"type": "json_object"}
    assert "tools" not in payload


@pytest.mark.parametrize(
    ("content", "flagged", "categories"),
    [
        ('{"violation": false, "category": "none"}', False, set()),
        ('{"violation": true, "category": "self_harm"}', True, {Category.SELF_HARM}),
        ('{"violation": 1, "category": "medical"}', True, {Category.MEDICAL}),
        ('{"violation": 0, "category": "none"}', False, set()),
        ('{"violation": true, "category": "none"}', True, set()),
        ('{"violation": false, "category": "sexual_content"}', True, {Category.SEXUAL_CONTENT}),
        ('{"violation": true, "category": "space_lasers"}', True, set()),
        ('{"violation": false, "category": "education"}', True, set()),
    ],
    ids=[
        "clean",
        "flagged",
        "int-true",
        "int-false",
        "flag-without-category",
        "category-without-flag",
        "unknown-category",
        "approved-category",
    ],
)
async def test_moderation_parsing_is_strictest(content, flagged, categories):
    result, _ = await _moderate(content)
    assert result.flagged is flagged
    assert result.categories == frozenset(categories)


@pytest.mark.parametrize(
    "content",
    [
        "not json",
        '{"violation": "yes", "category": "none"}',
        '{"violation": 2, "category": "none"}',
        '{"category": "none"}',
        '{"violation": false}',
        '{"violation": false, "category": "none", "extra": 1}',
        "[]",
    ],
)
async def test_moderation_malformed_output_raises(content):
    with pytest.raises(LLMError):
        await _moderate(content)


# Wiring into the layered classifier


async def test_layered_classifier_runs_on_groq_adapters():
    verdict = {
        "category": "animals_and_nature",
        "risk_level": "low",
        "requires_special_handling": False,
        "confidence": 0.97,
    }
    fake = FakeGroq(
        {
            "judge-model": _completion(json.dumps(verdict)),
            "guard-model": _completion('{"violation": false, "category": "none"}'),
        }
    )
    client = fake.client()
    classifier = LayeredClassifier(
        moderation=GroqModeration(client, CONFIG), judge=GroqJudge(client, CONFIG)
    )

    result = await classifier.classify("what do bees eat")

    assert result == ClassificationResult(**verdict)
    assert {p["model"] for p in fake.payloads()} == {"judge-model", "guard-model"}


# Config


def test_config_from_env():
    env = {
        "GROQ_API_KEY": "k",
        "GROQ_CHAT_MODEL": "c",
        "GROQ_JUDGE_MODEL": "j",
        "GROQ_MODERATION_MODEL": "m",
    }
    config = GroqConfig.from_env(env)
    assert (config.api_key, config.chat_model, config.judge_model, config.moderation_model) == (
        "k",
        "c",
        "j",
        "m",
    )


def test_config_requires_every_setting_and_never_echoes_values():
    with pytest.raises(GroqConfigError) as info:
        GroqConfig.from_env({"GROQ_API_KEY": "secret-value", "GROQ_CHAT_MODEL": ""})
    message = str(info.value)
    assert "GROQ_JUDGE_MODEL" in message and "GROQ_CHAT_MODEL" in message
    assert "secret-value" not in message


def test_config_repr_hides_api_key():
    assert "test-key" not in repr(CONFIG)
