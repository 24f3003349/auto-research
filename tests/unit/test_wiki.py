"""Tests for the wiki service."""
import pytest

from app.storage.db import Database
from app.wiki.service import WikiService, WikiPage


@pytest.fixture
def svc(tmp_path):
    return WikiService(Database(tmp_path / "test.db"))


def test_create_page_persists_body_and_tags(svc):
    page = svc.create_page(title="Plateau Detection", body="notes here", tags="evolution,notes")
    assert page.id
    assert page.title == "Plateau Detection"
    assert "evolution" in page.tags
    fetched = svc.get_page(page.id)
    assert fetched.body == "notes here"


def test_search_returns_matching_pages_via_fts5(svc):
    a = svc.create_page(title="Evolution", body="plateau detection strategies")
    b = svc.create_page(title="Prompts", body="how to write better prompts")
    hits = svc.search("plateau")
    ids = {p.id for p in hits}
    assert a.id in ids
    assert b.id not in ids


def test_search_is_case_insensitive(svc):
    svc.create_page(title="Alpha", body="Beta content")
    hits = svc.search("beta")
    assert len(hits) >= 1


def test_backlinks_returns_pages_that_mention_title(svc):
    svc.create_page(title="Fitness", body="primary metric")
    svc.create_page(title="Selection", body="see [[Fitness]] for details")
    svc.create_page(title="Mutation", body="no link here")
    backlinks = svc.backlinks("Fitness")
    titles = {p.title for p in backlinks}
    assert titles == {"Selection"}


def test_pages_indexed_for_fts_on_update(svc):
    p = svc.create_page(title="Beta", body="nothing relevant")
    svc.update_page(p.id, title="Beta", body="now talks about plateau breaking")
    hits = svc.search("plateau breaking")
    assert any(x.id == p.id for x in hits)


def test_list_pages_orders_by_updated_desc(svc):
    a = svc.create_page(title="A", body="x")
    b = svc.create_page(title="B", body="y")
    pages = svc.list_pages()
    assert pages[0].id == b.id
    assert pages[1].id == a.id


def test_create_page_links_to_run(svc):
    from app.backend.services.runs import RunRepo

    repo = RunRepo(svc.db)
    run = repo.create_run(topic="topic for wiki")
    p = svc.create_page(title="x", body="y", source="auto", run_id=run.id)
    assert p.run_id == run.id