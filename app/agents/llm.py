"""Pluggable LLM provider interface.

Default provider is EchoProvider (offline, deterministic, used in tests and
when no API key is set). OpenAIProvider implements the OpenAI Chat API;
swap by setting OPENAI_API_KEY in the environment.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

import httpx


@dataclass
class LLMMessage:
    role: str
    content: str


@dataclass
class LLMResponse:
    content: str
    model: str
    usage: dict = field(default_factory=dict)
    raw: dict | None = None


@runtime_checkable
class LLMProvider(Protocol):
    async def complete(
        self, messages: list[LLMMessage], *, temperature: float = 0.7
    ) -> LLMResponse: ...


class EchoProvider:
    """Offline deterministic provider — echoes the last user message."""

    model = "echo"

    async def complete(
        self, messages: list[LLMMessage], *, temperature: float = 0.7
    ) -> LLMResponse:
        last_user = next(
            (m.content for m in reversed(messages) if m.role == "user"), ""
        )
        return LLMResponse(content=f"echo:{last_user}", model=self.model)


class OpenAIProvider:
    """Async OpenAI Chat Completions provider."""

    BASE_URL = "https://api.openai.com/v1/chat/completions"

    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
        self.api_key = api_key
        self.model = model
        self._client: httpx.AsyncClient | None = None

    def _require_key(self) -> None:
        if not self.api_key:
            raise ValueError("OpenAIProvider requires an api_key")

    def _build_body(self, messages: list[LLMMessage], *, temperature: float) -> str:
        return json.dumps(
            {
                "model": self.model,
                "temperature": temperature,
                "messages": [{"role": m.role, "content": m.content} for m in messages],
            }
        )

    async def complete(
        self, messages: list[LLMMessage], *, temperature: float = 0.7
    ) -> LLMResponse:
        self._require_key()
        body = self._build_body(messages, temperature=temperature)
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=60.0)
        resp = await self._client.post(self.BASE_URL, headers=headers, content=body)
        resp.raise_for_status()
        data = resp.json()
        choice = data["choices"][0]
        return LLMResponse(
            content=choice["message"]["content"],
            model=data.get("model", self.model),
            usage=data.get("usage", {}),
            raw=data,
        )


def get_provider(
    api_key: str | None = None, model: str | None = None
) -> LLMProvider:
    """Resolve the active provider.

    Prefers OpenAI when an API key is available, falls back to EchoProvider.
    """
    key = api_key or os.environ.get("OPENAI_API_KEY", "")
    if key:
        return OpenAIProvider(api_key=key, model=model or "gpt-4o-mini")
    return EchoProvider()