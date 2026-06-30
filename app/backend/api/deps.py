"""Application factory used by both production and tests.

Production: `build_app()` — opens (or creates) the default cockpit.db and
serves the built React bundle from `frontend/dist` if present.

Tests: `build_app_for_tests(db=...)` — injects an isolated SQLite path.
"""
from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI

from app.agents.llm import EchoProvider, get_provider
from app.backend.api.routes import api_router, ws_router
from app.backend.services.event_bus import EventBus
from app.backend.services.orchestrator import Orchestrator
from app.backend.services.queue import JobQueue
from app.storage.db import Database


DEFAULT_DB_PATH = Path(os.environ.get("COCKPIT_DB", "cockpit.db")).resolve()


def build_app(
    db: Database | None = None,
    db_path: str | Path | None = None,
    provider=None,
) -> FastAPI:
    return _build(db=db, db_path=db_path, provider=provider, static=True)


def build_app_for_tests(db: str | Path) -> FastAPI:
    return _build(db=None, db_path=db, provider=EchoProvider(), static=False)


def _build(
    *,
    db: Database | None,
    db_path: str | Path | None,
    provider,
    static: bool,
) -> FastAPI:
    app = FastAPI(title="Auto-Research Cockpit")
    target = db or Database(db_path or DEFAULT_DB_PATH)
    bus = EventBus()
    q = JobQueue(workers=2)
    provider = provider or get_provider()
    orch = Orchestrator(db=target, provider=provider, bus=bus)
    q.start()

    app.state.db = target
    app.state.bus = bus
    app.state.queue = q
    app.state.orchestrator = orch
    app.state.provider = provider

    app.include_router(api_router, prefix="/api")
    app.include_router(ws_router)

    @app.get("/api/health")
    def health():
        return {"status": "ok", "provider": provider.__class__.__name__}

    if static:
        from fastapi.staticfiles import StaticFiles

        # app/backend/api/deps.py -> parents[3] is project root
        project_root = Path(__file__).resolve().parents[3]
        dist = project_root / "frontend" / "dist"
        if dist.exists():
            app.mount("/", StaticFiles(directory=str(dist), html=True), name="ui")
    return app


def create_default_app() -> FastAPI:
    return build_app()
