"""SQLite database connection, session factory, and schema migrations."""

from __future__ import annotations

import logging
from pathlib import Path

from sqlalchemy import Engine, create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker

from snipapp.core.models import Base

logger = logging.getLogger(__name__)

_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None


def get_db_path() -> Path:
    """Return platform-appropriate path for the SQLite database file."""
    import platform
    import os

    if platform.system() == "Darwin":
        base = Path.home() / "Library" / "Application Support" / "ByteSnip"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "bytesnip"

    base.mkdir(parents=True, exist_ok=True)
    return base / "snippets.db"


def init_engine(db_path: Path | None = None) -> Engine:
    """Create and configure the SQLAlchemy engine (call once at startup)."""
    global _engine, _SessionLocal

    path = db_path or get_db_path()
    url = f"sqlite:///{path}"
    logger.debug("Opening database at %s", path)

    engine = create_engine(url, connect_args={"check_same_thread": False})

    # Enable WAL mode and foreign keys for every connection
    @event.listens_for(engine, "connect")
    def _on_connect(conn, _record):  # type: ignore[no-untyped-def]
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    _run_migrations(engine)

    _engine = engine
    _SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    return engine


def get_session() -> Session:
    """Return a new SQLAlchemy session. Caller is responsible for closing it."""
    if _SessionLocal is None:
        raise RuntimeError("Database not initialised — call init_engine() first.")
    return _SessionLocal()


def _run_migrations(engine: Engine) -> None:
    """Apply lightweight schema migrations tracked in a 'schema_version' table."""
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE IF NOT EXISTS schema_version "
                "(version INTEGER PRIMARY KEY)"
            )
        )
        row = conn.execute(text("SELECT MAX(version) FROM schema_version")).fetchone()
        current = row[0] if row and row[0] is not None else 0

    migrations = _get_migrations()
    for version, sql in migrations:
        if version > current:
            logger.info("Applying migration v%d", version)
            with engine.begin() as conn:
                for statement in sql:
                    conn.execute(text(statement))
                conn.execute(
                    text("INSERT INTO schema_version (version) VALUES (:v)"),
                    {"v": version},
                )


def _get_migrations() -> list[tuple[int, list[str]]]:
    """Ordered list of (version, [sql_statements]) migrations."""
    return [
        (
            1,
            [
                # FTS5 virtual table for full-text search (without description — see v2)
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS snippets_fts
                USING fts5(
                    title, body, tags_text, folder_path,
                    content='snippets', content_rowid='id',
                    tokenize='unicode61'
                )
                """,
                # Keep FTS in sync via triggers
                """
                CREATE TRIGGER IF NOT EXISTS snippets_fts_insert
                AFTER INSERT ON snippets BEGIN
                    INSERT INTO snippets_fts(rowid, title, body, tags_text, folder_path)
                    VALUES (new.id, new.title, new.body, '', '');
                END
                """,
                """
                CREATE TRIGGER IF NOT EXISTS snippets_fts_delete
                AFTER DELETE ON snippets BEGIN
                    INSERT INTO snippets_fts(snippets_fts, rowid, title, body, tags_text, folder_path)
                    VALUES ('delete', old.id, old.title, old.body, '', '');
                END
                """,
                """
                CREATE TRIGGER IF NOT EXISTS snippets_fts_update
                AFTER UPDATE ON snippets BEGIN
                    INSERT INTO snippets_fts(snippets_fts, rowid, title, body, tags_text, folder_path)
                    VALUES ('delete', old.id, old.title, old.body, '', '');
                    INSERT INTO snippets_fts(rowid, title, body, tags_text, folder_path)
                    VALUES (new.id, new.title, new.body, '', '');
                END
                """,
            ],
        ),
        (
            2,
            [
                # Rebuild FTS with description column included
                "DROP TRIGGER IF EXISTS snippets_fts_insert",
                "DROP TRIGGER IF EXISTS snippets_fts_delete",
                "DROP TRIGGER IF EXISTS snippets_fts_update",
                "DROP TABLE IF EXISTS snippets_fts",
                """
                CREATE VIRTUAL TABLE snippets_fts
                USING fts5(
                    title, body, description, tags_text, folder_path,
                    content='snippets', content_rowid='id',
                    tokenize='unicode61'
                )
                """,
                """
                CREATE TRIGGER snippets_fts_insert
                AFTER INSERT ON snippets BEGIN
                    INSERT INTO snippets_fts(rowid, title, body, description, tags_text, folder_path)
                    VALUES (new.id, new.title, new.body, new.description, '', '');
                END
                """,
                """
                CREATE TRIGGER snippets_fts_delete
                AFTER DELETE ON snippets BEGIN
                    INSERT INTO snippets_fts(snippets_fts, rowid, title, body, description, tags_text, folder_path)
                    VALUES ('delete', old.id, old.title, old.body, old.description, '', '');
                END
                """,
                """
                CREATE TRIGGER snippets_fts_update
                AFTER UPDATE ON snippets BEGIN
                    INSERT INTO snippets_fts(snippets_fts, rowid, title, body, description, tags_text, folder_path)
                    VALUES ('delete', old.id, old.title, old.body, old.description, '', '');
                    INSERT INTO snippets_fts(rowid, title, body, description, tags_text, folder_path)
                    VALUES (new.id, new.title, new.body, new.description, '', '');
                END
                """,
                # Backfill any existing rows
                """
                INSERT INTO snippets_fts(rowid, title, body, description, tags_text, folder_path)
                SELECT id, title, body, description, '', '' FROM snippets
                """,
            ],
        ),
    ]
