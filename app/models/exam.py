"""
Exam metadata, sections, questions and options.
Also contains Auth/Security logs.
"""
from enum import Enum
from typing import List
from datetime import datetime
from sqlalchemy import String, Boolean, DateTime, BIGINT, ForeignKey, func, Text, DECIMAL, CHAR, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from core.database import Base
from models.base import TimestampMixin


class IPLogAction(str, Enum):
    login_success = 'login_success'
    login_failed = 'login_failed'
    logout = 'logout'
    exam_attempt_start = 'exam_attempt_start'


class QuestionType(str, Enum):
    mcq = 'mcq'
    subjective = 'subjective'


class ActiveSession(Base):
    __tablename__ = "active_sessions"

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BIGINT, ForeignKey("users.id", ondelete="CASCADE", onupdate="CASCADE"), unique=True, nullable=False)
    access_token_jti: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    refresh_token_jti: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    ip_address: Mapped[str] = mapped_column(String(45), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    user: Mapped["User"] = relationship("User")

    def __repr__(self) -> str:
        return f"<ActiveSession {self.user_id}>"


class IPLog(Base):
    __tablename__ = "ip_logs"

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BIGINT, ForeignKey("users.id", ondelete="SET NULL", onupdate="CASCADE"), nullable=True)
    email_attempted: Mapped[str] = mapped_column(String(100), nullable=False)
    ip_address: Mapped[str] = mapped_column(String(45), nullable=False)
    action: Mapped[IPLogAction] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)

    def __repr__(self) -> str:
        return f"<IPLog {self.action} {self.ip_address}>"


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BIGINT, ForeignKey("users.id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False)
    token: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    created_by: Mapped[int] = mapped_column(BIGINT, ForeignKey("users.id", ondelete="RESTRICT", onupdate="CASCADE"), nullable=False)
    is_used: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)

    user: Mapped["User"] = relationship("User", foreign_keys=[user_id])
    created_by_user: Mapped["User"] = relationship("User", foreign_keys=[created_by])

    def __repr__(self) -> str:
        return f"<PasswordResetToken {self.user_id}>"


class Exam(TimestampMixin, Base):
    __tablename__ = "exams"

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    course_id: Mapped[int] = mapped_column(BIGINT, ForeignKey("courses.id", ondelete="RESTRICT", onupdate="CASCADE"), nullable=False)
    created_by: Mapped[int] = mapped_column(BIGINT, ForeignKey("users.id", ondelete="RESTRICT", onupdate="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    negative_marking_factor: Mapped[float] = mapped_column(DECIMAL(4,2), default=0.00, nullable=False)
    total_marks: Mapped[float] = mapped_column(DECIMAL(7,2), default=0.00, nullable=False)
    passing_marks: Mapped[float] = mapped_column(DECIMAL(7,2), default=0.00, nullable=False)
    start_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    end_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    is_published: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    results_published: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    published_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    results_published_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)

    course: Mapped["Course"] = relationship("Course", back_populates="exams")
    creator: Mapped["User"] = relationship("User", foreign_keys=[created_by])
    questions: Mapped[List["Question"]] = relationship("Question", back_populates="exam", order_by="Question.order_index")
    attempts: Mapped[List["ExamAttempt"]] = relationship("ExamAttempt", back_populates="exam")

    def __repr__(self) -> str:
        return f"<Exam {self.title}>"


class Question(Base):
    __tablename__ = "questions"

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    exam_id: Mapped[int] = mapped_column(BIGINT, ForeignKey("exams.id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False)
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    question_type: Mapped[QuestionType] = mapped_column(nullable=False)
    marks: Mapped[float] = mapped_column(DECIMAL(5,2), nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    word_limit: Mapped[int] = mapped_column(Integer, nullable=True, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)

    exam: Mapped["Exam"] = relationship("Exam", back_populates="questions")
    options: Mapped[List["MCQOption"]] = relationship("MCQOption", back_populates="question")
    answers: Mapped[List["Answer"]] = relationship("Answer", back_populates="question")

    def __repr__(self) -> str:
        return f"<Question {self.id} exam_id={self.exam_id}>"


class MCQOption(Base):
    __tablename__ = "mcq_options"

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    question_id: Mapped[int] = mapped_column(BIGINT, ForeignKey("questions.id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False)
    option_label: Mapped[str] = mapped_column(CHAR(1), nullable=False)
    option_text: Mapped[str] = mapped_column(Text, nullable=False)
    is_correct: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    question: Mapped["Question"] = relationship("Question", back_populates="options")

    def __repr__(self) -> str:
        return f"<MCQOption {self.option_label} for Q{self.question_id}>"
