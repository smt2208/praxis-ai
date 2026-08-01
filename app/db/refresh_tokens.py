"""
app/db/refresh_tokens.py

Refresh token storage and revocation queries.
"""
import asyncpg


async def save_refresh_token(pool: asyncpg.Pool, user_id: str, token: str, expires_at) -> None:
    """Persist a refresh token to the DB."""
    await pool.execute(
        """
        INSERT INTO refresh_tokens (user_id, token, expires_at)
        VALUES ($1, $2, $3)
        """,
        user_id, token, expires_at,
    )


async def get_refresh_token(pool: asyncpg.Pool, token: str) -> dict | None:
    """
    Fetch a refresh token row.
    Returns None if not found OR if already expired.
    """
    row = await pool.fetchrow(
        """
        SELECT id, user_id, expires_at
        FROM refresh_tokens
        WHERE token = $1
          AND expires_at > CURRENT_TIMESTAMP
        """,
        token,
    )
    return dict(row) if row else None


async def delete_refresh_token(pool: asyncpg.Pool, token: str) -> None:
    """Revoke a single refresh token (logout current device)."""
    await pool.execute(
        "DELETE FROM refresh_tokens WHERE token = $1",
        token,
    )


async def delete_all_user_refresh_tokens(pool: asyncpg.Pool, user_id: str) -> None:
    """Revoke ALL refresh tokens for a user (logout all devices)."""
    await pool.execute(
        "DELETE FROM refresh_tokens WHERE user_id = $1",
        user_id,
    )
