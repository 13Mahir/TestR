"""
services/log_service.py
Helper functions for writing to system_logs and audit_logs tables.
Both tables are append-only — no updates or deletes ever occur here.

Called by routers and other services whenever a loggable event occurs.
These functions never raise — errors are swallowed so a logging
failure never blocks a user-facing operation.
"""

from typing import Optional, Any
from sqlalchemy.ext.asyncio import AsyncSession

from models import SystemLog, AuditLog, SystemLogEventType


async def write_system_log(
    db: AsyncSession,
    event_type: SystemLogEventType,
    actor_id: int,
    description: str,
    metadata: Optional[dict] = None,
) -> None:
    """
    Appends a row to system_logs.

    Args:
        event_type:  One of the SystemLogEventType enum values.
        actor_id:    PK of the user who triggered the event.
        description: Human-readable summary shown in the admin logs page.
        metadata:    Optional dict stored as JSON for extra context.
                     e.g. {"exam_id": 12, "course_id": 3}
                     e.g. {"count": 60, "batch": "22", "branch": "CSE"}

    Never raises — errors are caught and silently ignored.
    Does NOT commit — caller commits via get_db() transaction.
    """
    try:
        log = SystemLog(
            event_type=event_type,
            actor_id=actor_id,
            description=description,
            metadata=metadata,
        )
        db.add(log)
        await db.flush()
    except Exception:
        pass


async def write_audit_log(
    db: AsyncSession,
    admin_id: int,
    action: str,
    target_type: str,
    ip_address: str,
    target_id: Optional[Any] = None,
    details: Optional[dict] = None,
) -> None:
    """
    Appends a row to audit_logs.

    Args:
        admin_id:    PK of the admin who performed the action.
        action:      UPPER_SNAKE_CASE action name.
                     e.g. "CREATE_USER", "BULK_CREATE_STUDENTS",
                          "DEACTIVATE_USER", "FORCE_PASSWORD_RESET"
        target_type: "user", "course", "exam", "enrollment", "assignment"
        ip_address:  Client IP from the request.
        target_id:   PK of the affected record (stored as string).
                     Can be None for bulk operations with no single target.
        details:     Full context dict stored as JSON.
                     e.g. {"email": "22CSE001@se.clg.ac.in",
                            "batch": "22", "branch": "CSE"}

    Never raises — errors are caught and silently ignored.
    Does NOT commit — caller commits via get_db() transaction.
    """
    try:
        log = AuditLog(
            admin_id=admin_id,
            action=action,
            target_type=target_type,
            target_id=str(target_id) if target_id is not None else None,
            details=details,
            ip_address=ip_address,
        )
        db.add(log)
        await db.flush()
    except Exception:
        pass

from sqlalchemy import select, func, or_
from models import SystemLog, AuditLog, SystemLogEventType
from typing import Optional

async def list_system_logs(
    db: AsyncSession,
    event_type: Optional[str] = None,
    actor_id:   Optional[int] = None,
    limit:      int = 20,
    offset:     int = 0,
) -> tuple[list[SystemLog], int]:
    """
    Returns paginated system logs, newest first.

    Filters:
        event_type: Filter by SystemLogEventType value string
        actor_id:   Filter by the user who triggered the event

    Returns:
        (logs_list, total_count)
    """
    base_query  = select(SystemLog)
    count_query = select(func.count(SystemLog.id))

    if event_type:
        base_query  = base_query.where(
            SystemLog.event_type == event_type
        )
        count_query = count_query.where(
            SystemLog.event_type == event_type
        )

    if actor_id is not None:
        base_query  = base_query.where(SystemLog.actor_id == actor_id)
        count_query = count_query.where(SystemLog.actor_id == actor_id)

    total_result = await db.execute(count_query)
    total = total_result.scalar_one()

    logs_result = await db.execute(
        base_query
        .order_by(SystemLog.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    logs = list(logs_result.scalars().all())

    return logs, total


async def list_audit_logs(
    db: AsyncSession,
    action:      Optional[str] = None,
    admin_id:    Optional[int] = None,
    target_type: Optional[str] = None,
    limit:       int = 20,
    offset:      int = 0,
) -> tuple[list[AuditLog], int]:
    """
    Returns paginated audit logs, newest first.

    Filters:
        action:      Filter by action string e.g. 'CREATE_USER'
        admin_id:    Filter by admin who performed the action
        target_type: Filter by target type e.g. 'user', 'course'

    Returns:
        (logs_list, total_count)
    """
    base_query  = select(AuditLog)
    count_query = select(func.count(AuditLog.id))

    if action:
        base_query  = base_query.where(AuditLog.action == action)
        count_query = count_query.where(AuditLog.action == action)

    if admin_id is not None:
        base_query  = base_query.where(AuditLog.admin_id == admin_id)
        count_query = count_query.where(AuditLog.admin_id == admin_id)

    if target_type:
        base_query  = base_query.where(
            AuditLog.target_type == target_type
        )
        count_query = count_query.where(
            AuditLog.target_type == target_type
        )

    total_result = await db.execute(count_query)
    total = total_result.scalar_one()

    logs_result = await db.execute(
        base_query
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    logs = list(logs_result.scalars().all())

    return logs, total


async def export_audit_logs_csv(
    db: AsyncSession,
    action:      Optional[str] = None,
    admin_id:    Optional[int] = None,
    target_type: Optional[str] = None,
) -> str:
    """
    Exports ALL matching audit logs as a CSV string (no pagination).
    Used by the admin CSV export endpoint.

    Returns a UTF-8 CSV string with headers:
        id, admin_id, action, target_type, target_id,
        details, ip_address, created_at

    The details JSON column is serialised as a compact JSON string
    in the CSV cell.
    """
    import csv
    import io
    import json

    # Fetch all matching logs — no limit for export
    base_query = select(AuditLog)

    if action:
        base_query = base_query.where(AuditLog.action == action)
    if admin_id is not None:
        base_query = base_query.where(AuditLog.admin_id == admin_id)
    if target_type:
        base_query = base_query.where(
            AuditLog.target_type == target_type
        )

    result = await db.execute(
        base_query.order_by(AuditLog.created_at.desc())
    )
    logs = list(result.scalars().all())

    # Build CSV in memory
    output = io.StringIO()
    writer = csv.writer(output, quoting=csv.QUOTE_ALL)

    # Header row
    writer.writerow([
        "id", "admin_id", "action", "target_type", "target_id",
        "details", "ip_address", "created_at",
    ])

    # Data rows
    for log in logs:
        writer.writerow([
            log.id,
            log.admin_id,
            log.action,
            log.target_type,
            log.target_id or "",
            json.dumps(log.details) if log.details else "",
            log.ip_address,
            log.created_at.isoformat(),
        ])

    return output.getvalue()
