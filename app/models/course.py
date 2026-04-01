"""
Course and Enrollment models.
"""
from enum import Enum
from typing import List
from datetime import datetime
from sqlalchemy import String, Boolean, DateTime, BIGINT, ForeignKey, func, Text, CHAR, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from core.database import Base
from models.base import TimestampMixin


class CourseMode(str, Enum):
    theory = 'T'
    practical = 'P'


class Course(TimestampMixin, Base):
    __tablename__ = "courses"

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    course_code: Mapped[str] = mapped_column(String(15), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    branch_id: Mapped[int] = mapped_column(BIGINT, ForeignKey("branches.id", ondelete="RESTRICT", onupdate="CASCADE"), nullable=False)
    year: Mapped[str] = mapped_column(CHAR(2), nullable=False)
    mode: Mapped[CourseMode] = mapped_column(
        SAEnum(CourseMode, values_callable=lambda e: [m.value for m in e]),
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_by: Mapped[int] = mapped_column(BIGINT, ForeignKey("users.id", ondelete="RESTRICT", onupdate="CASCADE"), nullable=False)

    branch: Mapped["Branch"] = relationship("Branch")
    creator: Mapped["User"] = relationship("User", foreign_keys=[created_by])
    enrollments: Mapped[List["CourseEnrollment"]] = relationship("CourseEnrollment", back_populates="course")
    assignments: Mapped[List["CourseAssignment"]] = relationship("CourseAssignment", back_populates="course")
    exams: Mapped[List["Exam"]] = relationship("Exam", back_populates="course")

    def __repr__(self) -> str:
        return f"<Course {self.course_code}>"


class CourseEnrollment(Base):
    __tablename__ = "course_enrollments"

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    course_id: Mapped[int] = mapped_column(BIGINT, ForeignKey("courses.id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False)
    student_id: Mapped[int] = mapped_column(BIGINT, ForeignKey("users.id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False)
    enrolled_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)
    enrolled_by: Mapped[int] = mapped_column(BIGINT, ForeignKey("users.id", ondelete="RESTRICT", onupdate="CASCADE"), nullable=False)

    course: Mapped["Course"] = relationship("Course", back_populates="enrollments")
    student: Mapped["User"] = relationship("User", foreign_keys=[student_id], back_populates="enrollments")
    enrolled_by_user: Mapped["User"] = relationship("User", foreign_keys=[enrolled_by])

    def __repr__(self) -> str:
        return f"<CourseEnrollment {self.course_id}-{self.student_id}>"


class CourseAssignment(Base):
    __tablename__ = "course_assignments"

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    course_id: Mapped[int] = mapped_column(BIGINT, ForeignKey("courses.id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False)
    teacher_id: Mapped[int] = mapped_column(BIGINT, ForeignKey("users.id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False)
    assigned_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)
    assigned_by: Mapped[int] = mapped_column(BIGINT, ForeignKey("users.id", ondelete="RESTRICT", onupdate="CASCADE"), nullable=False)

    course: Mapped["Course"] = relationship("Course", back_populates="assignments")
    teacher: Mapped["User"] = relationship("User", foreign_keys=[teacher_id], back_populates="assignments")
    assigned_by_user: Mapped["User"] = relationship("User", foreign_keys=[assigned_by])

    def __repr__(self) -> str:
        return f"<CourseAssignment {self.course_id}-{self.teacher_id}>"
