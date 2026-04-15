"""
core/exceptions.py
Custom application exceptions for centralized error handling.
"""

class AppException(Exception):
    """Base exception for all application errors."""
    def __init__(self, message: str, details: dict = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}

class NotFoundException(AppException):
    """Resource not found (HTTP 404)."""
    pass

class ForbiddenException(AppException):
    """Action not allowed for current user (HTTP 403)."""
    pass

class UnauthorizedException(AppException):
    """Authentication required or failed (HTTP 401)."""
    pass

class ValidationException(AppException):
    """Input validation failed or business rule violation (HTTP 400)."""
    pass

class ConflictException(AppException):
    """Resource already exists or state conflict (HTTP 409)."""
    pass

class SystemException(AppException):
    """Internal system error (HTTP 500)."""
    pass
