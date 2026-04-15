"""
schemas/student.py
Pydantic schemas for student panel endpoints.
"""

from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from decimal import Decimal


class EnrolledCourseOut(BaseModel):
    id:                int
    course_code:       str
    name:              str
    description:       Optional[str] = None
    branch_code:       str
    year:              str
    mode:              str
    is_active:         bool
    enrolled_at:       datetime
    upcoming_exams:    int = 0
    completed_exams:   int = 0

    model_config = {"from_attributes": False}


class UpcomingExamOut(BaseModel):
    id:               int
    course_id:        int
    course_code:      str
    title:            str
    duration_minutes: int
    start_time:       datetime
    end_time:         datetime
    total_marks:      Decimal
    passing_marks:    Decimal
    has_attempted:    bool = False

    model_config = {"from_attributes": False}


class RecentResultOut(BaseModel):
    exam_id:          int
    exam_title:       str
    course_code:      str
    total_marks_awarded:   Decimal
    total_marks_available: Decimal
    percentage:       Decimal
    is_pass:          Optional[bool] = None
    results_published_at: Optional[datetime] = None

    model_config = {"from_attributes": False}


class SubjectPerformanceOut(BaseModel):
    course_code:     str
    course_name:     str
    exams_attempted: int
    average_score:   Decimal
    average_pct:     Decimal
    pass_count:      int
    fail_count:      int

    model_config = {"from_attributes": False}


class TranscriptEntryOut(BaseModel):
    course_code:     str
    course_name:     str
    exam_title:      str
    total_marks_awarded:   Decimal
    total_marks_available: Decimal
    percentage:      Decimal
    is_pass:         Optional[bool] = None
    submitted_at:    Optional[datetime] = None
    results_published_at: Optional[datetime] = None

    model_config = {"from_attributes": False}


class ExamLobbyOut(BaseModel):
    exam_id:          int
    title:            str
    course_code:      str
    duration_minutes: int
    total_marks:      Decimal
    passing_marks:    Decimal
    negative_marking_factor: Decimal
    start_time:       datetime
    end_time:         datetime
    question_count:   int
    can_attempt:      bool
    reason:           Optional[str] = None
    # reason: why can_attempt is False
    # e.g. "Exam starts in 12 minutes"
    #      "Already attempted"
    #      "Exam window has closed"
    minutes_until_start: Optional[Decimal] = None

    model_config = {"from_attributes": False}
