"""
Exam results and aggregates models.
"""
from datetime import datetime
from decimal import Decimal
from sqlalchemy import Boolean, DateTime, Integer, ForeignKey, func, DECIMAL
from sqlalchemy.orm import Mapped, mapped_column, relationship
from core.database import Base


class ExamResult(Base):
    __tablename__ = "exam_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    attempt_id: Mapped[int] = mapped_column(Integer, ForeignKey("exam_attempts.id", ondelete="RESTRICT", onupdate="CASCADE"), unique=True, nullable=False)
    exam_id: Mapped[int] = mapped_column(Integer, ForeignKey("exams.id", ondelete="RESTRICT", onupdate="CASCADE"), nullable=False)
    student_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="RESTRICT", onupdate="CASCADE"), nullable=False)
    mcq_marks_awarded: Mapped[Decimal] = mapped_column(DECIMAL(7,2), default=Decimal("0.00"), nullable=False)
    subjective_marks_awarded: Mapped[Decimal] = mapped_column(DECIMAL(7,2), default=Decimal("0.00"), nullable=False)
    negative_marks_deducted: Mapped[Decimal] = mapped_column(DECIMAL(7,2), default=Decimal("0.00"), nullable=False)
    total_marks_awarded: Mapped[Decimal] = mapped_column(DECIMAL(7,2), default=Decimal("0.00"), nullable=False)
    is_pass: Mapped[bool] = mapped_column(Boolean, nullable=True, default=None)
    published_by: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL", onupdate="CASCADE"), nullable=True, default=None)
    published_at: Mapped[datetime] = mapped_column(DateTime, nullable=True, default=None)
    computed_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)

    attempt: Mapped["ExamAttempt"] = relationship("ExamAttempt", back_populates="result")
    exam: Mapped["Exam"] = relationship("Exam")
    student: Mapped["User"] = relationship("User", foreign_keys=[student_id])
    publisher: Mapped["User"] = relationship("User", foreign_keys=[published_by], lazy="select")

    @property
    def total_computed(self) -> Decimal:
        return self.mcq_marks_awarded + self.subjective_marks_awarded - self.negative_marks_deducted

    def __repr__(self) -> str:
        return f"<ExamResult attempt={self.attempt_id}>"
