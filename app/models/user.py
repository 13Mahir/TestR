"""
User, School, Branch, and StudentProfile models for the TestR.
"""
from enum import Enum
from typing import List
from datetime import datetime
from sqlalchemy import String, Boolean, DateTime, BIGINT, ForeignKey, func, CHAR, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from core.database import Base
from models.base import TimestampMixin


class UserRole(str, Enum):
    admin = 'admin'
    teacher = 'teacher'
    student = 'student'


class School(Base):
    __tablename__ = "schools"

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(10), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)

    branches: Mapped[List["Branch"]] = relationship("Branch", back_populates="school")

    def __repr__(self) -> str:
        return f"<School {self.code}>"


class Branch(Base):
    __tablename__ = "branches"

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(10), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    school_id: Mapped[int] = mapped_column(BIGINT, ForeignKey("schools.id", ondelete="RESTRICT", onupdate="CASCADE"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)

    school: Mapped["School"] = relationship("School", back_populates="branches")

    def __repr__(self) -> str:
        return f"<Branch {self.code}>"


class User(TimestampMixin, Base):
    __tablename__ = "users"

    __table_args__ = (
        CheckConstraint(
            r"email REGEXP '^[0-9]{2}[a-zA-Z]{3}[0-9]{3}@[a-zA-Z]+\.clg\.ac\.in$' OR "
            r"email REGEXP '^[a-zA-Z]+\.[a-zA-Z]+@clg\.ac\.in$' OR "
            r"email = 'admin@clg.ac.in'",
            name='valid_user_emails'
        ),
    )

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(nullable=False)
    first_name: Mapped[str] = mapped_column(String(50), nullable=False)
    last_name: Mapped[str] = mapped_column(String(50), nullable=False, default='')
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    force_password_reset: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    student_profile: Mapped["StudentProfile"] = relationship("StudentProfile", back_populates="user", uselist=False)
    enrollments: Mapped[List["CourseEnrollment"]] = relationship("CourseEnrollment", back_populates="student", foreign_keys="[CourseEnrollment.student_id]")
    assignments: Mapped[List["CourseAssignment"]] = relationship("CourseAssignment", back_populates="teacher", foreign_keys="[CourseAssignment.teacher_id]")
    notifications: Mapped[List["Notification"]] = relationship("Notification", back_populates="user")

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def is_student(self) -> bool:
        return self.role == UserRole.student

    @property
    def is_teacher(self) -> bool:
        return self.role == UserRole.teacher

    @property
    def is_admin(self) -> bool:
        return self.role == UserRole.admin

    def __repr__(self) -> str:
        return f"<User {self.email}>"


class StudentProfile(Base):
    __tablename__ = "student_profiles"

    user_id: Mapped[int] = mapped_column(BIGINT, ForeignKey("users.id", ondelete="CASCADE", onupdate="CASCADE"), primary_key=True)
    batch_year: Mapped[str] = mapped_column(CHAR(2), nullable=False)
    branch_id: Mapped[int] = mapped_column(BIGINT, ForeignKey("branches.id", ondelete="RESTRICT", onupdate="CASCADE"), nullable=False)
    roll_number: Mapped[str] = mapped_column(String(10), nullable=False)

    user: Mapped["User"] = relationship("User", back_populates="student_profile")
    branch: Mapped["Branch"] = relationship("Branch")

    def __repr__(self) -> str:
        return f"<StudentProfile {self.roll_number}>"
