"""
schemas/notification.py
Pydantic schemas for the notification system endpoints.
"""

from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class NotificationOut(BaseModel):
    """A single notification as returned to the client."""
    id:         int
    type:       str
    title:      str
    body:       str
    link:       Optional[str]
    is_read:    bool
    created_at: datetime

    model_config = {"from_attributes": True}


class NotificationListResponse(BaseModel):
    """Response for GET /api/notifications/ — paginated list."""
    unread_count:  int
    total:         int
    page:          int
    per_page:      int
    pages:         int
    notifications: list[NotificationOut]


class MarkReadResponse(BaseModel):
    """Response for marking notifications as read."""
    message: str
    updated: Optional[int] = None
