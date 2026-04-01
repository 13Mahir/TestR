from app.core.database import get_db_cursor

def notify(user_id: int, type: str, title: str, body: str, link: str = None):
    """Send a single in-app notification to one user."""
    with get_db_cursor(commit=True) as cursor:
        cursor.execute(
            """INSERT INTO notifications (user_id, type, title, body, link)
               VALUES (%s, %s, %s, %s, %s)""",
            (user_id, type, title, body, link)
        )

def notify_many(user_ids: list[int], type: str, title: str,
                body: str, link: str = None):
    """Send the same notification to multiple users efficiently."""
    if not user_ids:
        return
    with get_db_cursor(commit=True) as cursor:
        cursor.executemany(
            """INSERT INTO notifications (user_id, type, title, body, link)
               VALUES (%s, %s, %s, %s, %s)""",
            [(uid, type, title, body, link) for uid in user_ids]
        )
