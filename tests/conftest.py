"""Shared pytest fixtures for the ByteSnip test suite."""

import pytest

from snipapp.core.db import init_engine, get_session
from snipapp.core.models import Folder, Snippet, Tag


@pytest.fixture()
def db(tmp_path):
    """Initialise a fresh in-memory-equivalent SQLite DB and yield the engine."""
    engine = init_engine(tmp_path / "test.db")
    yield engine
    engine.dispose()


@pytest.fixture()
def session(db):
    """Yield an open Session bound to the test DB."""
    with get_session() as s:
        yield s


@pytest.fixture()
def sample_snippets(db):
    """Insert a small, varied set of snippets and return them as a list."""
    with get_session() as s:
        folder = Folder(name="Utils")
        s.add(folder)
        s.flush()

        t1 = Tag(name="sorting")
        t2 = Tag(name="io")

        sn1 = Snippet(
            title="Bubble sort",
            body="def bubble(lst):\n    pass",
            language="python",
            description="classic sorting algorithm",
            folder_id=folder.id,
        )
        sn1.tags.append(t1)

        sn2 = Snippet(
            title="Read file",
            body="with open('f') as fh:\n    data = fh.read()",
            language="python",
            description="reads a whole file into memory",
            folder_id=folder.id,
        )
        sn2.tags.append(t2)

        sn3 = Snippet(
            title="HTTP GET",
            body="fetch('https://example.com')",
            language="javascript",
            description="simple fetch request",
        )

        s.add_all([sn1, sn2, sn3])
        s.commit()
        ids = [sn1.id, sn2.id, sn3.id]

    return ids
