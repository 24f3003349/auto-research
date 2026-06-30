"""SQLite database wrapper with FTS5 search support."""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Iterable


SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id            TEXT PRIMARY KEY,
    topic         TEXT NOT NULL,
    objective     TEXT,
    constraints   TEXT,
    status        TEXT NOT NULL DEFAULT 'queued',
    created_at    TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at    TEXT NOT NULL DEFAULT (datetime('now')),
    config        TEXT
);

CREATE TABLE IF NOT EXISTS agents (
    id            TEXT PRIMARY KEY,
    run_id        TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    role          TEXT NOT NULL,
    state         TEXT NOT NULL DEFAULT 'idle',
    input         TEXT,
    output        TEXT,
    error         TEXT,
    created_at    TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS metrics (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id        TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    agent_id      TEXT,
    name          TEXT NOT NULL,
    value         REAL NOT NULL,
    recorded_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS wiki_pages (
    id            TEXT PRIMARY KEY,
    title         TEXT NOT NULL,
    body          TEXT NOT NULL,
    tags          TEXT,
    source        TEXT,
    run_id        TEXT REFERENCES runs(id) ON DELETE SET NULL,
    created_at    TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE VIRTUAL TABLE IF NOT EXISTS wiki_fts USING fts5(
    title, body, tags, content='wiki_pages', content_rowid='rowid'
);

CREATE TABLE IF NOT EXISTS evolution_population (
    id            TEXT PRIMARY KEY,
    candidate     TEXT NOT NULL,
    fitness       REAL NOT NULL DEFAULT 0.0,
    generation    INTEGER NOT NULL,
    parent_id     TEXT,
    metadata      TEXT,
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS evolution_generations (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id        TEXT NOT NULL,
    generation    INTEGER NOT NULL,
    best_fitness  REAL NOT NULL,
    mean_fitness  REAL NOT NULL,
    diversity     REAL NOT NULL,
    plateau       INTEGER NOT NULL DEFAULT 0,
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


class Database:
    """Thin SQLite wrapper. One file, persistent, FTS5-enabled."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, isolation_level=None, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(SCHEMA)

    def execute(self, sql: str, params: Iterable[Any] = ()) -> None:
        with self._connect() as conn:
            conn.execute(sql, tuple(params))

    def executemany(self, sql: str, seq: Iterable[Iterable[Any]]) -> None:
        with self._connect() as conn:
            conn.executemany(sql, [tuple(p) for p in seq])

    def executescript(self, sql: str) -> None:
        with self._connect() as conn:
            conn.executescript(sql)

    def fetchone(self, sql: str, params: Iterable[Any] = ()) -> tuple | None:
        with self._connect() as conn:
            row = conn.execute(sql, tuple(params)).fetchone()
            return tuple(row) if row else None

    def fetchall(self, sql: str, params: Iterable[Any] = ()) -> list[tuple]:
        with self._connect() as conn:
            return [tuple(r) for r in conn.execute(sql, tuple(params)).fetchall()]

    def list_tables(self) -> list[str]:
        rows = self.fetchall(
            "SELECT name FROM sqlite_master WHERE type IN ('table','view') ORDER BY name"
        )
        return [r[0] for r in rows]