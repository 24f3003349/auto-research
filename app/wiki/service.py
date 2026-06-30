"""LLM Wiki: editable pages with tags, backlinks, and FTS5 search."""
from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from typing import Iterable

from app.storage.db import Database


BACKLINK_RE = re.compile(r"\[\[([^\]\n]+)\]\]")


@dataclass
class WikiPage:
    id: str
    title: str
    body: str
    tags: list[str]
    source: str | None
    run_id: str | None
    created_at: str
    updated_at: str

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "body": self.body,
            "tags": self.tags,
            "source": self.source,
            "run_id": self.run_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


def _split_tags(tags: Iterable[str]) -> str:
    return ",".join(t.strip() for t in tags if t.strip())


def _parse_tags(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [t.strip() for t in raw.split(",") if t.strip()]


def _row_to_page(row: tuple) -> WikiPage:
    return WikiPage(
        id=row[0],
        title=row[1],
        body=row[2],
        tags=_parse_tags(row[3]),
        source=row[4],
        run_id=row[5],
        created_at=row[6],
        updated_at=row[7],
    )


SELECT_PAGE = (
    "SELECT id, title, body, tags, source, run_id, created_at, updated_at "
    "FROM wiki_pages"
)


class WikiService:
    def __init__(self, db: Database):
        self.db = db

    def create_page(
        self,
        title: str,
        body: str,
        tags: Iterable[str] | str = (),
        source: str | None = None,
        run_id: str | None = None,
    ) -> WikiPage:
        if isinstance(tags, str):
            tags_str = tags
        else:
            tags_str = _split_tags(tags)
        page_id = f"page_{uuid.uuid4().hex[:10]}"
        self.db.execute(
            "INSERT INTO wiki_pages (id, title, body, tags, source, run_id) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (page_id, title, body, tags_str or None, source, run_id),
        )
        page = self.get_page(page_id)
        assert page is not None
        return page

    def get_page(self, page_id: str) -> WikiPage | None:
        row = self.db.fetchone(f"{SELECT_PAGE} WHERE id = ?", (page_id,))
        return _row_to_page(row) if row else None

    def get_page_by_title(self, title: str) -> WikiPage | None:
        row = self.db.fetchone(
            f"{SELECT_PAGE} WHERE title = ? ORDER BY updated_at DESC LIMIT 1",
            (title,),
        )
        return _row_to_page(row) if row else None

    def update_page(
        self,
        page_id: str,
        *,
        title: str | None = None,
        body: str | None = None,
        tags: Iterable[str] | str | None = None,
    ) -> WikiPage | None:
        existing = self.get_page(page_id)
        if existing is None:
            return None
        new_title = title if title is not None else existing.title
        new_body = body if body is not None else existing.body
        if isinstance(tags, str):
            new_tags = tags
        elif tags is None:
            new_tags = ",".join(existing.tags)
        else:
            new_tags = _split_tags(tags)
        self.db.execute(
            "UPDATE wiki_pages SET title = ?, body = ?, tags = ?, "
            "updated_at = strftime('%Y-%m-%d %H:%M:%f', 'now') WHERE id = ?",
            (new_title, new_body, new_tags or None, page_id),
        )
        return self.get_page(page_id)

    def list_pages(self, limit: int = 200) -> list[WikiPage]:
        rows = self.db.fetchall(
            f"{SELECT_PAGE} ORDER BY updated_at DESC LIMIT ?", (limit,)
        )
        return [_row_to_page(r) for r in rows]

    def search(self, query: str, limit: int = 50) -> list[WikiPage]:
        try:
            rows = self.db.fetchall(
                "SELECT p.id, p.title, p.body, p.tags, p.source, p.run_id, "
                "p.created_at, p.updated_at "
                "FROM wiki_fts f JOIN wiki_pages p ON p.rowid = f.rowid "
                "WHERE wiki_fts MATCH ? ORDER BY rank LIMIT ?",
                (query, limit),
            )
        except Exception:
            rows = self.db.fetchall(
                "SELECT id, title, body, tags, source, run_id, created_at, updated_at "
                "FROM wiki_pages WHERE title LIKE ? OR body LIKE ? OR tags LIKE ? "
                "ORDER BY updated_at DESC LIMIT ?",
                (f"%{query}%", f"%{query}%", f"%{query}%", limit),
            )
        return [_row_to_page(r) for r in rows]

    def backlinks(self, title: str) -> list[WikiPage]:
        rows = self.db.fetchall(
            f"{SELECT_PAGE} WHERE body LIKE ?", (f"%[[{title}]]%",)
        )
        return [_row_to_page(r) for r in rows]

    def extract_links(self, body: str) -> list[str]:
        return [m.group(1).strip() for m in BACKLINK_RE.finditer(body)]


def pages_from_run(
    svc: WikiService,
    run_id: str,
    topic: str,
    steps: list[str],
    finding: str,
    critique: str,
    score: float,
) -> list[WikiPage]:
    """Auto-create canonical wiki pages from a finished run."""
    pages: list[WikiPage] = []
    plan_body = "## Steps\n" + "\n".join(f"- {s}" for s in steps) if steps else ""
    pages.append(
        svc.create_page(
            title=f"Plan/{topic}",
            body=plan_body,
            tags=["plan", topic],
            source="auto",
            run_id=run_id,
        )
    )
    pages.append(
        svc.create_page(
            title=f"Finding/{topic}",
            body=finding,
            tags=["finding", topic],
            source="auto",
            run_id=run_id,
        )
    )
    pages.append(
        svc.create_page(
            title=f"Critique/{topic}",
            body=critique,
            tags=["critique", topic],
            source="auto",
            run_id=run_id,
        )
    )
    summary = (
        f"# {topic}\n\nScore: {score:.2f}\n\n"
        f"## Plan\n{plan_body}\n\n## Finding\n{finding}\n\n## Critique\n{critique}"
    )
    pages.append(
        svc.create_page(
            title=f"Run/{topic}",
            body=summary,
            tags=["run", topic],
            source="auto",
            run_id=run_id,
        )
    )
    return pages