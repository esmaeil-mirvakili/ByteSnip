"""Tests for snipapp.core.db — engine init, sessions, migrations, FTS."""

import pytest
from sqlalchemy import inspect, text

from snipapp.core.db import init_engine, get_session, _get_migrations
from snipapp.core.models import Snippet


# ---------------------------------------------------------------------------
# Engine initialisation
# ---------------------------------------------------------------------------

class TestInitEngine:
    def test_returns_engine(self, db):
        from sqlalchemy import Engine
        assert isinstance(db, Engine)

    def test_creates_snippets_table(self, db):
        inspector = inspect(db)
        assert "snippets" in inspector.get_table_names()

    def test_creates_folders_table(self, db):
        inspector = inspect(db)
        assert "folders" in inspector.get_table_names()

    def test_creates_tags_table(self, db):
        inspector = inspect(db)
        assert "tags" in inspector.get_table_names()

    def test_creates_snippet_tags_table(self, db):
        inspector = inspect(db)
        assert "snippet_tags" in inspector.get_table_names()

    def test_creates_schema_version_table(self, db):
        inspector = inspect(db)
        assert "schema_version" in inspector.get_table_names()

    def test_wal_mode_enabled(self, db):
        with db.connect() as conn:
            mode = conn.execute(text("PRAGMA journal_mode")).scalar()
        assert mode == "wal"

    def test_foreign_keys_enabled(self, db):
        with db.connect() as conn:
            fk = conn.execute(text("PRAGMA foreign_keys")).scalar()
        assert fk == 1

    def test_reinit_same_path_is_idempotent(self, tmp_path):
        path = tmp_path / "idem.db"
        e1 = init_engine(path)
        e2 = init_engine(path)
        # Second call succeeds and tables still exist
        inspector = inspect(e2)
        assert "snippets" in inspector.get_table_names()
        e1.dispose()
        e2.dispose()


# ---------------------------------------------------------------------------
# Migrations
# ---------------------------------------------------------------------------

class TestMigrations:
    def test_all_migrations_applied(self, db):
        with db.connect() as conn:
            version = conn.execute(text("SELECT MAX(version) FROM schema_version")).scalar()
        expected = max(v for v, _ in _get_migrations())
        assert version == expected

    def test_fts_table_created(self, db):
        with db.connect() as conn:
            # FTS virtual tables show up in sqlite_master
            row = conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table' AND name='snippets_fts'")
            ).fetchone()
        assert row is not None

    def test_fts_includes_description_column(self, db):
        with db.connect() as conn:
            conn.execute(
                text(
                    "INSERT INTO snippets (title, body, language, description, use_count)"
                    " VALUES ('t','x','python','uniquedesctoken',0)"
                )
            )
            conn.commit()
            # Query via rowid — content FTS tables can't SELECT individual columns directly
            row = conn.execute(
                text("SELECT rowid FROM snippets_fts WHERE snippets_fts MATCH 'uniquedesctoken'")
            ).fetchone()
        assert row is not None

    def test_fts_insert_trigger(self, db):
        with get_session() as s:
            sn = Snippet(title="trigger test", body="body text", language="python", description="")
            s.add(sn)
            s.commit()
            snippet_id = sn.id

        with db.connect() as conn:
            row = conn.execute(
                text("SELECT rowid FROM snippets_fts WHERE snippets_fts MATCH '\"trigger\"*'")
            ).fetchone()
        assert row is not None
        assert row[0] == snippet_id

    def test_fts_delete_trigger(self, db):
        with get_session() as s:
            sn = Snippet(title="delete me", body="gone", language="python")
            s.add(sn)
            s.commit()
            sn_id = sn.id

        with get_session() as s:
            sn = s.get(Snippet, sn_id)
            s.delete(sn)
            s.commit()

        with db.connect() as conn:
            row = conn.execute(
                text("SELECT rowid FROM snippets_fts WHERE snippets_fts MATCH '\"delete\"*'")
            ).fetchone()
        assert row is None

    def test_fts_update_trigger(self, db):
        with get_session() as s:
            sn = Snippet(title="original title", body="x", language="python")
            s.add(sn)
            s.commit()
            sn_id = sn.id

        with get_session() as s:
            sn = s.get(Snippet, sn_id)
            sn.title = "updated title"
            s.commit()

        with db.connect() as conn:
            new_row = conn.execute(
                text("SELECT rowid FROM snippets_fts WHERE snippets_fts MATCH '\"updated\"*'")
            ).fetchone()
            old_row = conn.execute(
                text("SELECT rowid FROM snippets_fts WHERE snippets_fts MATCH '\"original\"*'")
            ).fetchone()
        assert new_row is not None
        assert old_row is None


# ---------------------------------------------------------------------------
# Session management
# ---------------------------------------------------------------------------

class TestGetSession:
    def test_raises_without_init(self, tmp_path):
        # Force uninitialized state by patching the global
        import snipapp.core.db as db_mod
        original = db_mod._SessionLocal
        db_mod._SessionLocal = None
        try:
            with pytest.raises(RuntimeError, match="not initialised"):
                get_session()
        finally:
            db_mod._SessionLocal = original

    def test_context_manager_closes_session(self, db):
        with get_session() as s:
            assert s.is_active
        # SQLAlchemy 2.x close() ends the transaction; in_transaction() is False
        assert not s.in_transaction()

    def test_multiple_independent_sessions(self, db):
        with get_session() as s1:
            sn = Snippet(title="s1 snippet", body="x", language="python")
            s1.add(sn)
            s1.commit()
            sn_id = sn.id

        with get_session() as s2:
            fetched = s2.get(Snippet, sn_id)
            assert fetched is not None
            assert fetched.title == "s1 snippet"
