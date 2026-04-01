"""
schemas/auth.py
Pydantic request and response schemas for all auth endpoints.
"""

from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional


class LoginRequest(BaseModel):
    """Request body for POST /api/auth/login"""
    email:    str
    password: str

    @field_validator("email")
    @classmethod
    def email_must_not_be_empty(cls, v: str) -> str:
        v = v.strip().lower()
        if not v:
            raise ValueError("Email must not be empty.")
        return v

    @field_validator("password")
    @classmethod
    def password_must_not_be_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Password must not be empty.")
        return v


class LoginResponse(BaseModel):
    """Response body for successful POST /api/auth/login"""
    message:              str
    role:                 str
    email:                str
    full_name:            str
    force_password_reset: bool


class MeResponse(BaseModel):
    """Response body for GET /api/auth/me"""
    id:                   int
    email:                str
    role:                 str
    first_name:           str
    last_name:            str
    full_name:            str
    is_active:            bool
    force_password_reset: bool

    model_config = {"from_attributes": True}


class ChangePasswordRequest(BaseModel):
    """Request body for POST /api/auth/change-password"""
    current_password: str
    new_password:     str

    @field_validator("new_password")
    @classmethod
    def new_password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("New password must be at least 8 characters.")
        return v


class RefreshResponse(BaseModel):
    """Response body for POST /api/auth/refresh"""
    message: str


class MessageResponse(BaseModel):
    """Generic message-only response."""
    message: str
