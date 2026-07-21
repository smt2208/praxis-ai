"""
app/auth/security.py

Pure utility functions for password hashing and JWT token lifecycle.
No FastAPI dependencies here — importable anywhere without side effects.

Token strategy:
  - Access token  → short-lived JWT (30 min), carries user identity in payload.
  - Refresh token → long-lived opaque string (secrets.token_urlsafe), stored in DB.
    Using an opaque token (not JWT) for refresh means we can revoke it instantly
    by deleting the DB row — no need to wait for expiry.
"""
import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
from jose import JWTError, jwt

from app.config import get_settings

settings = get_settings()


# --- Password helpers --------------------------------------------------

def hash_password(plain: str) -> str:
    """Return a bcrypt hash of the plain-text password."""
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(plain.encode('utf-8'), salt)
    return hashed.decode('utf-8')


def verify_password(plain: str, hashed: str) -> bool:
    """Return True if *plain* matches the stored bcrypt *hashed* value."""
    try:
        return bcrypt.checkpw(plain.encode('utf-8'), hashed.encode('utf-8'))
    except (ValueError, TypeError):
        return False


# --- Access token (JWT) -----------------------------------------------

def create_access_token(user_id: str, email: str) -> str:
    """
    Mint a short-lived signed JWT.

    Payload fields:
      sub   → user UUID (standard JWT subject claim)
      email → user email (convenience; avoids a DB lookup on every request)
      type  → "access" (guards against accidentally accepting a refresh JWT)
      exp   → expiry timestamp
    """
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.access_token_expire_minutes
    )
    payload = {
        "sub": user_id,
        "email": email,
        "type": "access",
        "exp": expire,
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def decode_access_token(token: str) -> dict:
    """
    Decode and verify a JWT access token.

    Raises JWTError if:
      - Signature is invalid / token was tampered with
      - Token has expired
      - Token type is not "access" (prevents refresh tokens being used as access tokens)
    """
    payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
    if payload.get("type") != "access":
        raise JWTError("Token type mismatch — not an access token.")
    return payload


# --- Refresh token (opaque) -------------------------------------------

def create_refresh_token() -> tuple[str, datetime]:
    """
    Generate a cryptographically secure opaque refresh token.

    Returns:
      (token_string, expires_at_datetime)

    Why opaque instead of JWT?
      - We store it in the DB, so we can instantly revoke it (logout).
      - A JWT refresh token cannot be revoked before its expiry without
        a blocklist — which adds DB complexity anyway.
    """
    token = secrets.token_urlsafe(64)       # 86-char URL-safe base64 string
    expires_at = (datetime.now(timezone.utc) + timedelta(
        days=settings.refresh_token_expire_days
    )).replace(tzinfo=None)
    return token, expires_at
