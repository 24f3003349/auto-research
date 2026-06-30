"""Repository for research runs and their agents."""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from typing import Any

from app.storage.db import Database


@dataclass
class RunRecord:
    id: str
    topic: str
    objective: str | None
    constraints: str | None
    status: str
    created_at: str
    updated_at: str
    config: dict | None


@dataclass
class AgentRecord:
    id: str
    run_id: str
    role: str
    state: str
    input: str | None
    output: str | None
    error: str | None
    created_at: str
    updated_at: str


def _row_to_run(row: tuple) -> RunRecord:
    config = row[7]
    return RunRecord(
        id=row[0],
        topic=row[1],
        objective=row[2],
        constraints=row[3],
        status=row[4],
        created_at=row[5],
        updated_at=row[6],
        config=json.loads(config) if config else None,
    )


def _row_to_agent(row: tuple) -> AgentRecord:
    return AgentRecord(
        id=row[0],
        run_id=row[1],
        role=row[2],
        state=row[3],
        input=row[4],
        output=row[5],
        error=row[6],
        created_at=row[7],
        updated_at=row[8],
    )


class RunRepo:
    def __init__(self, db: Database):
        self.db = db

    def create_run(
        self,
        topic: str,
        objective: str | None = None,
        constraints: str | None = None,
        config: dict | None = None,
    ) -> RunRecord:
        rid = f"run_{uuid.uuid4().hex[:12]}"
        self.db.execute(
            "INSERT INTO runs (id, topic, objective, constraints, status, config) "
            "VALUES (?, ?, ?, ?, 'queued', ?)",
            (rid, topic, objective, constraints, json.dumps(config) if config else None),
        )
        run = self.get_run(rid)
        assert run is not None
        return run

    def get_run(self, run_id: str) -> RunRecord | None:
        row = self.db.fetchone(
            "SELECT id, topic, objective, constraints, status, created_at, updated_at, config "
            "FROM runs WHERE id = ?",
            (run_id,),
        )
        return _row_to_run(row) if row else None

    def list_runs(self) -> list[RunRecord]:
        rows = self.db.fetchall(
            "SELECT id, topic, objective, constraints, status, created_at, updated_at, config "
            "FROM runs ORDER BY created_at DESC"
        )
        return [_row_to_run(r) for r in rows]

    def update_status(self, run_id: str, status: str) -> None:
        self.db.execute(
            "UPDATE runs SET status = ?, updated_at = strftime('%Y-%m-%d %H:%M:%f', 'now') "
            "WHERE id = ?",
            (status, run_id),
        )

    def record_agent(
        self,
        run_id: str,
        role: str,
        input: str | None = None,
        output: str | None = None,
        error: str | None = None,
        state: str = "completed",
    ) -> AgentRecord:
        aid = f"agent_{uuid.uuid4().hex[:12]}"
        self.db.execute(
            "INSERT INTO agents (id, run_id, role, state, input, output, error) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (aid, run_id, role, state, input, output, error),
        )
        agent = self.get_agent(aid)
        assert agent is not None
        return agent

    def get_agent(self, agent_id: str) -> AgentRecord | None:
        row = self.db.fetchone(
            "SELECT id, run_id, role, state, input, output, error, created_at, updated_at "
            "FROM agents WHERE id = ?",
            (agent_id,),
        )
        return _row_to_agent(row) if row else None

    def list_agents(self, run_id: str) -> list[AgentRecord]:
        rows = self.db.fetchall(
            "SELECT id, run_id, role, state, input, output, error, created_at, updated_at "
            "FROM agents WHERE run_id = ? ORDER BY created_at ASC",
            (run_id,),
        )
        return [_row_to_agent(r) for r in rows]

    def record_metric(
        self, run_id: str, name: str, value: float, agent_id: str | None = None
    ) -> None:
        self.db.execute(
            "INSERT INTO metrics (run_id, agent_id, name, value) VALUES (?, ?, ?, ?)",
            (run_id, agent_id, name, value),
        )