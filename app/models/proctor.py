"""
Proctoring violation events and snapshots models.
"""
from enum import Enum
from datetime import datetime
from sqlalchemy import String, DateTime, BIGINT, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from core.database import Base

class ViolationType(str, Enum):
    tab_switch = 'tab_switch'
    fullscreen_exit = 'fullscreen_exit'
    camera_unavailable = 'camera_unavailable'
    copy_paste_attempt = 'copy_paste_attempt'

class ProctorViolation(Base):
    __tablename__ = "proctor_violations"

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    attempt_id: Mapped[int] = mapped_column(BIGINT, ForeignKey("exam_attempts.id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False)
    violation_type: Mapped[ViolationType] = mapped_column(nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)
    details: Mapped[str] = mapped_column(String(255), nullable=True)

    attempt: Mapped["ExamAttempt"] = relationship("ExamAttempt", back_populates="violations")

    def __repr__(self) -> str:
        return f"<ProctorViolation {self.violation_type} on {self.attempt_id}>"

class ProctorSnapshot(Base):
    __tablename__ = "proctor_snapshots"

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    attempt_id: Mapped[int] = mapped_column(BIGINT, ForeignKey("exam_attempts.id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False)
    gcs_path: Mapped[str] = mapped_column(String(500), nullable=False)
    captured_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)

    attempt: Mapped["ExamAttempt"] = relationship("ExamAttempt", back_populates="snapshots")

    async def get_signed_url(self, expiry_minutes: int = 60) -> str:
        """Generates a GCS signed URL for this snapshot. Implemented in Prompt 44."""
        raise NotImplementedError

    def __repr__(self) -> str:
        return f"<ProctorSnapshot {self.id} on {self.attempt_id}>"
