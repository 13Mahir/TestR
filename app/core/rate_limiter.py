"""
core/rate_limiter.py
Simplified in-memory rate limiter for brute-force protection.
Stores attempts in a global dictionary keyed by IP + action.
"""
import time
from typing import Dict, Tuple
from fastapi import Request, HTTPException, status

# Global storage: { "ip:action": (count, reset_time) }
_rate_limit_db: Dict[str, Tuple[int, float]] = {}

def rate_limit(limit: int, window_seconds: int, action: str = "default"):
    """
    Decorator-like function to enforce rate limits per IP.
    Usage:
        await rate_limit(limit=5, window_seconds=60, action="login")(request)
    """
    async def decorator(request: Request):
        # Extract IP (handling proxies)
        forwarded_for = request.headers.get("X-Forwarded-For")
        ip = forwarded_for.split(",")[0].strip() if forwarded_for else request.client.host
        
        key = f"{ip}:{action}"
        now = time.time()
        
        # Cleanup expired entries occasionally or on access
        count, reset_time = _rate_limit_db.get(key, (0, now + window_seconds))
        
        if now > reset_time:
            # Window expired, reset
            count = 1
            reset_time = now + window_seconds
        else:
            count += 1
            
        _rate_limit_db[key] = (count, reset_time)
        
        if count > limit:
            retry_after = int(reset_time - now)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Too many requests. Please try again in {retry_after} seconds.",
                headers={"Retry-After": str(retry_after)}
            )
            
    return decorator
