# Auto-Research Cockpit

Desktop research cockpit. Stripped-down, single-process MVP covering
the three panes the spec calls for: **Research Runs**, **LLM Wiki**, **Evolution Lab**.

## Stack

- **Backend**: Python 3.12 + FastAPI + SQLite (FTS5) + asyncio
- **Frontend**: React 18 + Vite + TypeScript + Tailwind + Recharts
- **Tests**: pytest (62 tests, TDD throughout)

No Redis, no Celery, no LangGraph, no Docker, no Tauri/Electron — open
`http://localhost:8000` in any browser and you have the desktop app.

## Layout

```
app/
  backend/
    __main__.py        # entrypoint: python -m app.backend
    api/               # FastAPI routes + WebSocket
    services/          # event_bus, queue, orchestrator, runs
  agents/              # LLM provider + 5-role harness
  research/            # orchestrator engine
  wiki/                # pages + FTS5 search + backlinks
  evolution/           # engine, plateau detector, mutate/crossover
  storage/             # SQLite wrapper
  prompts/             # role prompts (plain text, editable)
frontend/              # React UI
tests/
  unit/                # component-level TDD tests
  integration/         # FastAPI tests with TestClient
```

## Run it

```bash
uv sync
cd frontend && npm install && npm run build && cd ..
uv run python -m app.backend
```

Then open http://127.0.0.1:8000.

To use real OpenAI, set `OPENAI_API_KEY` before launching.

## Tests

```bash
uv run pytest          # 61 tests
```

## Coverage of the brief

| Brief ask                               | Where it lives                                            |
|-----------------------------------------|-----------------------------------------------------------|
| Research Runs (topic / objective / Run) | `app/research/engine.py` + `app/backend/api/routes.py`    |
| Auto wiki from completed runs           | `app/wiki/service.py::pages_from_run`                     |
| 5 agent roles + orchestrator            | `app/agents/harness.py` + `app/research/engine.py`        |
| Evolution lab (population + fitness)   | `app/evolution/engine.py`                                 |
| Plateau detection + adaptive mutation   | `app/evolution/engine.py::PlateauDetector`                |
| Live updates                            | `EventBus` + `JobQueue` + `/ws` WebSocket                 |
| Background jobs                         | `app/backend/services/queue.py`                           |
| Pluggable LLM provider                  | `app/agents/llm.py` (Echo + OpenAI; LiteLLM later)        |
