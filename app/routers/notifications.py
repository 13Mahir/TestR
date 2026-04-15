"""
routers/notifications.py
Notification endpoints for the in-app bell icon system.
All routes prefixed with /api/notifications in main.py.

Notifications are READ-ONLY from the client's perspective.
Creation happens server-side only via notification_service.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.dependencies import get_current_user
from models import User
from schemas.notification import (
    NotificationOut,
    NotificationListResponse,
    MarkReadResponse,
)
from services.notification_service import (
    get_notifications_for_user,
    get_unread_count,
    mark_notifications_read,
    delete_notification,
)

router = APIRouter(tags=["notifications"])


@router.get("/", response_model=NotificationListResponse)
async def list_notifications(
    unread_only: bool = False,
    page: int = Query(1, ge=1),
    per_page: int = Query(15, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Returns paginated notifications for the current user."""
    offset = (page - 1) * per_page
    notifications, total, unread_count = await get_notifications_for_user(
        db=db,
        user_id=current_user.id,
        unread_only=unread_only,
        limit=per_page,
        offset=offset,
    )

    import math
    pages = math.ceil(total / per_page) if total > 0 else 1

    return NotificationListResponse(
        unread_count=unread_count,
        total=total,
        page=page,
        per_page=per_page,
        pages=pages,
        notifications=[NotificationOut.model_validate(n) for n in notifications],
    )


@router.patch("/{notification_id}/read", response_model=MarkReadResponse)
async def mark_one_as_read(
    notification_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Marks a single notification as read."""
    await mark_notifications_read(
        db=db,
        user_id=current_user.id,
        notification_ids=[notification_id],
    )
    
    await db.commit()
    return MarkReadResponse(message="Marked as read.")


@router.patch("/read-all", response_model=MarkReadResponse)
async def mark_all_as_read(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Marks all unread notifications as read."""
    updated = await mark_notifications_read(
        db=db,
        user_id=current_user.id,
        notification_ids=[],
    )
    await db.commit()
    return MarkReadResponse(message="All notifications marked as read.", updated=updated)


@router.delete("/{notification_id}")
async def delete_one_notification(
    notification_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Hard delete a specific notification."""
    await delete_notification(
        db=db,
        user_id=current_user.id,
        notification_id=notification_id,
    )
    
    await db.commit()
    return {"message": "Notification deleted."}


@router.get("/unread-count")
async def get_unread_count_only(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Lightweight endpoint for polling."""
    count = await get_unread_count(db=db, user_id=current_user.id)
    return {"unread_count": count}
