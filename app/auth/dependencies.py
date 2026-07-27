"""
app/auth/dependencies.py

FastAPI dependency: get_current_user
Validates the Bearer JWT on every protected route and returns the
decoded user dict so handlers never have to touch token logic.
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError

from app.auth.security import decode_access_token

# Clean Bearer auth scheme for Swagger UI — prompts directly for JWT token
_security_scheme = HTTPBearer()


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
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    # Return a lightweight dict — avoids a DB round-trip on every request.
    return {"id": user_id, "email": payload.get("email")}

