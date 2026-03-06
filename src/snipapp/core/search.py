"""Snippet search: SQLite FTS5 full-text search with fuzzy fallback."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.orm import Session

from snipapp.core.models import Snippet, Tag


@dataclass
class SearchResult:
    snippet: Snippet
    score: float


def search_snippets(
    session: Session,
    query: str,
    folder_id: int | None = None,
    tag_name: str | None = None,
    limit: int = 100,
) -> list[SearchResult]:
    """Return snippets matching *query*, ranked by relevance.

    Uses FTS5 when *query* is non-empty, otherwise returns most-recently-used
    snippets. Falls back to a LIKE scan if FTS fails.
    """
    if not query.strip():
        return _recent_snippets(session, folder_id, tag_name, limit)

    try:
        return _fts_search(session, query, folder_id, tag_name, limit)
    except Exception:
        return _like_search(session, query, folder_id, tag_name, limit)


def _fts_search(
    session: Session, query: str, folder_id: int | None, tag_name: str | None, limit: int
) -> list[SearchResult]:
    fts_query = _build_fts_query(query)
    sql = text(
        """
        SELECT s.id, bm25(snippets_fts) AS score
        FROM snippets_fts
        JOIN snippets s ON snippets_fts.rowid = s.id
        WHERE snippets_fts MATCH :q
          AND (:folder_id IS NULL OR s.folder_id = :folder_id)
        ORDER BY score
        LIMIT :limit
        """
    )
    rows = session.execute(sql, {"q": fts_query, "folder_id": folder_id, "limit": limit}).fetchall()
    results = []
    for row in rows:
        snippet = session.get(Snippet, row.id)
        if snippet:
            results.append(SearchResult(snippet=snippet, score=float(row.score)))
    if tag_name:
        results = [r for r in results if any(t.name == tag_name for t in r.snippet.tags)]
    return results


def _like_search(
    session: Session, query: str, folder_id: int | None, tag_name: str | None, limit: int
) -> list[SearchResult]:
    pattern = f"%{query}%"
    q = session.query(Snippet).filter(
        Snippet.title.ilike(pattern)
        | Snippet.body.ilike(pattern)
        | Snippet.description.ilike(pattern)
    )
    if folder_id is not None:
        q = q.filter(Snippet.folder_id == folder_id)
    if tag_name:
        q = q.filter(Snippet.tags.any(Tag.name == tag_name))
    snippets = q.limit(limit).all()
    return [SearchResult(snippet=s, score=0.0) for s in snippets]


def _recent_snippets(
    session: Session, folder_id: int | None, tag_name: str | None, limit: int
) -> list[SearchResult]:
    q = session.query(Snippet)
    if folder_id is not None:
        q = q.filter(Snippet.folder_id == folder_id)
    if tag_name:
        q = q.filter(Snippet.tags.any(Tag.name == tag_name))
    snippets = q.order_by(Snippet.last_used_at.desc().nullslast(), Snippet.updated_at.desc()).limit(limit).all()
    return [SearchResult(snippet=s, score=0.0) for s in snippets]


def _build_fts_query(raw: str) -> str:
    """Convert a user query into an FTS5 match expression."""
    tokens = raw.strip().split()
    return " OR ".join(f'"{t}"*' for t in tokens if t)
