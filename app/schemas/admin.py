"""
schemas/admin.py
Pydantic request and response schemas for all admin API endpoints.
User management, course management, logs, and password reset schemas
all live here.
"""

from pydantic import BaseModel, field_validator, model_validator
from typing import Optional
from datetime import datetime


# ── User schemas ──────────────────────────────────────────────────────────────

class SingleUserCreateRequest(BaseModel):
    """
    Request body for POST /api/admin/users/single
    Admin provides email — role and name are derived from email pattern.
    """
    email:    str
    password: str

    @field_validator("email")
    @classmethod
    def validate_and_normalise_email(cls, v: str) -> str:
        import re
        v = v.strip().lower()
        
        student_pattern = r'^[0-9]{2}[a-z]{3}[0-9]{3}@[a-z]+\.clg\.ac\.in$'
        faculty_pattern = r'^[a-z]+\.[a-z]+@clg\.ac\.in$'
        admin_pattern = r'^admin@clg\.ac\.in$'
        
        if not (re.fullmatch(student_pattern, v) or 
                re.fullmatch(faculty_pattern, v) or 
                re.fullmatch(admin_pattern, v)):
            raise ValueError(
                "Invalid email format. Allowed formats: "
                "YYBRNRNN@sch.clg.ac.in (students), "
                "firstname.lastname@clg.ac.in (faculty), "
                "or admin@clg.ac.in"
            )
        return v

    @field_validator("password")
    @classmethod
    def password_min_length(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters.")
        return v


class BulkStudentCreateRequest(BaseModel):
    """
    Request body for POST /api/admin/users/bulk-students
    Creates all students for a given batch + branch + roll range.
    All three parameters are required together.
    """
    batch_year:      str   # e.g. "22"
    branch_code:     str   # e.g. "CSE"
    roll_start:      int   # e.g. 1
    roll_end:        int   # e.g. 60
    default_password: str  # Same password for all created students

    @field_validator("batch_year")
    @classmethod
    def validate_batch_year(cls, v: str) -> str:
        import re
        v = v.strip()
        if not re.fullmatch(r'\d{2}', v):
            raise ValueError("batch_year must be exactly 2 digits e.g. '22'.")
        return v

    @field_validator("branch_code")
    @classmethod
    def normalise_branch_code(cls, v: str) -> str:
        import re
        v = v.strip().upper()
        if not re.fullmatch(r'[A-Za-z]{3}', v):
            raise ValueError("branch_code must be exactly 3 letters (e.g. 'CSE').")
        return v

    @field_validator("default_password")
    @classmethod
    def password_min_length(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Default password must be at least 8 characters.")
        return v

    @model_validator(mode="after")
    def validate_roll_range(self) -> "BulkStudentCreateRequest":
        if self.roll_start < 1:
            raise ValueError("roll_start must be at least 1.")
        if self.roll_end > 999:
            raise ValueError("roll_end must not exceed 999.")
        if self.roll_start > self.roll_end:
            raise ValueError(
                "roll_start must be less than or equal to roll_end."
            )
        if (self.roll_end - self.roll_start + 1) > 300:
            raise ValueError(
                "Cannot create more than 300 students in a single bulk "
                "operation."
            )
        return self


class BulkTeacherCreateRequest(BaseModel):
    """
    Request body metadata for POST /api/admin/users/bulk-teachers
    The actual CSV file is sent as a multipart upload.
    This schema validates the non-file fields of the form.
    """
    default_password: str

    @field_validator("default_password")
    @classmethod
    def password_min_length(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Default password must be at least 8 characters.")
        return v


class BulkDeactivateRequest(BaseModel):
    """
    Request body for POST /api/admin/users/bulk-deactivate
    Deactivates all students in a given batch year + branch.
    Used at year-end to retire a graduating batch.
    """
    batch_year:  str   # e.g. "22"
    branch_code: Optional[str] = None
    # If branch_code is None → deactivate entire batch across all branches
    # If branch_code given  → deactivate only that branch of the batch

    @field_validator("batch_year")
    @classmethod
    def validate_batch_year(cls, v: str) -> str:
        import re
        v = v.strip()
        if not re.fullmatch(r'\d{2}', v):
            raise ValueError("batch_year must be exactly 2 digits.")
        return v


class UserOut(BaseModel):
    """A user record as returned in list/detail responses."""
    id:                   int
    email:                str
    role:                 str
    first_name:           str
    last_name:            str
    full_name:            str
    is_active:            bool
    force_password_reset: bool
    created_at:           datetime

    model_config = {"from_attributes": True}


class UserListResponse(BaseModel):
    """Paginated user list response."""
    items:      list[UserOut]
    total:      int
    page:       int
    page_size:  int
    total_pages: int
    has_next:   bool
    has_prev:   bool


class BulkCreateResult(BaseModel):
    """
    Summary response for any bulk creation operation.
    Reports successes, skips (already existing), and failures.
    """
    created:  int
    skipped:  int   # emails that already existed
    failed:   int   # emails that failed for other reasons
    errors:   list[str]  # human-readable descriptions of failures
    message:  str


class BulkDeactivateResult(BaseModel):
    """Summary response for bulk deactivation."""
    deactivated: int
    message:     str


class BulkActivateResult(BaseModel):
    """Summary response for bulk activation."""
    activated: int
    message:   str


class PasswordResetTokenOut(BaseModel):
    """Response for force-password-reset token generation."""
    user_id:    int
    user_email: str
    token:      str
    expires_at: datetime
    message:    str

class ResetPasswordRequest(BaseModel):
    """Request body for applying a password reset token."""
    token:        str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def password_min_length(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters.")
        return v

from pydantic import BaseModel, EmailStr, Field

class SystemLogOut(BaseModel):
    """A single system log entry as returned to the client."""
    id:          int
    event_type:  str
    actor_id:    int
    description: str
    metadata:    Optional[dict] = Field(None, validation_alias="log_metadata")
    created_at:  datetime

    model_config = {"from_attributes": True}


class SystemLogListResponse(BaseModel):
    """Paginated system log list response."""
    items:       list[SystemLogOut]
    total:       int
    page:        int
    page_size:   int
    total_pages: int
    has_next:    bool
    has_prev:    bool


class AuditLogOut(BaseModel):
    """A single audit log entry as returned to the client."""
    id:          int
    admin_id:    int
    action:      str
    target_type: str
    target_id:   Optional[str] = None
    details:     Optional[dict] = None
    ip_address:  str
    created_at:  datetime

    model_config = {"from_attributes": True}


class AuditLogListResponse(BaseModel):
    """Paginated audit log list response."""
    items:       list[AuditLogOut]
    total:       int
    page:        int
    page_size:   int
    total_pages: int
    has_next:    bool
    has_prev:    bool


class CourseCreateRequest(BaseModel):
    """Request body for POST /api/admin/courses"""
    course_code: str
    name:        str
    description: Optional[str] = None
    branch_code: str   # e.g. "CSE" — looked up to get branch_id
    year:        str   # e.g. "22"
    mode:        str   # "T" or "P"

    @field_validator("course_code")
    @classmethod
    def normalise_course_code(cls, v: str) -> str:
        import re
        v = v.strip().upper()
        if not re.fullmatch(r'[0-9]{2}[A-Z]{2}[0-9]{3}[TP]', v):
            raise ValueError(
                "course_code must match format YYBRNNNM "
                "e.g. '22CS101T'. "
                "YY=year, BR=2-char branch, NNN=3-digit number, "
                "M=T(Theory) or P(Practical)."
            )
        return v

    @field_validator("mode")
    @classmethod
    def validate_mode(cls, v: str) -> str:
        v = v.strip().upper()
        if v not in ("T", "P"):
            raise ValueError("mode must be 'T' (Theory) or 'P' (Practical).")
        return v

    @field_validator("year")
    @classmethod
    def validate_year(cls, v: str) -> str:
        import re
        v = v.strip()
        if not re.fullmatch(r'\d{2}', v):
            raise ValueError("year must be exactly 2 digits e.g. '22'.")
        return v

    @field_validator("branch_code")
    @classmethod
    def normalise_branch_code(cls, v: str) -> str:
        return v.strip().upper()

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("name must not be empty.")
        return v


class CourseOut(BaseModel):
    """A course record as returned to the client."""
    id:          int
    course_code: str
    name:        str
    description: Optional[str] = None
    branch_code: str   # resolved from branch relationship
    year:        str
    mode:        str
    is_active:   bool
    created_at:  datetime
    # Counts — populated by service layer
    enrolled_students: int = 0
    assigned_teachers: int = 0

    model_config = {"from_attributes": False}
    # from_attributes=False because branch_code is not a direct
    # column — it is resolved in the service layer


class CourseListResponse(BaseModel):
    """Paginated course list response."""
    items:       list[CourseOut]
    total:       int
    page:        int
    page_size:   int
    total_pages: int
    has_next:    bool
    has_prev:    bool


class EnrollSingleRequest(BaseModel):
    """Request body for POST /api/admin/courses/{id}/enroll/single"""
    student_email: str

    @field_validator("student_email")
    @classmethod
    def normalise(cls, v: str) -> str:
        return v.strip().lower()


class EnrollBulkRequest(BaseModel):
    """
    Request body for POST /api/admin/courses/{id}/enroll/bulk
    Enrolls all students in a batch+branch+roll range into the course.
    All three parameters are required together.
    """
    batch_year:  str
    branch_code: str
    roll_start:  int
    roll_end:    int

    @field_validator("batch_year")
    @classmethod
    def validate_batch_year(cls, v: str) -> str:
        import re
        v = v.strip()
        if not re.fullmatch(r'\d{2}', v):
            raise ValueError("batch_year must be exactly 2 digits.")
        return v

    @field_validator("branch_code")
    @classmethod
    def normalise_branch_code(cls, v: str) -> str:
        return v.strip().upper()

    @model_validator(mode="after")
    def validate_roll_range(self) -> "EnrollBulkRequest":
        if self.roll_start < 1:
            raise ValueError("roll_start must be at least 1.")
        if self.roll_end > 999:
            raise ValueError("roll_end must not exceed 999.")
        if self.roll_start > self.roll_end:
            raise ValueError("roll_start must be <= roll_end.")
        if (self.roll_end - self.roll_start + 1) > 300:
            raise ValueError(
                "Cannot enroll more than 300 students in a single "
                "bulk operation."
            )
        return self


class AssignSingleRequest(BaseModel):
    """Request body for POST /api/admin/courses/{id}/assign/single"""
    teacher_email: str

    @field_validator("teacher_email")
    @classmethod
    def normalise(cls, v: str) -> str:
        return v.strip().lower()


class EnrollmentOut(BaseModel):
    """Summary of an enrollment/assignment operation."""
    enrolled:  int = 0
    unenrolled: int = 0
    assigned:  int = 0
    unassigned: int = 0
    skipped:   int = 0
    failed:    int = 0
    errors:    list[str] = []
    message:   str


class BranchOut(BaseModel):
    id:          int
    code:        str
    name:        str
    school_id:   int

    model_config = {"from_attributes": True}


class SchoolWithBranchesOut(BaseModel):
    id:          int
    code:        str
    name:        str
    branches:    list[BranchOut] = []

    model_config = {"from_attributes": True}

class SchoolCreateRequest(BaseModel):
    """Request body for POST /api/admin/schools"""
    code: str
    name: str

    @field_validator("code")
    @classmethod
    def normalise_code(cls, v: str) -> str:
        return v.strip().lower()

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("name must not be empty.")
        return v

class BranchCreateRequest(BaseModel):
    """Request body for POST /api/admin/branches"""
    school_id: int
    code:      str
    name:      str

    @field_validator("code")
    @classmethod
    def normalise_code(cls, v: str) -> str:
        return v.strip().upper()

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("name must not be empty.")
        return v


