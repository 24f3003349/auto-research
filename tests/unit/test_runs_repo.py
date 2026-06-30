"""Tests for run + agent repository."""
import json
import pytest

from app.storage.db import Database
from app.backend.services.runs import RunRepo, AgentRecord, RunRecord


@pytest.fixture
def db(tmp_path):
    return Database(tmp_path / "test.db")


@pytest.fixture
def repo(db):
    return RunRepo(db)


def test_create_run_returns_record(repo):
    run = repo.create_run(topic="plateau detection", objective="max diversity")
    assert isinstance(run, RunRecord)
    assert run.id
    assert run.topic == "plateau detection"
    assert run.objective == "max diversity"
    assert run.status == "queued"


def test_list_runs_orders_newest_first(repo):
    a = repo.create_run(topic="a")
    b = repo.create_run(topic="b")
    runs = repo.list_runs()
    assert runs[0].id == b.id
    assert runs[1].id == a.id


def test_get_run_returns_none_when_missing(repo):
    assert repo.get_run("nope") is None


def test_update_run_status(repo):
    run = repo.create_run(topic="x")
    repo.update_status(run.id, "running")
    assert repo.get_run(run.id).status == "running"


def test_record_agent_persists_input_and_output(repo):
    run = repo.create_run(topic="x")
    agent = repo.record_agent(
        run_id=run.id, role="planner", input="plan it", output="step 1, step 2"
    )
    assert agent.id
    assert agent.role == "planner"
    fetched = repo.get_agent(agent.id)
    assert fetched.input == "plan it"
    assert fetched.output == "step 1, step 2"
    assert fetched.state == "completed"


def test_list_agents_for_run_returns_in_creation_order(repo):
    run = repo.create_run(topic="x")
    a = repo.record_agent(run_id=run.id, role="planner", input="i", output="o")
    b = repo.record_agent(run_id=run.id, role="researcher", input="i", output="o")
    agents = repo.list_agents(run.id)
    assert [x.id for x in agents] == [a.id, b.id]


def test_record_metric_stores_value(repo):
    run = repo.create_run(topic="x")
    repo.record_metric(run_id=run.id, name="fitness", value=0.87)
    rows = repo.db.fetchall(
        "SELECT name, value FROM metrics WHERE run_id = ?", (run.id,)
    )
    assert rows == [("fitness", 0.87)]


def test_run_record_serializes_config(repo):
    run = repo.create_run(topic="x", config={"generations": 10, "pop_size": 20})
    again = repo.get_run(run.id)
    assert again.config == {"generations": 10, "pop_size": 20}