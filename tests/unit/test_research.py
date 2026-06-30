"""Tests for the research engine."""
import json

import pytest

from app.agents.harness import AgentRole
from app.agents.llm import LLMResponse
from app.research.engine import ResearchEngine, ResearchResult


class ScriptedProvider:
    """Returns a fixed sequence of LLM replies, one per call."""

    def __init__(self, replies: list[LLMResponse]):
        self.replies = list(replies)
        self.calls: list[tuple[str, str]] = []

    async def complete(self, messages, *, temperature=0.7):
        self.calls.append((messages[0].content[:40], messages[-1].content[:60]))
        return self.replies.pop(0)


@pytest.mark.asyncio
async def test_engine_runs_full_pipeline():
    p = ScriptedProvider(
        [
            LLMResponse(content='["define problem", "explore", "summarize"]', model="echo"),
            LLMResponse(content="finding text", model="echo"),
            LLMResponse(content="def tiny(): pass", model="echo"),
            LLMResponse(content="0.91", model="echo"),
            LLMResponse(content="- risk: insufficient data", model="echo"),
        ]
    )
    events: list[tuple[str, str]] = []
    engine = ResearchEngine(
        provider=p,
        hook=lambda evt: events.append((evt["type"], evt.get("detail", ""))),
    )
    result = await engine.run(topic="x", objective="y", run_id="r1")

    assert isinstance(result, ResearchResult)
    assert result.run_id == "r1"
    assert result.steps == ["define problem", "explore", "summarize"]
    assert result.finding == "finding text"
    assert result.score == 0.91
    assert result.critique.startswith("- risk")
    assert any(e[0] == "agent.started" for e in events)
    assert any(e[0] == "agent.completed" for e in events)
    assert any(e[0] == "run.completed" for e in events)


@pytest.mark.asyncio
async def test_engine_continues_when_evaluator_fails():
    """Bad evaluator output should default to 0.0, not crash the pipeline."""
    p = ScriptedProvider(
        [
            LLMResponse(content='["a"]', model="echo"),
            LLMResponse(content="finding", model="echo"),
            LLMResponse(content="def stub(): pass", model="echo"),
            LLMResponse(content="not a number", model="echo"),
            LLMResponse(content="- ok", model="echo"),
        ]
    )
    engine = ResearchEngine(provider=p)
    result = await engine.run(topic="x", objective="y", run_id="r1")
    assert result.score == 0.0
    assert result.critique == "- ok"