"""
utils/email_validator.py
Email pattern validation and role detection for all three user types.

Student  : YYBRHRLN@sch.clg.ac.in   e.g. 22CSE001@se.clg.ac.in
Teacher  : first.last@clg.ac.in     e.g. john.smith@clg.ac.in
Admin    : admin@clg.ac.in          (single fixed address)
"""

import re
from dataclasses import dataclass, field
from typing import Optional

ADMIN_EMAIL = "admin@clg.ac.in"

# Compiled once at import time for performance.
# Student: 2-digit year + 2-4 uppercase branch + 3-digit roll
#          @ 1-5 lowercase school .clg.ac.in
STUDENT_EMAIL_RE = re.compile(
    r'^(?P<batch_year>\d{2})'
    r'(?P<branch_code>[A-Z]{2,4})'
    r'(?P<roll_number>\d{3})'
    r'@(?P<school_code>[a-z]{1,5})'
    r'\.clg\.ac\.in$',
    re.IGNORECASE
)

# Teacher: lowercase first . lowercase last @ clg.ac.in
TEACHER_EMAIL_RE = re.compile(
    r'^(?P<first_name>[a-z]{1,50})'
    r'\.'
    r'(?P<last_name>[a-z]{1,50})'
    r'@clg\.ac\.in$',
    re.IGNORECASE
)


@dataclass
class EmailParseResult:
    """Structured result of parsing and validating an email address."""
    is_valid:    bool
    role:        Optional[str]  = None   # 'admin' | 'teacher' | 'student'
    # Student-only fields
    batch_year:  Optional[str]  = None
    branch_code: Optional[str]  = None
    roll_number: Optional[str]  = None
    school_code: Optional[str]  = None
    # Teacher/Admin fields
    first_name:  Optional[str]  = None
    last_name:   Optional[str]  = None
    # Error
    error:       Optional[str]  = None


def parse_email(email: str) -> EmailParseResult:
    """
    Parses an email and returns an EmailParseResult.

    Priority order: admin → teacher → student.
    If no pattern matches, returns is_valid=False with an error message.
    """
    if not email or not isinstance(email, str):
        return EmailParseResult(is_valid=False,
                                error="Email must be a non-empty string.")

    email = email.strip()

    # ── Admin ──────────────────────────────────────────────────────────────
    if email.lower() == ADMIN_EMAIL:
        return EmailParseResult(
            is_valid=True,
            role="admin",
            first_name="System",
            last_name="Admin",
        )

    # ── Teacher ────────────────────────────────────────────────────────────
    teacher_match = TEACHER_EMAIL_RE.match(email)
    if teacher_match:
        return EmailParseResult(
            is_valid=True,
            role="teacher",
            first_name=teacher_match.group("first_name").capitalize(),
            last_name=teacher_match.group("last_name").capitalize(),
        )

    # ── Student ────────────────────────────────────────────────────────────
    student_match = STUDENT_EMAIL_RE.match(email)
    if student_match:
        return EmailParseResult(
            is_valid=True,
            role="student",
            batch_year=student_match.group("batch_year"),
            branch_code=student_match.group("branch_code").upper(),
            roll_number=student_match.group("roll_number"),
            school_code=student_match.group("school_code").lower(),
        )

    # ── No match ───────────────────────────────────────────────────────────
    return EmailParseResult(
        is_valid=False,
        error=(
            f"'{email}' does not match any recognised email pattern. "
            "Expected formats: "
            "student: YYBRHRLN@sch.clg.ac.in, "
            "teacher: first.last@clg.ac.in, "
            "admin: admin@clg.ac.in"
        ),
    )


def validate_student_email(email: str) -> EmailParseResult:
    """
    Validates that email matches the student pattern exactly.
    Returns an invalid result if the email is valid but belongs to
    a teacher or admin.
    """
    result = parse_email(email)
    if result.is_valid and result.role != "student":
        return EmailParseResult(
            is_valid=False,
            error=f"'{email}' is a {result.role} email, not a student email.",
        )
    return result


def validate_teacher_email(email: str) -> EmailParseResult:
    """
    Validates that email matches the teacher pattern exactly.
    Returns an invalid result if the email is valid but belongs to
    a student or admin.
    """
    result = parse_email(email)
    if result.is_valid and result.role != "teacher":
        return EmailParseResult(
            is_valid=False,
            error=f"'{email}' is a {result.role} email, not a teacher email.",
        )
    return result


def build_student_email(
    batch_year: str,
    branch_code: str,
    roll_number: str,
    school_code: str,
) -> str:
    """
    Constructs a valid student email from its four components.

    - batch_year   must be exactly 2 digits          e.g. "22"
    - branch_code  must be 2-4 alpha chars            e.g. "CSE"
    - roll_number  must be castable to int, 1-999     e.g. "1" or "001"
    - school_code  must be 1-5 alpha chars            e.g. "se"

    roll_number is zero-padded to 3 digits in the output.
    branch_code is uppercased, school_code is lowercased.

    Returns: e.g. "22CSE001@se.clg.ac.in"
    Raises ValueError with a descriptive message on invalid input.
    """
    # Validate batch_year
    batch_year = str(batch_year).strip()
    if not re.fullmatch(r'\d{2}', batch_year):
        raise ValueError(
            f"batch_year must be exactly 2 digits, got '{batch_year}'."
        )

    # Validate and normalise branch_code
    branch_code = str(branch_code).strip().upper()
    if not re.fullmatch(r'[A-Z]{2,4}', branch_code):
        raise ValueError(
            f"branch_code must be 2-4 uppercase alpha chars, got '{branch_code}'."
        )

    # Validate roll_number
    try:
        roll_int = int(roll_number)
    except (ValueError, TypeError):
        raise ValueError(
            f"roll_number must be a number, got '{roll_number}'."
        )
    if not (1 <= roll_int <= 999):
        raise ValueError(
            f"roll_number must be between 1 and 999, got {roll_int}."
        )
    roll_padded = f"{roll_int:03d}"

    # Validate and normalise school_code
    school_code = str(school_code).strip().lower()
    if not re.fullmatch(r'[a-z]{1,5}', school_code):
        raise ValueError(
            f"school_code must be 1-5 lowercase alpha chars, got '{school_code}'."
        )

    email = f"{batch_year}{branch_code}{roll_padded}@{school_code}.clg.ac.in"
    return email


def build_teacher_email(first_name: str, last_name: str) -> str:
    """
    Constructs a valid teacher email from first and last name.

    Both names are stripped and lowercased.
    Only alphabetic characters are permitted in each name.

    Returns: e.g. "john.smith@clg.ac.in"
    Raises ValueError with a descriptive message on invalid input.
    """
    first = str(first_name).strip().lower()
    last  = str(last_name).strip().lower()

    if not first:
        raise ValueError("first_name cannot be empty.")
    if not last:
        raise ValueError("last_name cannot be empty.")
    if not first.isalpha():
        raise ValueError(
            f"first_name must contain only letters, got '{first_name}'."
        )
    if not last.isalpha():
        raise ValueError(
            f"last_name must contain only letters, got '{last_name}'."
        )

    return f"{first}.{last}@clg.ac.in"
