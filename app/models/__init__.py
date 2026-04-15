"""
Single import surface for all models to ensure mappers configure correctly 
and simplify imports elsewhere in the application.
"""
from core.database import Base
from models.base import TimestampMixin

from models.user import School, Branch, User, StudentProfile, UserRole
from models.course import Course, CourseEnrollment, CourseAssignment, CourseMode
from models.auth import ActiveSession, IPLog, PasswordResetToken, IPLogAction
from models.exam import Exam, Question, MCQOption, QuestionType
from models.attempt import ExamAttempt, Answer, SubjectiveGrade, AttemptStatus
from models.result import ExamResult
from models.proctor import ProctorViolation, ProctorSnapshot, ViolationType
from models.notification import Notification
from models.forum import ForumThread, ForumPost
from models.discussion import DiscussionPost, DiscussionReply
from models.log import SystemLog, AuditLog, SystemLogEventType, LogLevel

__all__ = [
    "Base",
    "TimestampMixin",
    "School", "Branch", "User", "StudentProfile", "UserRole",
    "Course", "CourseEnrollment", "CourseAssignment", "CourseMode",
    "ActiveSession", "IPLog", "PasswordResetToken", "Exam",
    "Question", "MCQOption", "QuestionType", "IPLogAction",
    "ExamAttempt", "Answer", "SubjectiveGrade", "AttemptStatus",
    "ExamResult",
    "ProctorViolation", "ProctorSnapshot", "ViolationType",
    "Notification",
    "ForumThread", "ForumPost",
    "DiscussionPost", "DiscussionReply",
    "SystemLog", "AuditLog", "SystemLogEventType", "LogLevel",
]

