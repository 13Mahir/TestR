"""
Models for the Discussion Forum.
"""
from typing import List, TYPE_CHECKING, Optional
from sqlalchemy import String, Boolean, BIGINT, ForeignKey, Text, CHAR
from sqlalchemy.orm import Mapped, mapped_column, relationship
from core.database import Base
from models.base import TimestampMixin

if TYPE_CHECKING:
    from models.user import User


class DiscussionPost(TimestampMixin, Base):
    __tablename__ = "discussion_posts"

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    author_id: Mapped[int] = mapped_column(BIGINT, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    is_pinned: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Selective Access Restrictions
    restrict_school_id: Mapped[Optional[int]] = mapped_column(BIGINT, ForeignKey("schools.id"), nullable=True)
    restrict_branch_id: Mapped[Optional[int]] = mapped_column(BIGINT, ForeignKey("branches.id"), nullable=True)
    restrict_batch_year: Mapped[Optional[str]] = mapped_column(CHAR(2), nullable=True)
    restrict_emails: Mapped[Optional[str]] = mapped_column(Text, nullable=True) # JSON list as string

    author: Mapped["User"] = relationship("User")
    replies: Mapped[List["DiscussionReply"]] = relationship("DiscussionReply", back_populates="post", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<DiscussionPost {self.id}: {self.title[:20]}>"

class DiscussionReply(TimestampMixin, Base):
    __tablename__ = "discussion_replies"

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    post_id: Mapped[int] = mapped_column(BIGINT, ForeignKey("discussion_posts.id", ondelete="CASCADE"), nullable=False)
    author_id: Mapped[int] = mapped_column(BIGINT, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    post: Mapped["DiscussionPost"] = relationship("DiscussionPost", back_populates="replies")
    author: Mapped["User"] = relationship("User")

    def __repr__(self) -> str:
        return f"<DiscussionReply {self.id} for Post {self.post_id}>"
