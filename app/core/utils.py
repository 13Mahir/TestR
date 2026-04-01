"""
core/utils.py
Utility functions for the TestR.
"""
from datetime import datetime, timezone
from typing import Optional

def ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """
    Attaches timezone.utc to a naive datetime object.
    If the datetime is already aware, returns it as is.
    If None, returns None.
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt
