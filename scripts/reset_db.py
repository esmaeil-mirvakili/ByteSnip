"""Reset the ByteSnip database — deletes all snippets, folders, and tags.

Usage:
    python scripts/reset_db.py          # prompts for confirmation
    python scripts/reset_db.py --yes    # skips confirmation
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from snipapp.core.db import get_db_path, init_engine
from snipapp.core.models import Folder, Snippet, SnippetTag, Tag
from sqlalchemy import text


def reset(engine) -> None:
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM snippet_tags"))
        conn.execute(text("DELETE FROM tags"))
        conn.execute(text("DELETE FROM snippets"))
        conn.execute(text("DELETE FROM folders"))
        # FTS5 content tables require this special command to clear the index
        conn.execute(text("INSERT INTO snippets_fts(snippets_fts) VALUES('delete-all')"))
    print("Database reset — all snippets, folders, and tags removed.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Reset the ByteSnip database.")
    parser.add_argument("--yes", action="store_true", help="Skip confirmation prompt.")
    args = parser.parse_args()

    db_path = get_db_path()
    print(f"Database: {db_path}")

    if not db_path.exists():
        print("No database found — nothing to reset.")
        return

    if not args.yes:
        answer = input("This will permanently delete all snippets, folders, and tags. Continue? [y/N] ")
        if answer.strip().lower() != "y":
            print("Aborted.")
            return

    engine = init_engine(db_path)
    reset(engine)


if __name__ == "__main__":
    main()
