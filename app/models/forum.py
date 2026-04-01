"""
Discussion forum threads and posts models.
"""
from typing import List
from sqlalchemy import String, Boolean, BIGINT, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from core.database import Base
from models.base import TimestampMixin

class ForumThread(TimestampMixin, Base):
    __tablename__ = "forum_threads"

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    created_by: Mapped[int] = mapped_column(BIGINT, ForeignKey("users.id", ondelete="RESTRICT", onupdate="CASCADE"), nullable=False)
    is_pinned: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_locked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    creator: Mapped["User"] = relationship("User")
    posts: Mapped[List["ForumPost"]] = relationship(
        "ForumPost",
        primaryjoin="and_(ForumThread.id==ForumPost.thread_id, ForumPost.parent_post_id==None)",
        lazy="dynamic",
        back_populates="thread"
    )

    def __repr__(self) -> str:
        return f"<ForumThread {self.title}>"

class ForumPost(TimestampMixin, Base):
    __tablename__ = "forum_posts"

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    thread_id: Mapped[int] = mapped_column(BIGINT, ForeignKey("forum_threads.id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False)
    parent_post_id: Mapped[int] = mapped_column(BIGINT, ForeignKey("forum_posts.id", ondelete="SET NULL", onupdate="CASCADE"), nullable=True, default=None)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[int] = mapped_column(BIGINT, ForeignKey("users.id", ondelete="RESTRICT", onupdate="CASCADE"), nullable=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    thread: Mapped["ForumThread"] = relationship("ForumThread", back_populates="posts", foreign_keys=[thread_id])
    creator: Mapped["User"] = relationship("User")
    parent: Mapped["ForumPost"] = relationship("ForumPost", remote_side=[id], back_populates="replies")
    replies: Mapped[List["ForumPost"]] = relationship("ForumPost", back_populates="parent", cascade="all, delete-orphan")

    @property
    def display_content(self) -> str:
        return "[deleted]" if self.is_deleted else self.content

    def __repr__(self) -> str:
        return f"<ForumPost {self.id} on Thread {self.thread_id}>"
