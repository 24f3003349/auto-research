"""Integration tests for the FastAPI app surface."""
import pytest
from fastapi.testclient import TestClient

from app.backend.api.deps import build_app_for_tests
from app.storage.db import Database


@pytest.fixture
def client(tmp_path):
    db_path = tmp_path / "cockpit.db"
    app = build_app_for_tests(db=str(db_path))
    return TestClient(app)


def test_health_endpoint(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"


def test_list_runs_is_empty_initially(client):
    r = client.get("/api/runs")
    assert r.status_code == 200
    assert r.json() == []


def test_create_and_get_run(client):
    r = client.post("/api/runs", json={"topic": "plateau", "objective": "max diversity"})
    assert r.status_code == 200
    body = r.json()
    assert body["id"].startswith("run_")
    rid = body["id"]
    # Fetch it back
    r = client.get(f"/api/runs/{rid}")
    assert r.status_code == 200
    assert r.json()["topic"] == "plateau"


def test_run_endpoint_executes_pipeline_and_updates_status(client):
    r = client.post(
        "/api/runs",
        json={"topic": "x", "objective": "y"},
    )
    rid = r.json()["id"]
    # Wait briefly for background execution.
    import time
    for _ in range(60):
        rr = client.get(f"/api/runs/{rid}")
        if rr.json()["status"] in ("completed", "failed"):
            break
        time.sleep(0.05)
    assert rr.json()["status"] == "completed"


def test_wiki_pages_created_from_a_run(client):
    client.post("/api/runs", json={"topic": "wiki-test", "objective": "y"})
    import time
    for _ in range(60):
        if client.get("/api/wiki/pages").json():
            break
        time.sleep(0.05)
    r = client.get("/api/wiki/pages")
    titles = [p["title"] for p in r.json()]
    assert any("Run/wiki-test" in t for t in titles)


def test_wiki_search(client):
    # Create a unique page that mentions a unique word, then search.
    r = client.post(
        "/api/wiki/pages",
        json={"title": "Galaxy", "body": "zorgon makes it unique", "tags": "test"},
    )
    assert r.status_code == 200
    r = client.get("/api/wiki/search", params={"q": "zorgon"})
    assert r.status_code == 200
    titles = [p["title"] for p in r.json()]
    assert "Galaxy" in titles


def test_evolution_run_creates_generations(client):
    r = client.post(
        "/api/evolution/run",
        json={"seed": "abc", "generations": 3, "pop_size": 4, "fitness_kind": "length"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["generations"][0]["generation"] == 0
    gens = body["generations"]
    assert len(gens) == 3
    # The 'length' fitness function is unbounded so we clamp; just sanity-check.
    assert all(0.0 <= g["best_fitness"] <= 1000.0 for g in gens)


def test_websocket_receives_run_events(client):
    with client.websocket_connect("/ws") as ws:
        # Trigger a run while the socket is connected.
        r = client.post("/api/runs", json={"topic": "ws-topic", "objective": "y"})
        rid = r.json()["id"]
        # Drain events until we see run.completed or timeout.
        saw_completed = False
        import time
        deadline = time.time() + 5.0
        while time.time() < deadline:
            try:
                evt = ws.receive_json()
            except Exception:
                break
            if evt.get("type") == "run.completed" and evt.get("run_id") == rid:
                saw_completed = True
                break
        assert saw_completed