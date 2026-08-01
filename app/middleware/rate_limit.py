"""
app/middleware/rate_limit.py

Per-user rate limiting via slowapi.
The limiter key is derived from the JWT sub (user UUID) when a
valid Bearer token is present, falling back to the client IP.

Usage in main.py:
    from app.middleware.rate_limit import limiter, rate_limit_handler
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_handler)

Usage on an endpoint:
    @app.post("/api/v1/chat")
    @limiter.limit("20/minute")
    async def chat(request: Request, ...):
        ...
"""
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from fastapi import Request, Response
from fastapi.responses import JSONResponse

from app.auth.security import decode_access_token


def _get_user_or_ip(request: Request) -> str:
    """
    Rate-limit key function.
    - If a valid Bearer JWT is present, use the user UUID as key
      (limits are per-user, not per-IP, so VPN/proxy hopping doesn't help).
    - Otherwise fall back to the client IP.
    """
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header.split(" ", 1)[1]
        try:
            payload = decode_access_token(token)
            user_id = payload.get("sub")
            if user_id:
                return f"user:{user_id}"
        except Exception:
            pass  # Invalid token — fall through to IP
    return get_remote_address(request)


# Singleton limiter — imported and attached to app in main.py
limiter = Limiter(key_func=_get_user_or_ip)


def rate_limit_handler(request: Request, exc: RateLimitExceeded) -> Response:
    """Return a clean JSON 429 instead of the default plain-text one."""
    return JSONResponse(
        status_code=429,
        content={
            "detail": "You're sending messages too quickly. Please wait a moment and try again.",
        },
    )
