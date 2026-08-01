"""
app/db/users.py

User account CRUD and email verification queries.
"""
import asyncpg


async def create_user(pool: asyncpg.Pool, email: str, hashed_password: str) -> str:
    """Create a new user with a hashed password and return its UUID."""
    row = await pool.fetchrow(
        """
        INSERT INTO users (email, hashed_password) VALUES ($1, $2)
        RETURNING id
        """,
        email, hashed_password,
    )
    return str(row["id"])


async def get_user_by_email(pool: asyncpg.Pool, email: str) -> dict | None:
    """Fetch a user row by email. Returns None if not found."""
    row = await pool.fetchrow(
        "SELECT id, email, hashed_password, is_verified FROM users WHERE email = $1",
        email,
    )
    return dict(row) if row else None


async def get_user_by_id(pool: asyncpg.Pool, user_id: str) -> dict | None:
    """Fetch a user row by UUID. Returns None if not found."""
    row = await pool.fetchrow(
        "SELECT id, email FROM users WHERE id = $1",
        user_id,
    )
    return dict(row) if row else None


async def set_verification_token(pool: asyncpg.Pool, user_id: str, token: str) -> None:
    """Store a verification token on the user row after registration."""
    await pool.execute(
        "UPDATE users SET verification_token = $1 WHERE id = $2",
        token, user_id,
    )


async def verify_email_token(pool: asyncpg.Pool, token: str) -> bool:
    """
    Mark the user as verified if the token matches and hasn't been used.
    Returns True if a user was verified, False if the token is invalid or already used.
    """
    result = await pool.execute(
        """
        UPDATE users
        SET is_verified = TRUE, verification_token = NULL
        WHERE verification_token = $1
          AND is_verified = FALSE
        """,
        token,
    )
    return result == "UPDATE 1"
