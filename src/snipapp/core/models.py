"""SQLAlchemy ORM models: Folder, Snippet, Tag, SnippetTag."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Folder(Base):
    __tablename__ = "folders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    parent_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("folders.id"), nullable=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    parent: Mapped[Folder | None] = relationship("Folder", remote_side="Folder.id", back_populates="children")
    children: Mapped[list[Folder]] = relationship("Folder", back_populates="parent")
    snippets: Mapped[list[Snippet]] = relationship("Snippet", back_populates="folder")


class Tag(Base):
    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)

    snippets: Mapped[list[Snippet]] = relationship(
        "Snippet", secondary="snippet_tags", back_populates="tags"
    )


class SnippetTag(Base):
    __tablename__ = "snippet_tags"

    snippet_id: Mapped[int] = mapped_column(Integer, ForeignKey("snippets.id"), primary_key=True)
    tag_id: Mapped[int] = mapped_column(Integer, ForeignKey("tags.id"), primary_key=True)


class Snippet(Base):
    __tablename__ = "snippets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    folder_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("folders.id"), nullable=True
    )
    title: Mapped[str] = mapped_column(String, nullable=False, default="Untitled")
    body: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str] = mapped_column(String, nullable=False, default="text")
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    use_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    folder: Mapped[Folder | None] = relationship("Folder", back_populates="snippets")
    tags: Mapped[list[Tag]] = relationship(
        "Tag", secondary="snippet_tags", back_populates="snippets"
    )
