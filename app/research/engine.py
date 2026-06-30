"""Research engine: orchestrates planner -> researcher -> evaluator -> critic.

Returns a structured ResearchResult and emits events via the hook so the UI
can stream progress.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field, asdict
from typing import Any, Awaitable, Callable

from app.agents.harness import (
    AgentRole,
    code as agent_code,
    critique as agent_critique,
    evaluate as agent_evaluate,
    plan as agent_plan,
    research as agent_research,
)
from app.agents.llm import LLMProvider


EventHook = Callable[[dict], None]


@dataclass
class ResearchResult:
    run_id: str
    topic: str
    objective: str
    steps: list[str] = field(default_factory=list)
    hypothesis: str = ""
    finding: str = ""
    code: str = ""
    score: float = 0.0
    critique: str = ""
    artifacts: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


class ResearchEngine:
    def __init__(
        self,
        provider: LLMProvider,
        hook: EventHook | None = None,
        max_steps: int = 5,
    ):
        self.provider = provider
        self.hook = hook or (lambda e: None)
        self.max_steps = max_steps

    def _emit(self, type_: str, **detail: Any) -> None:
        try:
            self.hook({"type": type_, **detail})
        except Exception:
            # Hooks must never break the engine.
            pass

    async def run(
        self, topic: str, objective: str, run_id: str | None = None
    ) -> ResearchResult:
        run_id = run_id or "run_anon"
        result = ResearchResult(run_id=run_id, topic=topic, objective=objective)
        self._emit("run.started", run_id=run_id, topic=topic, objective=objective)

        # 1) Planner
        self._emit("agent.started", agent="planner", run_id=run_id)
        steps = await agent_plan(topic, self.provider)
        result.steps = steps[: self.max_steps]
        self._emit("agent.completed", agent="planner", run_id=run_id, detail=str(steps))

        # 2) Researcher (form a hypothesis-style finding)
        self._emit("agent.started", agent="researcher", run_id=run_id)
        result.finding = await agent_research(topic, result.steps, self.provider)
        result.hypothesis = (
            f"If {result.steps[0] if result.steps else 'we proceed'}, "
            f"then {result.finding[:120]}"
        )
        self._emit("agent.completed", agent="researcher", run_id=run_id)

        # 3) Coder (always produce a tiny prototype stub based on finding)
        self._emit("agent.started", agent="coder", run_id=run_id)
        result.code = await agent_code(
            spec=f"Smallest possible experiment capturing: {result.finding[:120]}",
            provider=self.provider,
        )
        self._emit("agent.completed", agent="coder", run_id=run_id)

        # 4) Evaluator (scored against objective)
        self._emit("agent.started", agent="evaluator", run_id=run_id)
        score = await agent_evaluate(
            artifact=result.code or result.finding,
            objective=objective,
            provider=self.provider,
        )
        result.score = score if score is not None else 0.0
        self._emit("agent.completed", agent="evaluator", run_id=run_id, score=result.score)

        # 5) Critic (actionable weaknesses)
        self._emit("agent.started", agent="critic", run_id=run_id)
        result.critique = await agent_critique(
            artifact=result.code or result.finding,
            objective=objective,
            provider=self.provider,
        )
        self._emit("agent.completed", agent="critic", run_id=run_id)

        # 6) Build a textual report (artifact)
        result.artifacts["report"] = _render_report(result)
        self._emit("run.completed", run_id=run_id, score=result.score)
        return result


def _render_report(r: ResearchResult) -> str:
    parts = [
        f"# Research Report — {r.topic}",
        f"**Objective:** {r.objective}",
        "",
        "## Plan",
        "\n".join(f"- {s}" for s in r.steps) or "- (no steps)",
        "",
        "## Hypothesis",
        r.hypothesis or "(none)",
        "",
        "## Finding",
        r.finding or "(none)",
        "",
        "## Prototype",
        "```python",
        r.code or "# no code",
        "```",
        "",
        "## Score",
        f"{r.score:.2f} / 1.00",
        "",
        "## Critic",
        r.critique or "(no critique)",
    ]
    return "\n".join(parts)