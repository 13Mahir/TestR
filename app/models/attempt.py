"""
Exam attempts, answers, and subjective grading models.
"""
from enum import Enum
from typing import List
from datetime import datetime
from sqlalchemy import String, Boolean, DateTime, BIGINT, ForeignKey, func, Text, DECIMAL
from sqlalchemy.orm import Mapped, mapped_column, relationship
from core.database import Base


class AttemptStatus(str, Enum):
    in_progress = 'in_progress'
    submitted = 'submitted'
    auto_submitted = 'auto_submitted'


class ExamAttempt(Base):
    __tablename__ = "exam_attempts"

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    exam_id: Mapped[int] = mapped_column(BIGINT, ForeignKey("exams.id", ondelete="RESTRICT", onupdate="CASCADE"), nullable=False)
    student_id: Mapped[int] = mapped_column(BIGINT, ForeignKey("users.id", ondelete="RESTRICT", onupdate="CASCADE"), nullable=False)
    ip_address: Mapped[str] = mapped_column(String(45), nullable=False)
    status: Mapped[AttemptStatus] = mapped_column(nullable=False, default=AttemptStatus.in_progress)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(DateTime, nullable=True, default=None)

    exam: Mapped["Exam"] = relationship("Exam", back_populates="attempts")
    student: Mapped["User"] = relationship("User")
    answers: Mapped[List["Answer"]] = relationship("Answer", back_populates="attempt")
    result: Mapped["ExamResult"] = relationship("ExamResult", back_populates="attempt", uselist=False)
    violations: Mapped[List["ProctorViolation"]] = relationship("ProctorViolation", back_populates="attempt")
    snapshots: Mapped[List["ProctorSnapshot"]] = relationship("ProctorSnapshot", back_populates="attempt")

    def __repr__(self) -> str:
        return f"<ExamAttempt exam={self.exam_id} student={self.student_id}>"


class Answer(Base):
    __tablename__ = "answers"

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    attempt_id: Mapped[int] = mapped_column(BIGINT, ForeignKey("exam_attempts.id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False)
    question_id: Mapped[int] = mapped_column(BIGINT, ForeignKey("questions.id", ondelete="RESTRICT", onupdate="CASCADE"), nullable=False)
    selected_option_id: Mapped[int] = mapped_column(BIGINT, ForeignKey("mcq_options.id", ondelete="SET NULL", onupdate="CASCADE"), nullable=True, default=None)
    subjective_text: Mapped[str] = mapped_column(Text, nullable=True, default=None)
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=True, default=None)
    marks_awarded: Mapped[float] = mapped_column(DECIMAL(5,2), nullable=True, default=None)

    attempt: Mapped["ExamAttempt"] = relationship("ExamAttempt", back_populates="answers")
    question: Mapped["Question"] = relationship("Question", back_populates="answers")
    selected_option: Mapped["MCQOption"] = relationship("MCQOption")
    grade: Mapped["SubjectiveGrade"] = relationship("SubjectiveGrade", back_populates="answer", uselist=False)

    def __repr__(self) -> str:
        return f"<Answer attempt={self.attempt_id} question={self.question_id}>"


class SubjectiveGrade(Base):
    __tablename__ = "subjective_grades"

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    answer_id: Mapped[int] = mapped_column(BIGINT, ForeignKey("answers.id", ondelete="CASCADE", onupdate="CASCADE"), unique=True, nullable=False)
    graded_by: Mapped[int] = mapped_column(BIGINT, ForeignKey("users.id", ondelete="RESTRICT", onupdate="CASCADE"), nullable=False)
    marks_awarded: Mapped[float] = mapped_column(DECIMAL(5,2), nullable=False)
    feedback: Mapped[str] = mapped_column(Text, nullable=True)
    graded_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)

    answer: Mapped["Answer"] = relationship("Answer", back_populates="grade")
    grader: Mapped["User"] = relationship("User")

    def __repr__(self) -> str:
        return f"<SubjectiveGrade answer={self.answer_id}>"
