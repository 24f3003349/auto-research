"""JSON API + WebSocket routes.

The HTTP surface is intentionally small: runs, agents, wiki, search, and
evolution. Long-running research goes through the background queue.
Live updates stream over /ws.
"""
from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, HTTPException, Request, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from app.backend.services.orchestrator import Orchestrator
from app.backend.services.queue import JobStatus
from app.evolution.engine import EvolutionEngine, llm_fitness_for_prompts


api_router = APIRouter()
ws_router = APIRouter()


# --- Schemas ---


class CreateRunRequest(BaseModel):
    topic: str
    objective: str | None = None
    constraints: str | None = None
    config: dict | None = None


class CreatePageRequest(BaseModel):
    title: str
    body: str
    tags: list[str] | str | None = None
    source: str | None = None
    run_id: str | None = None


class UpdatePageRequest(BaseModel):
    title: str | None = None
    body: str | None = None
    tags: list[str] | str | None = None


class EvolutionRequest(BaseModel):
    seed: str = "seed text"
    pop_size: int = Field(default=6, ge=2, le=64)
    generations: int = Field(default=5, ge=1, le=100)
    mutation_rate: float = Field(default=0.05, ge=0.0, le=1.0)
    plateau_window: int = Field(default=3, ge=2, le=20)
    fitness_kind: str = Field(default="length")  # "length" | "diversity" | "fixed"


# --- Helpers ---


def _db(request: Request):
    return request.app.state.db


def _bus(request: Request):
    return request.app.state.bus


def _orch(request: Request) -> Orchestrator:
    return request.app.state.orchestrator


def _queue(request: Request):
    return request.app.state.queue


# --- Routes: runs ---


@api_router.get("/runs")
def list_runs(request: Request):
    runs = _orch(request).runs.list_runs()
    return [r.__dict__ for r in runs]


@api_router.post("/runs")
async def create_run(request: Request, body: CreateRunRequest):
    orch = _orch(request)
    queue = _queue(request)

    # Create the run row up front so the client can poll by id immediately.
    run = orch.runs.create_run(
        topic=body.topic,
        objective=body.objective,
        constraints=body.constraints,
        config=body.config,
    )
    run_id = run.id

    async def task(run_id=run_id):
        return await orch.start_run(
            topic=body.topic,
            objective=body.objective or "",
            run_id=run_id,
        )

    job = await queue.submit(task)
    return {"id": run_id, "job_id": job.id}


@api_router.get("/runs/{run_id}")
def get_run(request: Request, run_id: str):
    runs = _orch(request).runs
    run = runs.get_run(run_id)
    if run is None:
        raise HTTPException(404, "run not found")
    out = run.__dict__
    agents = runs.list_agents(run_id)
    out["agents"] = [a.__dict__ for a in agents]
    return out


@api_router.get("/runs/{run_id}/agents")
def list_run_agents(request: Request, run_id: str):
    return [a.__dict__ for a in _orch(request).runs.list_agents(run_id)]


@api_router.get("/jobs/{job_id}")
def get_job(request: Request, job_id: str):
    q = _queue(request)
    job = q.get(job_id)
    if job is None:
        raise HTTPException(404, "job not found")
    return job.to_dict()


# --- Routes: wiki ---


@api_router.get("/wiki/pages")
def list_wiki_pages(request: Request):
    svc = _orch(request).wiki
    return [p.to_dict() for p in svc.list_pages()]


@api_router.post("/wiki/pages")
def create_wiki_page(request: Request, body: CreatePageRequest):
    tags = body.tags
    svc = _orch(request).wiki
    page = svc.create_page(
        title=body.title,
        body=body.body,
        tags=tags if tags is not None else [],
        source=body.source,
        run_id=body.run_id,
    )
    return page.to_dict()


@api_router.get("/wiki/pages/{page_id}")
def get_wiki_page(request: Request, page_id: str):
    svc = _orch(request).wiki
    page = svc.get_page(page_id)
    if page is None:
        raise HTTPException(404, "page not found")
    out = page.to_dict()
    out["backlinks"] = [p.to_dict() for p in svc.backlinks(page.title)]
    return out


@api_router.patch("/wiki/pages/{page_id}")
def update_wiki_page(request: Request, page_id: str, body: UpdatePageRequest):
    svc = _orch(request).wiki
    page = svc.update_page(
        page_id,
        title=body.title,
        body=body.body,
        tags=body.tags,
    )
    if page is None:
        raise HTTPException(404, "page not found")
    return page.to_dict()


@api_router.get("/wiki/search")
def wiki_search(request: Request, q: str, limit: int = 50):
    svc = _orch(request).wiki
    return [p.to_dict() for p in svc.search(q, limit=limit)]


# --- Routes: evolution ---


def _fitness_func(kind: str):
    if kind == "length":
        return lambda s: min(1.0, len(s) / 20.0)
    if kind == "diversity":
        return lambda s: min(1.0, len(set(s)) / 10.0)
    if kind == "fixed":
        return lambda s: 0.5
    return lambda s: 0.5


@api_router.post("/evolution/run")
async def evolution_run(request: Request, body: EvolutionRequest):
    bus = _bus(request)
    db = _db(request)
    gen_records = []
    events = []
    bus.subscribe(lambda e: events.append(e))
    fitness = _fitness_func(body.fitness_kind)
    eng = EvolutionEngine(
        pop_size=body.pop_size,
        seed=body.seed,
        fitness=fitness,
        mutation_rate=body.mutation_rate,
        plateau_window=body.plateau_window,
        db=db,
    )
    run_id = f"evo_{body.seed[:8]}"
    gen0 = await eng.initial_generation(run_id=run_id)
    gen_records.append(gen0.to_dict())
    for _ in range(body.generations - 1):
        stats = await eng.step_generation(run_id=run_id)
        gen_records.append(stats.to_dict())
    for _ in range(5):
        await asyncio.sleep(0)
    pop = [c.__dict__ | {"metadata": c.metadata} for c in eng.list_population()]
    return {
        "run_id": run_id,
        "generations": gen_records,
        "population": pop,
        "mutation_rate": eng.mutation_rate,
        "events": events[-50:],
    }


# --- WebSocket: live event stream ---


@ws_router.websocket("/ws")
async def ws_events(ws: WebSocket):
    await ws.accept()
    bus: Any = ws.app.state.bus

    loop = asyncio.get_event_loop()
    queue: asyncio.Queue = asyncio.Queue()

    def push(event):
        loop.call_soon_threadsafe(queue.put_nowait, event)

    sub_id = bus.subscribe(push)
    try:
        # Replay recent history first.
        for evt in bus.history():
            await ws.send_json(evt)
        while True:
            evt = await queue.get()
            await ws.send_json(evt)
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        bus.unsubscribe(sub_id)