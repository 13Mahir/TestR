"""
Exam results and aggregates models.
"""
from datetime import datetime
from sqlalchemy import Boolean, DateTime, BIGINT, ForeignKey, func, DECIMAL
from sqlalchemy.orm import Mapped, mapped_column, relationship
from core.database import Base


class ExamResult(Base):
    __tablename__ = "exam_results"

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    attempt_id: Mapped[int] = mapped_column(BIGINT, ForeignKey("exam_attempts.id", ondelete="RESTRICT", onupdate="CASCADE"), unique=True, nullable=False)
    exam_id: Mapped[int] = mapped_column(BIGINT, ForeignKey("exams.id", ondelete="RESTRICT", onupdate="CASCADE"), nullable=False)
    student_id: Mapped[int] = mapped_column(BIGINT, ForeignKey("users.id", ondelete="RESTRICT", onupdate="CASCADE"), nullable=False)
    mcq_marks_awarded: Mapped[float] = mapped_column(DECIMAL(7,2), default=0.00, nullable=False)
    subjective_marks_awarded: Mapped[float] = mapped_column(DECIMAL(7,2), default=0.00, nullable=False)
    negative_marks_deducted: Mapped[float] = mapped_column(DECIMAL(7,2), default=0.00, nullable=False)
    total_marks_awarded: Mapped[float] = mapped_column(DECIMAL(7,2), default=0.00, nullable=False)
    is_pass: Mapped[bool] = mapped_column(Boolean, nullable=True, default=None)
    published_by: Mapped[int] = mapped_column(BIGINT, ForeignKey("users.id", ondelete="SET NULL", onupdate="CASCADE"), nullable=True, default=None)
    published_at: Mapped[datetime] = mapped_column(DateTime, nullable=True, default=None)
    computed_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)

    attempt: Mapped["ExamAttempt"] = relationship("ExamAttempt", back_populates="result")
    exam: Mapped["Exam"] = relationship("Exam")
    student: Mapped["User"] = relationship("User", foreign_keys=[student_id])
    publisher: Mapped["User"] = relationship("User", foreign_keys=[published_by], lazy="select")

    @property
    def total_computed(self) -> float:
        return float(self.mcq_marks_awarded) + float(self.subjective_marks_awarded) - float(self.negative_marks_deducted)

    def __repr__(self) -> str:
        return f"<ExamResult attempt={self.attempt_id}>"
