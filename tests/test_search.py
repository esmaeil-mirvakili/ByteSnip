"""Tests for snipapp.core.search — FTS, LIKE fallback, filtering, ranking."""

import pytest

from snipapp.core.db import get_session
from snipapp.core.models import Folder, Snippet
from snipapp.core.search import (
    SearchResult,
    _build_fts_query,
    _like_search,
    search_snippets,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ids(results: list[SearchResult]) -> set[int]:
    return {r.snippet.id for r in results}


# ---------------------------------------------------------------------------
# _build_fts_query
# ---------------------------------------------------------------------------

class TestBuildFtsQuery:
    def test_single_token(self):
        assert _build_fts_query("hello") == '"hello"*'

    def test_multiple_tokens(self):
        q = _build_fts_query("foo bar")
        assert '"foo"*' in q
        assert '"bar"*' in q
        assert " OR " in q

    def test_empty_string(self):
        assert _build_fts_query("") == ""

    def test_whitespace_only(self):
        assert _build_fts_query("   ") == ""

    def test_extra_whitespace_between_tokens(self):
        q = _build_fts_query("  a   b  ")
        assert '"a"*' in q
        assert '"b"*' in q


# ---------------------------------------------------------------------------
# search_snippets — empty query returns all snippets
# ---------------------------------------------------------------------------

class TestSearchEmpty:
    def test_returns_all_snippets(self, sample_snippets, db):
        with get_session() as s:
            results = search_snippets(s, "")
        assert len(results) == 3

    def test_returns_search_result_objects(self, sample_snippets, db):
        with get_session() as s:
            results = search_snippets(s, "")
        assert all(isinstance(r, SearchResult) for r in results)
        assert all(isinstance(r.snippet, Snippet) for r in results)

    def test_empty_db_returns_empty(self, db):
        with get_session() as s:
            results = search_snippets(s, "")
        assert results == []


# ---------------------------------------------------------------------------
# search_snippets — title search
# ---------------------------------------------------------------------------

class TestSearchByTitle:
    def test_matches_exact_title_word(self, sample_snippets, db):
        with get_session() as s:
            results = search_snippets(s, "Bubble")
        titles = {r.snippet.title for r in results}
        assert "Bubble sort" in titles

    def test_partial_title_match(self, sample_snippets, db):
        with get_session() as s:
            results = search_snippets(s, "sort")
        assert len(results) >= 1
        assert any("sort" in r.snippet.title.lower() for r in results)

    def test_no_match_returns_empty(self, sample_snippets, db):
        with get_session() as s:
            results = search_snippets(s, "xyzzy_no_match_12345")
        assert results == []


# ---------------------------------------------------------------------------
# search_snippets — body search
# ---------------------------------------------------------------------------

class TestSearchByBody:
    def test_matches_body_content(self, sample_snippets, db):
        with get_session() as s:
            results = search_snippets(s, "fetch")
        bodies = {r.snippet.body for r in results}
        assert any("fetch" in b for b in bodies)

    def test_matches_python_keyword_in_body(self, sample_snippets, db):
        with get_session() as s:
            results = search_snippets(s, "open")
        assert any("open" in r.snippet.body for r in results)


# ---------------------------------------------------------------------------
# search_snippets — description search
# ---------------------------------------------------------------------------

class TestSearchByDescription:
    def test_matches_description(self, sample_snippets, db):
        with get_session() as s:
            results = search_snippets(s, "algorithm")
        descs = {r.snippet.description for r in results}
        assert any("algorithm" in d for d in descs)

    def test_matches_partial_description(self, sample_snippets, db):
        with get_session() as s:
            results = search_snippets(s, "sorting")
        assert len(results) >= 1

    def test_description_only_snippet_found(self, db):
        with get_session() as s:
            sn = Snippet(
                title="Untitled",
                body="x = 1",
                language="python",
                description="unique_desc_xyz",
            )
            s.add(sn)
            s.commit()

        with get_session() as s:
            results = search_snippets(s, "unique_desc_xyz")
        assert len(results) == 1
        assert results[0].snippet.description == "unique_desc_xyz"


# ---------------------------------------------------------------------------
# search_snippets — folder filter
# ---------------------------------------------------------------------------

class TestSearchFolderFilter:
    def test_folder_filter_limits_results(self, sample_snippets, db):
        with get_session() as s:
            folder = s.query(Folder).filter_by(name="Utils").first()
            results = search_snippets(s, "", folder_id=folder.id)
        # Only the 2 snippets inside "Utils" should be returned
        assert len(results) == 2

    def test_folder_filter_excludes_other_folders(self, db):
        with get_session() as s:
            f1 = Folder(name="F1")
            f2 = Folder(name="F2")
            s.add_all([f1, f2])
            s.flush()
            sn1 = Snippet(title="In F1", body="x", language="python", folder_id=f1.id)
            sn2 = Snippet(title="In F2", body="y", language="python", folder_id=f2.id)
            s.add_all([sn1, sn2])
            s.commit()
            f1_id = f1.id
            f2_id = f2.id

        with get_session() as s:
            r1 = search_snippets(s, "", folder_id=f1_id)
            r2 = search_snippets(s, "", folder_id=f2_id)
        assert all(r.snippet.folder_id == f1_id for r in r1)
        assert all(r.snippet.folder_id == f2_id for r in r2)

    def test_none_folder_returns_all(self, sample_snippets, db):
        with get_session() as s:
            results = search_snippets(s, "", folder_id=None)
        assert len(results) == 3


# ---------------------------------------------------------------------------
# search_snippets — limit
# ---------------------------------------------------------------------------

class TestSearchLimit:
    def test_limit_respected(self, db):
        with get_session() as s:
            for i in range(10):
                s.add(Snippet(title=f"Snippet {i}", body=f"x{i}", language="python"))
            s.commit()

        with get_session() as s:
            results = search_snippets(s, "", limit=3)
        assert len(results) <= 3

    def test_default_limit_not_exceeded(self, db):
        with get_session() as s:
            for i in range(150):
                s.add(Snippet(title=f"S{i}", body=f"x", language="python"))
            s.commit()

        with get_session() as s:
            results = search_snippets(s, "")
        assert len(results) <= 100


# ---------------------------------------------------------------------------
# _like_search (fallback)
# ---------------------------------------------------------------------------

class TestLikeSearch:
    def test_matches_title(self, db):
        with get_session() as s:
            s.add(Snippet(title="like title test", body="x", language="python"))
            s.commit()

        with get_session() as s:
            results = _like_search(s, "like title", None, None, 100)
        assert any("like title" in r.snippet.title for r in results)

    def test_matches_body(self, db):
        with get_session() as s:
            s.add(Snippet(title="t", body="unique_body_token", language="python"))
            s.commit()

        with get_session() as s:
            results = _like_search(s, "unique_body_token", None, None, 100)
        assert len(results) == 1

    def test_matches_description(self, db):
        with get_session() as s:
            s.add(Snippet(
                title="t", body="x", language="python",
                description="like_desc_token"
            ))
            s.commit()

        with get_session() as s:
            results = _like_search(s, "like_desc_token", None, None, 100)
        assert len(results) == 1

    def test_case_insensitive(self, db):
        with get_session() as s:
            s.add(Snippet(title="CamelCase Title", body="x", language="python"))
            s.commit()

        with get_session() as s:
            results = _like_search(s, "camelcase", None, None, 100)
        assert len(results) == 1

    def test_no_match_returns_empty(self, db):
        with get_session() as s:
            s.add(Snippet(title="t", body="x", language="python"))
            s.commit()

        with get_session() as s:
            results = _like_search(s, "zzznomatch", None, None, 100)
        assert results == []
