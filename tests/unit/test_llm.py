"""Tests for LLM provider layer."""
import json

import pytest

from app.agents.llm import (
    LLMMessage,
    LLMProvider,
    LLMResponse,
    EchoProvider,
    OpenAIProvider,
    get_provider,
)


def test_llm_message_to_openai_payload():
    msgs = [
        LLMMessage(role="system", content="be helpful"),
        LLMMessage(role="user", content="hello"),
    ]
    out = msgs_to_openai(msgs)
    assert out == [
        {"role": "system", "content": "be helpful"},
        {"role": "user", "content": "hello"},
    ]


def msgs_to_openai(msgs):
    return [{"role": m.role, "content": m.content} for m in msgs]


@pytest.mark.asyncio
async def test_echo_provider_returns_message():
    p = EchoProvider()
    r = await p.complete([LLMMessage("user", "ping")])
    assert r.content == "echo:ping"
    assert r.model == "echo"


@pytest.mark.asyncio
async def test_echo_provider_is_default_when_no_key():
    p = get_provider(api_key=None)
    assert isinstance(p, EchoProvider)


def test_openai_provider_requires_api_key():
    p = OpenAIProvider(api_key="", model="gpt-4o-mini")
    with pytest.raises(ValueError, match="api_key"):
        p._require_key()


def test_openai_provider_builds_request_body():
    p = OpenAIProvider(api_key="sk-test", model="gpt-4o-mini")
    body = p._build_body(
        [LLMMessage("user", "hi")], temperature=0.5
    )
    parsed = json.loads(body)
    assert parsed["model"] == "gpt-4o-mini"
    assert parsed["temperature"] == 0.5
    assert parsed["messages"] == [{"role": "user", "content": "hi"}]


@pytest.mark.asyncio
async def test_openai_provider_parses_response(monkeypatch):
    p = OpenAIProvider(api_key="sk-test", model="gpt-4o-mini")

    class FakeResp:
        status_code = 200
        text = json.dumps(
            {
                "choices": [
                    {"message": {"content": "hello back"}, "finish_reason": "stop"}
                ],
                "usage": {"prompt_tokens": 3, "completion_tokens": 2, "total_tokens": 5},
                "model": "gpt-4o-mini-2024-07-18",
            }
        )

        def raise_for_status(self):
            return None

        def json(self):
            return json.loads(self.text)

    class FakeClient:
        async def post(self, url, headers=None, content=None):
            return FakeResp()

        async def aclose(self):
            return None

    p._client = FakeClient()
    r = await p.complete([LLMMessage("user", "hi")])
    assert r.content == "hello back"
    assert r.model == "gpt-4o-mini-2024-07-18"
    assert r.usage == {"prompt_tokens": 3, "completion_tokens": 2, "total_tokens": 5}