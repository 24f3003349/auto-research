"""High-level orchestrator: runs the research engine, populates the wiki,
records agents/metrics in the run repo, and emits bus events.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass

from app.agents.llm import LLMProvider
from app.backend.services.event_bus import EventBus
from app.backend.services.runs import RunRepo
from app.research.engine import ResearchEngine
from app.storage.db import Database
from app.wiki.service import WikiService, pages_from_run


@dataclass
class OrchestratorResult:
    run_id: str
    topic: str
    objective: str
    score: float
    pages: list
    result: dict


class Orchestrator:
    """Coordinates the pipeline and emits progress events on the bus."""

    def __init__(
        self,
        db: Database,
        provider: LLMProvider,
        bus: EventBus,
    ):
        self.db = db
        self.provider = provider
        self.bus = bus
        self.runs = RunRepo(db)
        self.wiki = WikiService(db)

    async def start_run(self, topic: str, objective: str) -> OrchestratorResult:
        run = self.runs.create_run(topic=topic, objective=objective)
        await self._publish(
            "run.started",
            run_id=run.id,
            topic=topic,
            objective=objective,
        )
        self.runs.update_status(run.id, "running")

        def hook(evt: dict) -> None:
            # Engine calls the hook synchronously; persist + schedule bus fanout.
            self._persist_agent_event_sync(run.id, evt)
            asyncio.create_task(self.bus.publish(evt))

        engine = ResearchEngine(provider=self.provider, hook=hook)
        result = await engine.run(topic=topic, objective=objective, run_id=run.id)

        self.runs.record_metric(run_id=run.id, name="score", value=result.score)
        self.runs.update_status(run.id, "completed")

        pages = pages_from_run(
            self.wiki,
            run_id=run.id,
            topic=topic,
            steps=result.steps,
            finding=result.finding,
            critique=result.critique,
            score=result.score,
        )
        await self._publish(
            "run.completed",
            run_id=run.id,
            score=result.score,
            wiki_pages=[p.id for p in pages],
        )
        return OrchestratorResult(
            run_id=run.id,
            topic=topic,
            objective=objective,
            score=result.score,
            pages=pages,
            result=result.to_dict(),
        )

    async def _publish(self, type_: str, **detail) -> None:
        await self.bus.publish({"type": type_, **detail})

    async def _persist_agent_event(self, run_id: str, evt: dict) -> None:
        # Backwards-compat alias; new code uses the sync version.
        self._persist_agent_event_sync(run_id, evt)

    def _persist_agent_event_sync(self, run_id: str, evt: dict) -> None:
        agent = evt.get("agent")
        if not agent:
            return
        detail = evt.get("detail", "")
        score = evt.get("score")
        output_str = "" if score is None else f"score={score}"
        try:
            self.runs.record_agent(
                run_id=run_id,
                role=agent,
                input=str(detail)[:200],
                output=output_str,
                state="completed",
            )
            if score is not None:
                self.runs.record_metric(
                    run_id=run_id, name=agent, value=float(score)
                )
        except Exception:
            pass