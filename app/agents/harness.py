"""Agent harness.

Five fixed roles (planner, researcher, coder, evaluator, critic). Each is a
prompt-driven async function over an LLMProvider. No LangGraph; plain control
flow keeps the MVP simple and testable.
"""
from __future__ import annotations

import json
from enum import Enum
from typing import Any

from app.agents.llm import LLMMessage, LLMProvider
from app.prompts.roles import (
    CODER_SYSTEM,
    CRITIC_SYSTEM,
    EVALUATOR_SYSTEM,
    PLANNER_SYSTEM,
    RESEARCHER_SYSTEM,
)


class AgentRole(str, Enum):
    PLANNER = "planner"
    RESEARCHER = "researcher"
    CODER = "coder"
    EVALUATOR = "evaluator"
    CRITIC = "critic"


async def _chat(
    provider: LLMProvider, system: str, user: str, *, temperature: float = 0.7
) -> str:
    resp = await provider.complete(
        [LLMMessage("system", system), LLMMessage("user", user)],
        temperature=temperature,
    )
    return resp.content.strip()


async def plan(topic: str, provider: LLMProvider) -> list[str]:
    raw = await _chat(
        provider,
        PLANNER_SYSTEM,
        f"Topic: {topic}\nReturn a JSON array of 3-7 steps.",
        temperature=0.2,
    )
    return _parse_steps(raw)


def _parse_steps(raw: str) -> list[str]:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.startswith("json"):
            raw = raw[len("json"):].strip()
    try:
        data = json.loads(raw)
        if isinstance(data, list):
            return [str(x) for x in data if str(x).strip()]
    except Exception:
        pass
    # Fallback: split lines.
    return [line.strip("- *").strip() for line in raw.splitlines() if line.strip()]


async def research(topic: str, steps: list[str], provider: LLMProvider) -> str:
    return await _chat(
        provider,
        RESEARCHER_SYSTEM,
        f"Topic: {topic}\nSteps: {steps}",
        temperature=0.5,
    )


async def code(spec: str, provider: LLMProvider) -> str:
    return await _chat(provider, CODER_SYSTEM, f"Spec: {spec}", temperature=0.3)


async def evaluate(artifact: str, objective: str, provider: LLMProvider) -> float:
    raw = await _chat(
        provider,
        EVALUATOR_SYSTEM,
        f"Artifact: {artifact}\nObjective: {objective}\nScore (0.0-1.0):",
        temperature=0.1,
    )
    try:
        return max(0.0, min(1.0, float(raw.strip().split()[0])))
    except (ValueError, IndexError):
        return 0.0


async def critique(artifact: str, objective: str, provider: LLMProvider) -> str:
    return await _chat(
        provider,
        CRITIC_SYSTEM,
        f"Artifact: {artifact}\nObjective: {objective}",
        temperature=0.4,
    )


async def run_agent(
    role: AgentRole,
    topic: str,
    provider: LLMProvider,
    **kwargs: Any,
) -> Any:
    """Dispatch helper used by the orchestrator."""
    if role is AgentRole.PLANNER:
        return await plan(topic, provider)
    if role is AgentRole.RESEARCHER:
        return await research(topic, kwargs.get("steps", []), provider)
    if role is AgentRole.CODER:
        return await code(kwargs.get("spec", topic), provider)
    if role is AgentRole.EVALUATOR:
        return await evaluate(
            kwargs.get("artifact", ""), kwargs.get("objective", ""), provider
        )
    if role is AgentRole.CRITIC:
        return await critique(
            kwargs.get("artifact", ""), kwargs.get("objective", ""), provider
        )
    raise ValueError(f"unknown role: {role}")