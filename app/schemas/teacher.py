"""
schemas/teacher.py
Pydantic request and response schemas for teacher panel endpoints.
Covers: assigned courses, exam creation, question management,
grading, grade book, and result publishing.
"""

from pydantic import BaseModel, field_validator, model_validator
from typing import Optional
from datetime import datetime
from decimal import Decimal


# ── Course schemas ────────────────────────────────────────────────

class AssignedCourseOut(BaseModel):
    """A course the teacher is assigned to."""
    id:                int
    course_code:       str
    name:              str
    description:       Optional[str] = None
    branch_code:       str
    year:              str
    mode:              str
    is_active:         bool
    enrolled_students: int
    assigned_at:       datetime

    model_config = {"from_attributes": False}


# ── Exam schemas ──────────────────────────────────────────────────

class ExamCreateRequest(BaseModel):
    """Request body for POST /api/teacher/exams"""
    course_id:               int
    title:                   str
    description:             Optional[str] = None
    duration_minutes:        int
    negative_marking_factor: Decimal = Decimal("0.0")
    passing_marks:           Decimal = Decimal("0.0")
    start_time:              datetime
    end_time:                datetime

    @field_validator("title")
    @classmethod
    def title_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("title must not be empty.")
        return v

    @field_validator("duration_minutes")
    @classmethod
    def validate_duration(cls, v: int) -> int:
        if v < 5:
            raise ValueError(
                "duration_minutes must be at least 5."
            )
        if v > 480:
            raise ValueError(
                "duration_minutes must not exceed 480 (8 hours)."
            )
        return v

    @field_validator("negative_marking_factor")
    @classmethod
    def validate_negative_factor(cls, v: Decimal) -> Decimal:
        if v < 0 or v > 1:
            raise ValueError(
                "negative_marking_factor must be between 0.0 "
                "(no penalty) and 1.0 (full mark deducted)."
            )
        return v

    @model_validator(mode="after")
    def validate_times(self) -> "ExamCreateRequest":
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time.")
        duration_from_times = (
            self.end_time - self.start_time
        ).total_seconds() / 60
        if self.duration_minutes > duration_from_times:
            raise ValueError(
                "duration_minutes cannot exceed the time window "
                "between start_time and end_time."
            )
        return self


class ExamUpdateRequest(BaseModel):
    """
    Request body for PATCH /api/teacher/exams/{id}
    All fields are optional — only provided fields are updated.
    An exam that has been published cannot be updated.
    """
    title:                   Optional[str]   = None
    description:             Optional[str]   = None
    duration_minutes:        Optional[int]   = None
    negative_marking_factor: Optional[Decimal] = None
    passing_marks:           Optional[Decimal] = None
    start_time:              Optional[datetime] = None
    end_time:                Optional[datetime] = None


class ExamOut(BaseModel):
    """An exam as returned to the client."""
    id:                      int
    course_id:               int
    course_code:             str
    title:                   str
    description:             Optional[str] = None
    duration_minutes:        int
    negative_marking_factor: Decimal
    total_marks:             Decimal
    passing_marks:           Decimal
    start_time:              datetime
    end_time:                datetime
    is_published:            bool
    results_published:       bool
    published_at:            Optional[datetime] = None
    results_published_at:    Optional[datetime] = None
    question_count:          int = 0
    created_at:              datetime

    model_config = {"from_attributes": False}


class ExamListResponse(BaseModel):
    """Paginated exam list."""
    items:       list[ExamOut]
    total:       int
    page:        int
    page_size:   int
    total_pages: int
    has_next:    bool
    has_prev:    bool


# ── Question schemas ──────────────────────────────────────────────

class MCQOptionIn(BaseModel):
    """A single MCQ option as sent in a create request."""
    option_label: str    # 'A', 'B', 'C', or 'D'
    option_text:  str
    is_correct:   bool = False

    @field_validator("option_label")
    @classmethod
    def validate_label(cls, v: str) -> str:
        v = v.strip().upper()
        if v not in ("A", "B", "C", "D"):
            raise ValueError(
                "option_label must be one of: A, B, C, D."
            )
        return v

    @field_validator("option_text")
    @classmethod
    def text_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("option_text must not be empty.")
        return v


