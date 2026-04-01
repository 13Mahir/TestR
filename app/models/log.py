"""
System event logs and admin audit logs models.
"""
from enum import Enum
from datetime import datetime
from sqlalchemy import String, DateTime, BIGINT, ForeignKey, func, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from core.database import Base

class SystemLogEventType(str, Enum):
    exam_created = 'exam_created'
    exam_published = 'exam_published'
    results_published = 'results_published'
    users_created = 'users_created'
    course_created = 'course_created'
    course_activated = 'course_activated'
    course_deactivated = 'course_deactivated'

# Append-only
class SystemLog(Base):
    __tablename__ = "system_logs"

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    event_type: Mapped[SystemLogEventType] = mapped_column(nullable=False)
    actor_id: Mapped[int] = mapped_column(BIGINT, ForeignKey("users.id", ondelete="RESTRICT", onupdate="CASCADE"), nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    log_metadata: Mapped[dict] = mapped_column("metadata", JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)

    actor: Mapped["User"] = relationship("User", lazy="noload")

    def __repr__(self) -> str:
        return f"<SystemLog {self.event_type} by {self.actor_id}>"

# Append-only
class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    admin_id: Mapped[int] = mapped_column(BIGINT, ForeignKey("users.id", ondelete="RESTRICT", onupdate="CASCADE"), nullable=False)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    target_type: Mapped[str] = mapped_column(String(50), nullable=False)
    target_id: Mapped[str] = mapped_column(String(50), nullable=True)
    details: Mapped[dict] = mapped_column(JSON, nullable=True)
    ip_address: Mapped[str] = mapped_column(String(45), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)

    admin: Mapped["User"] = relationship("User", lazy="noload")

    def __repr__(self) -> str:
        return f"<AuditLog {self.action} by {self.admin_id}>"
