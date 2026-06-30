"""Tests for the research orchestrator (runs engine + wiki + emits events)."""
import asyncio

import pytest

from app.agents.llm import LLMProvider, LLMResponse
from app.backend.services.event_bus import EventBus
from app.backend.services.orchestrator import Orchestrator, OrchestratorResult
from app.storage.db import Database


class ScriptedProvider:
    """Cycles through a fixed list of replies; one per call."""

    def __init__(self, replies: list[str]):
        self.replies = list(replies)
        self.n = 0

    async def complete(self, messages, *, temperature=0.7):
        self.n += 1
        idx = min(self.n - 1, len(self.replies) - 1)
        return LLMResponse(content=self.replies[idx], model="echo")


@pytest.fixture
def setup(tmp_path):
    db = Database(tmp_path / "test.db")
    bus = EventBus()
    provider = ScriptedProvider(
        [
            '["define", "explore"]',          # planner
            "the finding is clear",           # researcher
            "def stub(): pass",               # coder
            "0.66",                           # evaluator
            "- not enough data",              # critic
        ]
    )
    return db, bus, provider


@pytest.mark.asyncio
async def test_orchestrator_creates_run_completes_run_and_writes_wiki(setup):
    db, bus, provider = setup
    events: list[dict] = []
    bus.subscribe(lambda e: events.append(e))
    orch = Orchestrator(db=db, provider=provider, bus=bus)
    result = await orch.start_run(topic="x", objective="y")
    # Let scheduled bus.publish tasks flush.
    for _ in range(10):
        await asyncio.sleep(0)
    assert isinstance(result, OrchestratorResult)
    assert result.run_id.startswith("run_")
    assert result.score == 0.66
    # Run should be marked completed.
    assert orch.runs.get_run(result.run_id).status == "completed"
    # Wiki should have auto-generated pages.
    pages = orch.wiki.list_pages()
    assert any("Finding" in p.title for p in pages)
    assert any("Run/" in p.title for p in pages)
    # Events should include key milestones.
    types = {e["type"] for e in events}
    assert "run.started" in types
    assert "agent.started" in types
    assert "run.completed" in types


@pytest.mark.asyncio
async def test_orchestrator_handles_evaluator_garbage(setup):
    db, bus, _ = setup
    # Build a provider whose evaluator reply is unparseable — score falls to 0.
    class MixedProvider:
        def __init__(self):
            self.responses = iter(
                [
                    LLMResponse(content='["a"]', model="echo"),
                    LLMResponse(content="finding", model="echo"),
                    LLMResponse(content="def x(): pass", model="echo"),
                    LLMResponse(content="not a float", model="echo"),
                    LLMResponse(content="- weak", model="echo"),
                ]
            )

        async def complete(self, messages, *, temperature=0.7):
            return next(self.responses)

    orch = Orchestrator(db=db, provider=MixedProvider(), bus=bus)
    result = await orch.start_run(topic="y", objective="z")
    assert result.score == 0.0