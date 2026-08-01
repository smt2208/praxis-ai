"""
app/auth/router.py

Authentication endpoints:
  POST /api/v1/auth/register       → create account, send verification email, return tokens
  POST /api/v1/auth/login          → verify credentials + email, return access + refresh token
  POST /api/v1/auth/verify-email   → activate account from email link token
  POST /api/v1/auth/refresh        → exchange refresh token for a new access token
  POST /api/v1/auth/logout         → revoke refresh token(s)
  GET  /api/v1/auth/me             → return current user info (protected)

Token lifecycle:
  - Access token  (30 min JWT)  → sent in Authorization: Bearer header on every request
  - Refresh token (7 day opaque) → sent only to /refresh to get a new access token
"""
import secrets
import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.auth.security import (
    hash_password, verify_password,
    create_access_token, create_refresh_token,
)
from app.auth.dependencies import get_current_user
from app.dependencies import get_pool
from app.db import (
    create_user, get_user_by_email, get_user_by_id,
    save_refresh_token, get_refresh_token,
    delete_refresh_token, delete_all_user_refresh_tokens,
    set_verification_token, verify_email_token,
)
from app.schemas import (
    RegisterRequest, LoginRequest, RefreshRequest, LogoutRequest,
    TokenResponse, UserMeResponse, VerifyEmailRequest,
)
from app.middleware.rate_limit import limiter
from app.email import send_verification_email

router = APIRouter(prefix="/api/v1/auth", tags=["Auth"])


# --- Helpers -----------------------------------------------------------

async def _issue_tokens(pool: asyncpg.Pool, user_id: str, email: str) -> TokenResponse:
    """
    Mint a fresh access + refresh token pair and persist the refresh token.
    Called by both register and login so logic lives in one place.
    """
    access_token = create_access_token(user_id, email)
    refresh_token, expires_at = create_refresh_token()
    await save_refresh_token(pool, user_id, refresh_token, expires_at)
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
    )


# --- Endpoints ---------------------------------------------------------

@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")   # brute-force protection: max 5 registration attempts per minute per IP
async def register(request: Request, body: RegisterRequest, pool: asyncpg.Pool = Depends(get_pool)):
    """
    Register a new user account.
    Sends a verification email. Returns tokens so the client can access
    the app immediately, but the email gate is enforced on login.
    """
    existing = await get_user_by_email(pool, body.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    hashed = hash_password(body.password)
    user_id = await create_user(pool, body.email, hashed)

    # Generate and store a secure one-time verification token
    token = secrets.token_urlsafe(32)
    await set_verification_token(pool, user_id, token)

    # Send verification email (errors are caught inside — won't fail registration)
    send_verification_email(body.email, token)

    tokens = await _issue_tokens(pool, user_id, body.email)
    tokens.needs_verification = True   # tell UI to show "check your inbox" screen
    return tokens


@router.post("/verify-email", status_code=status.HTTP_200_OK)
async def verify_email(body: VerifyEmailRequest, pool: asyncpg.Pool = Depends(get_pool)):
    """
    Activate a user account using the token from the verification email link.
    The token is consumed (set to NULL) on first use — cannot be reused.
    """
    verified = await verify_email_token(pool, body.token)
    if not verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Verification link is invalid or has already been used.",
        )
    return {"message": "Email verified successfully. You can now log in."}


@router.post("/login", response_model=TokenResponse)
@limiter.limit("10/minute")  # brute-force protection: max 10 login attempts per minute per IP
async def login(request: Request, body: LoginRequest, pool: asyncpg.Pool = Depends(get_pool)):
    """
    Authenticate with email + password.
    Blocks login if the email has not been verified yet.
    Returns both tokens on success.
    """
    user = await get_user_by_email(pool, body.email)
    if not user or not verify_password(body.password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
        )

    if not user["is_verified"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Please verify your email before logging in. Check your inbox for the verification link.",
        )

    return await _issue_tokens(pool, str(user["id"]), user["email"])


@router.post("/refresh", response_model=TokenResponse)
async def refresh(body: RefreshRequest, pool: asyncpg.Pool = Depends(get_pool)):
    """
    Exchange a valid refresh token for a new access token + new refresh token.

    Rotation strategy: the old refresh token is deleted and a brand-new one
    is issued (refresh token rotation). This limits the damage if a refresh
    token is ever stolen — each token can only be used once.
    """
    # Validate the refresh token against the DB
    token_row = await get_refresh_token(pool, body.refresh_token)
    if not token_row:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token is invalid or has expired. Please log in again.",
        )

    # Fetch the user
    user = await get_user_by_id(pool, str(token_row["user_id"]))
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User no longer exists.",
        )

    # Rotate: delete old, issue new pair
    await delete_refresh_token(pool, body.refresh_token)
    return await _issue_tokens(pool, str(user["id"]), user["email"])


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    body: LogoutRequest,
    pool: asyncpg.Pool = Depends(get_pool),
    current_user: dict = Depends(get_current_user),
):
    """
    Revoke refresh token(s) to invalidate sessions.

    - logout_all_devices=False (default) → revoke only the provided token
    - logout_all_devices=True            → revoke ALL tokens for this user
    """
    if body.logout_all_devices:
        await delete_all_user_refresh_tokens(pool, current_user["id"])
    else:
        await delete_refresh_token(pool, body.refresh_token)


@router.get("/me", response_model=UserMeResponse)
async def me(current_user: dict = Depends(get_current_user)):
    """Return the currently authenticated user's info from the JWT payload."""
    return UserMeResponse(user_id=current_user["id"], email=current_user["email"])
