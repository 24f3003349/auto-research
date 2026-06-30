"""Tests for the agent harness."""
import json

import pytest

from app.agents.llm import LLMMessage, LLMProvider, LLMResponse
from app.agents.harness import (
    AgentRole,
    plan,
    research,
    code,
    evaluate,
    critique,
    run_agent,
    PLANNER_SYSTEM,
    RESEARCHER_SYSTEM,
    CODER_SYSTEM,
    EVALUATOR_SYSTEM,
    CRITIC_SYSTEM,
)


class ScriptedProvider:
    """Provider that returns canned responses, optionally indexed by user msg."""

    def __init__(self, replies: list[LLMResponse]):
        self.replies = list(replies)
        self.calls: list[list[LLMMessage]] = []

    async def complete(self, messages, *, temperature=0.7):
        self.calls.append(list(messages))
        return self.replies.pop(0)


@pytest.mark.asyncio
async def test_plan_returns_list_of_steps():
    p = ScriptedProvider(
        [LLMResponse(content='["define problem", "collect data", "summarize"]', model="echo")]
    )
    steps = await plan("reduce churn", provider=p)
    assert steps == ["define problem", "collect data", "summarize"]
    # system + user
    assert p.calls[0][0].role == "system"
    assert p.calls[0][0].content == PLANNER_SYSTEM


@pytest.mark.asyncio
async def test_research_returns_finding():
    p = ScriptedProvider([LLMResponse(content="we found X", model="echo")])
    out = await research(topic="ml", steps=["s1"], provider=p)
    assert out == "we found X"


@pytest.mark.asyncio
async def test_code_returns_implementation():
    p = ScriptedProvider([LLMResponse(content="def f(): pass", model="echo")])
    out = await code(spec="f(x) returns y", provider=p)
    assert out == "def f(): pass"
    assert p.calls[0][0].content == CODER_SYSTEM


@pytest.mark.asyncio
async def test_evaluate_returns_float_score():
    p = ScriptedProvider([LLMResponse(content="0.82", model="echo")])
    score = await evaluate(artifact="bla", objective="min cost", provider=p)
    assert score == 0.82


@pytest.mark.asyncio
async def test_critique_returns_actionable_notes():
    p = ScriptedProvider([LLMResponse(content="- missing baseline\n- needs more data", model="echo")])
    notes = await critique(artifact="x", objective="y", provider=p)
    assert notes.startswith("- missing")


@pytest.mark.asyncio
async def test_run_agent_dispatches_by_role():
    p = ScriptedProvider([
        LLMResponse(content='["a", "b"]', model="echo"),  # planner
        LLMResponse(content="finding", model="echo"),     # researcher
    ])
    out = await run_agent(
        AgentRole.PLANNER, topic="x", provider=p
    )
    assert out == ["a", "b"]


def test_role_enum_values():
    assert AgentRole.PLANNER.value == "planner"
    assert AgentRole.RESEARCHER.value == "researcher"
    assert AgentRole.CODER.value == "coder"
    assert AgentRole.EVALUATOR.value == "evaluator"
    assert AgentRole.CRITIC.value == "critic"