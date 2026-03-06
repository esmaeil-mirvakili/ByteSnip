"""Tests for snipapp.core.models — ORM fields, relationships, constraints."""

import pytest
from sqlalchemy.exc import IntegrityError

from snipapp.core.db import get_session
from snipapp.core.models import Folder, Snippet, SnippetTag, Tag


# ---------------------------------------------------------------------------
# Snippet defaults and fields
# ---------------------------------------------------------------------------

class TestSnippetDefaults:
    def test_title_default(self, db):
        with get_session() as s:
            sn = Snippet(body="x = 1", language="python")
            s.add(sn)
            s.commit()
            assert sn.title == "Untitled"

    def test_description_default_empty(self, db):
        with get_session() as s:
            sn = Snippet(title="t", body="x = 1", language="python")
            s.add(sn)
            s.commit()
            assert sn.description == ""

    def test_use_count_default_zero(self, db):
        with get_session() as s:
            sn = Snippet(title="t", body="x", language="python")
            s.add(sn)
            s.commit()
            assert sn.use_count == 0

    def test_last_used_at_default_none(self, db):
        with get_session() as s:
            sn = Snippet(title="t", body="x", language="python")
            s.add(sn)
            s.commit()
            assert sn.last_used_at is None

    def test_created_at_set_on_insert(self, db):
        with get_session() as s:
            sn = Snippet(title="t", body="x", language="python")
            s.add(sn)
            s.commit()
            assert sn.created_at is not None

    def test_id_assigned_after_commit(self, db):
        with get_session() as s:
            sn = Snippet(title="t", body="x", language="python")
            s.add(sn)
            s.commit()
            assert isinstance(sn.id, int)
            assert sn.id > 0

    def test_explicit_description(self, db):
        with get_session() as s:
            sn = Snippet(title="t", body="x", language="python", description="my desc")
            s.add(sn)
            s.commit()
            fetched = s.get(Snippet, sn.id)
            assert fetched.description == "my desc"

    def test_use_count_increment(self, db):
        with get_session() as s:
            sn = Snippet(title="t", body="x", language="python")
            s.add(sn)
            s.commit()
            sn.use_count += 1
            s.commit()
            fetched = s.get(Snippet, sn.id)
            assert fetched.use_count == 1


# ---------------------------------------------------------------------------
# Folder model and hierarchy
# ---------------------------------------------------------------------------

class TestFolderModel:
    def test_create_root_folder(self, db):
        with get_session() as s:
            f = Folder(name="Root")
            s.add(f)
            s.commit()
            assert f.id is not None
            assert f.parent_id is None

    def test_parent_child_relationship(self, db):
        with get_session() as s:
            parent = Folder(name="Parent")
            s.add(parent)
            s.flush()
            child = Folder(name="Child", parent_id=parent.id)
            s.add(child)
            s.commit()

            assert child.parent_id == parent.id
            assert child.parent.name == "Parent"

    def test_children_list(self, db):
        with get_session() as s:
            parent = Folder(name="Parent")
            s.add(parent)
            s.flush()
            c1 = Folder(name="C1", parent_id=parent.id)
            c2 = Folder(name="C2", parent_id=parent.id)
            s.add_all([c1, c2])
            s.commit()

            fetched = s.get(Folder, parent.id)
            assert len(fetched.children) == 2

    def test_three_level_hierarchy(self, db):
        with get_session() as s:
            root = Folder(name="root")
            s.add(root)
            s.flush()
            mid = Folder(name="mid", parent_id=root.id)
            s.add(mid)
            s.flush()
            leaf = Folder(name="leaf", parent_id=mid.id)
            s.add(leaf)
            s.commit()

            assert leaf.parent.name == "mid"
            assert leaf.parent.parent.name == "root"

    def test_snippet_in_folder(self, db):
        with get_session() as s:
            f = Folder(name="Scripts")
            s.add(f)
            s.flush()
            sn = Snippet(title="t", body="x", language="python", folder_id=f.id)
            s.add(sn)
            s.commit()

            fetched = s.get(Folder, f.id)
            assert len(fetched.snippets) == 1
            assert fetched.snippets[0].title == "t"

    def test_snippet_without_folder(self, db):
        with get_session() as s:
            sn = Snippet(title="t", body="x", language="python")
            s.add(sn)
            s.commit()
            assert sn.folder_id is None
            assert sn.folder is None


# ---------------------------------------------------------------------------
# Tag model
# ---------------------------------------------------------------------------

class TestTagModel:
    def test_create_tag(self, db):
        with get_session() as s:
            t = Tag(name="utils")
            s.add(t)
            s.commit()
            assert t.id is not None

    def test_tag_name_unique(self, db):
        with get_session() as s:
            s.add(Tag(name="dup"))
            s.commit()
        with get_session() as s:
            s.add(Tag(name="dup"))
            with pytest.raises(IntegrityError):
                s.commit()

    def test_multiple_tags_on_snippet(self, db):
        with get_session() as s:
            sn = Snippet(title="t", body="x", language="python")
            sn.tags = [Tag(name="a"), Tag(name="b"), Tag(name="c")]
            s.add(sn)
            s.commit()
            assert len(sn.tags) == 3

    def test_tag_shared_across_snippets(self, db):
        with get_session() as s:
            tag = Tag(name="shared")
            sn1 = Snippet(title="s1", body="x", language="python")
            sn2 = Snippet(title="s2", body="y", language="python")
            sn1.tags.append(tag)
            sn2.tags.append(tag)
            s.add_all([sn1, sn2])
            s.commit()

            fetched_tag = s.get(Tag, tag.id)
            assert len(fetched_tag.snippets) == 2

    def test_snippet_tag_junction_row(self, db):
        with get_session() as s:
            from sqlalchemy import select
            tag = Tag(name="x")
            sn = Snippet(title="t", body="y", language="python")
            sn.tags.append(tag)
            s.add(sn)
            s.commit()

            row = s.execute(
                select(SnippetTag).where(
                    SnippetTag.snippet_id == sn.id,
                    SnippetTag.tag_id == tag.id,
                )
            ).first()
            assert row is not None
