"""
app/core/dependencies.py

All FastAPI Depends() callables live here — single source of truth for
request-scoped injection (DB pool, authenticated user, etc.).
"""
import asyncpg
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError

from app.core.security import decode_access_token

# Clean Bearer auth scheme for Swagger UI — prompts directly for JWT token
_security_scheme = HTTPBearer()


async def get_pool(request: Request) -> asyncpg.Pool:
    """Inject the asyncpg pool from app.state into any endpoint."""
    return request.app.state.db_pool


async def get_current_user(
    auth: HTTPAuthorizationCredentials = Depends(_security_scheme),
) -> dict:
    """
    Decode the JWT, extract identity, and return user dict.
    Used as: current_user: dict = Depends(get_current_user)
    """
    token = auth.credentials
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_access_token(token)
        sub = payload.get("sub")
        if not sub or not isinstance(sub, str):
            raise credentials_exception
        user_id = sub
    except JWTError:
        raise credentials_exception

    # Return a lightweight dict — avoids a DB round-trip on every request.
    return {"id": user_id, "email": payload.get("email")}