class MCQQuestionCreateRequest(BaseModel):
    """Request body for POST /api/teacher/exams/{id}/questions/mcq"""
    question_text: str
    marks:         Decimal
    order_index:   int = 0
    options:       list[MCQOptionIn]

    @field_validator("question_text")
    @classmethod
    def text_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("question_text must not be empty.")
        return v

    @field_validator("marks")
    @classmethod
    def validate_marks(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("marks must be greater than 0.")
        return v

    @model_validator(mode="after")
    def validate_options(self) -> "MCQQuestionCreateRequest":
        if len(self.options) < 2:
            raise ValueError(
                "MCQ must have at least 2 options."
            )
        if len(self.options) > 4:
            raise ValueError(
                "MCQ must have at most 4 options."
            )
        labels = [o.option_label for o in self.options]
        if len(labels) != len(set(labels)):
            raise ValueError(
                "Duplicate option labels found. "
                "Each label (A/B/C/D) must appear at most once."
            )
        correct_count = sum(
            1 for o in self.options if o.is_correct
        )
        if correct_count != 1:
            raise ValueError(
                f"Exactly one option must be marked as correct. "
                f"Found {correct_count}."
            )
        return self


class SubjectiveQuestionCreateRequest(BaseModel):
    """
    Request body for
    POST /api/teacher/exams/{id}/questions/subjective
    """
    question_text: str
    marks:         Decimal
    order_index:   int = 0
    word_limit:    Optional[int] = None

    @field_validator("question_text")
    @classmethod
    def text_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("question_text must not be empty.")
        return v

    @field_validator("marks")
    @classmethod
    def validate_marks(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("marks must be greater than 0.")
        return v

    @field_validator("word_limit")
    @classmethod
    def validate_word_limit(
        cls, v: Optional[int]
    ) -> Optional[int]:
        if v is not None and v < 10:
            raise ValueError(
                "word_limit must be at least 10 if specified."
            )
        return v


class MCQOptionOut(BaseModel):
    """An MCQ option as returned to the client."""
    id:           int
    option_label: str
    option_text:  str
    is_correct:   bool

    model_config = {"from_attributes": True}


class QuestionOut(BaseModel):
    """A question as returned to the client."""
    id:            int
    exam_id:       int
    question_text: str
    question_type: str
    marks:         Decimal
    order_index:   int
    word_limit:    Optional[int] = None
    options:       list[MCQOptionOut] = []

    model_config = {"from_attributes": False}


class ExamPublishRequest(BaseModel):
    """
    Request body for POST /api/teacher/exams/{id}/publish
    No fields required — publishing uses the exam's stored
    start_time/end_time/duration.
    """
    pass

class StudentAnswerOut(BaseModel):
    """
    A student's answer to a single question as shown to the
    teacher in the grading interface.
    """
    answer_id:          int
    question_id:        int
    question_text:      str
    question_type:      str
    marks_available:    Decimal
    word_limit:         Optional[int] = None
    # MCQ fields
    selected_option_id: Optional[int]  = None
    selected_label:     Optional[str]  = None
    selected_text:      Optional[str]  = None
    correct_label:      Optional[str]  = None
    is_correct:         Optional[bool] = None
    # Subjective fields
    subjective_text:    Optional[str]  = None
    # Grade fields (None if not yet graded)
    marks_awarded:      Optional[Decimal] = None
    teacher_feedback:   Optional[str]   = None
    is_graded:          bool = False

    model_config = {"from_attributes": False}


class StudentAttemptSummary(BaseModel):
    """
    Summary of a student's exam attempt shown in the grading
    list view.
    """
    attempt_id:         int
    student_id:         int
    student_email:      str
    student_name:       str
    started_at:         datetime
    submitted_at:       Optional[datetime] = None
    status:             str
    mcq_marks:          Decimal = Decimal("0.0")
    subjective_marks:   Decimal = Decimal("0.0")
    total_marks_awarded: Decimal = Decimal("0.0")
    is_fully_graded:    bool = False
    violation_count:    int  = 0

    model_config = {"from_attributes": False}


class SubjectiveGradeRequest(BaseModel):
    """
    Request body for POST
    /api/teacher/exams/{id}/grade/{attempt_id}/{answer_id}
    """
    marks_awarded: Decimal
    feedback:      Optional[str] = None

    @field_validator("marks_awarded")
    @classmethod
    def validate_marks(cls, v: Decimal) -> Decimal:
        if v < 0:
            raise ValueError("marks_awarded cannot be negative.")
        return v


class GradeBookEntryOut(BaseModel):
    """
    One row in the grade book — one student's result for an exam.
    """
    student_id:              int
    student_email:           str
    student_name:            str
    attempt_id:              Optional[int]   = None
    mcq_marks_awarded:       Decimal = Decimal("0.0")
    subjective_marks_awarded: Decimal = Decimal("0.0")
    negative_marks_deducted: Decimal = Decimal("0.0")
    total_marks_awarded:     Decimal = Decimal("0.0")
    total_marks_available:   Decimal
    percentage:              Decimal = Decimal("0.0")
    is_pass:                 Optional[bool]  = None
    status:                  str
    # status: 'submitted', 'auto_submitted', 'not_attempted',
    #         'in_progress'

    model_config = {"from_attributes": False}


class GradeBookResponse(BaseModel):
    """Complete grade book for an exam."""
    exam_id:              int
    exam_title:           str
    course_code:          str
    total_marks:          Decimal
    passing_marks:        Decimal
    is_published:         bool
    results_published:    bool
    entries:              list[GradeBookEntryOut]
    attempted_count:      int
    not_attempted_count:  int
    pass_count:           int
    fail_count:           int
