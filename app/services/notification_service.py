"""
services/notification_service.py
Business logic for creating, listing, and marking notifications.

Notifications are created SERVER-SIDE ONLY by other services
(exam published, results published, user created, etc.).
The client only reads and marks them as read.
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, func, update, and_
from sqlalchemy.ext.asyncio import AsyncSession

from models import Notification


async def create_notification(
    db: AsyncSession,
    user_id: int,
    type: str,
    title: str,
    body: str,
    link: Optional[str] = None,
) -> Notification:
    """Creates a single in-app notification for one user."""
    notification = Notification(
        user_id=user_id,
        type=type,
        title=title,
        body=body,
        link=link,
        is_read=False,
    )
    db.add(notification)
    await db.flush()
    return notification


async def create_notifications_bulk(
    db: AsyncSession,
    user_ids: list[int],
    type: str,
    title: str,
    body: str,
    link: Optional[str] = None,
) -> int:
    """Creates the same notification for multiple users in bulk."""
    if not user_ids:
        return 0
    notifications = [
        Notification(
            user_id=uid,
            type=type,
            title=title,
            body=body,
            link=link,
            is_read=False,
        )
        for uid in user_ids
    ]
    db.add_all(notifications)
    await db.flush()
    return len(notifications)


async def get_notifications_for_user(
    db: AsyncSession,
    user_id: int,
    unread_only: bool = False,
    limit: int = 15,
    offset: int = 0,
) -> tuple[list[Notification], int, int]:
    """
    Fetches paginated notifications for a user, newest first.
    Returns: (notifications, total_count, unread_count)
    """
    stmt = select(Notification).where(Notification.user_id == user_id)
    if unread_only:
        stmt = stmt.where(Notification.is_read == False)
    
    # Paginated notifications
    result = await db.execute(
        stmt.order_by(Notification.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    notifications = list(result.scalars().all())

    # Total count (based on the same filter)
    total_stmt = select(func.count(Notification.id)).where(Notification.user_id == user_id)
    if unread_only:
        total_stmt = total_stmt.where(Notification.is_read == False)
    total_result = await db.execute(total_stmt)
    total = total_result.scalar_one()

    # Unread count (always for the bell)
    unread_result = await db.execute(
        select(func.count(Notification.id))
        .where(Notification.user_id == user_id)
        .where(Notification.is_read == False)
    )
    unread_count = unread_result.scalar_one()

    return notifications, total, unread_count


async def get_unread_count(
    db: AsyncSession,
    user_id: int,
) -> int:
    """
    Returns just the unread notification count for a user.
    Called by the polling endpoint to minimise payload size.
    """
    result = await db.execute(
        select(func.count(Notification.id))
        .where(
            and_(
                Notification.user_id == user_id,
                Notification.is_read == False,
            )
        )
    )
    return result.scalar_one()


async def mark_notifications_read(
    db: AsyncSession,
    user_id: int,
    notification_ids: list[int],
) -> int:
    """
    Marks specific notifications as read for the given user.
    If notification_ids is empty, marks ALL notifications as read.

    The user_id check ensures users cannot mark other users'
    notifications as read (IDOR prevention).

    Returns the count of rows updated.
    Does NOT commit — caller commits.
    """
    query = (
        update(Notification)
        .where(Notification.user_id == user_id)
        .where(Notification.is_read == False)
    )

    if notification_ids:
        query = query.where(Notification.id.in_(notification_ids))

    result = await db.execute(query.values(is_read=True))
    await db.flush()
    return result.rowcount


async def delete_notification(
    db: AsyncSession,
    user_id: int,
    notification_id: int,
) -> bool:
    """
    Deletes a single notification belonging to user_id.
    Returns True if deleted, False if not found or not owned by user.
    Does NOT commit — caller commits.
    """
    result = await db.execute(
        select(Notification).where(
            and_(
                Notification.id == notification_id,
                Notification.user_id == user_id,
            )
        )
    )
    notification = result.scalar_one_or_none()
    if notification is None:
        return False
    await db.delete(notification)
    await db.flush()
    return True
