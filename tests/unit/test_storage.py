"""Tests for storage layer."""
import pytest

from app.storage.db import Database


def test_database_creates_tables(tmp_path):
    db = Database(tmp_path / "test.db")
    tables = db.list_tables()
    assert "runs" in tables
    assert "wiki_pages" in tables
    assert "agents" in tables
    assert "evolution_population" in tables
    assert "wiki_fts" in tables


def test_database_persists_across_instances(tmp_path):
    path = tmp_path / "test.db"
    db1 = Database(path)
    db1.execute("INSERT INTO runs (id, topic, status) VALUES (?, ?, ?)", ("r1", "test", "queued"))

    db2 = Database(path)
    row = db2.fetchone("SELECT topic, status FROM runs WHERE id = ?", ("r1",))
    assert row == ("test", "queued")


def test_database_execute_script_runs_multi_statement(tmp_path):
    db = Database(tmp_path / "test.db")
    db.executescript(
        "CREATE TABLE t (x INTEGER); INSERT INTO t VALUES (1); INSERT INTO t VALUES (2);"
    )
    rows = db.fetchall("SELECT x FROM t ORDER BY x")
    assert rows == [(1,), (2,)]