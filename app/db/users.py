"""
app/db/users.py

User account CRUD and email verification queries.
"""
import asyncpg


async def create_user(pool: asyncpg.Pool, email: str, hashed_password: str, full_name: str = "") -> str:
    """Create a new user with a hashed password and optional full name. Returns its UUID."""
    row = await pool.fetchrow(
        """
        INSERT INTO users (email, hashed_password, full_name) VALUES ($1, $2, $3)
        RETURNING id
        """,
        email, hashed_password, full_name or None,
    )
    return str(row["id"])


async def get_user_by_email(pool: asyncpg.Pool, email: str) -> dict | None:
    """Fetch a user row by email. Returns None if not found."""
    row = await pool.fetchrow(
        "SELECT id, email, hashed_password, is_verified, full_name FROM users WHERE email = $1",
        email,
    )
    return dict(row) if row else None


async def get_user_by_id(pool: asyncpg.Pool, user_id: str) -> dict | None:
    """Fetch a user row by UUID. Returns None if not found."""
    row = await pool.fetchrow(
        """
        SELECT id, email, is_verified, full_name, memory_enabled, age, profession, city, state, country
        FROM users WHERE id = $1
        """,
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


async def set_password_reset_token(
    pool: asyncpg.Pool, email: str, token: str, expires_at
) -> bool:
    """
    Store a password reset token and expiry on the user row.
    Returns True if the email exists, False if not found.
    """
    result = await pool.execute(
        """
        UPDATE users
        SET password_reset_token = $1, password_reset_expires_at = $2
        WHERE email = $3
        """,
        token, expires_at, email,
    )
    return result == "UPDATE 1"


async def get_user_by_reset_token(pool: asyncpg.Pool, token: str) -> dict | None:
    """Fetch user by valid (not-expired) reset token. Returns None if invalid or expired."""
    row = await pool.fetchrow(
        """
        SELECT id, email
        FROM users
        WHERE password_reset_token = $1
          AND password_reset_expires_at > (NOW() AT TIME ZONE 'utc')
        """,
        token,
    )
    return dict(row) if row else None


async def reset_user_password(
    pool: asyncpg.Pool, token: str, new_hashed_password: str
) -> bool:
    """
    Update password and clear the reset token in a single atomic operation.
    Returns True if the update was applied, False if the token is invalid/expired.
    """
    result = await pool.execute(
        """
        UPDATE users
        SET hashed_password = $1,
            password_reset_token = NULL,
            password_reset_expires_at = NULL
        WHERE password_reset_token = $2
          AND password_reset_expires_at > (NOW() AT TIME ZONE 'utc')
        """,
        new_hashed_password, token,
    )
    return result == "UPDATE 1"


async def update_full_name(pool: asyncpg.Pool, user_id: str, full_name: str) -> None:
    """Update the user's display name."""
    await pool.execute(
        "UPDATE users SET full_name = $1 WHERE id = $2",
        full_name or None, user_id,
    )


async def update_user_profile(
    pool: asyncpg.Pool,
    user_id: str,
    full_name: str = "",
    age: int | None = None,
    profession: str = "",
    city: str = "",
    state: str = "",
    country: str = "",
) -> None:
    """Update all extended profile fields for a user."""
    await pool.execute(
        """
        UPDATE users
        SET full_name = $1,
            age = $2,
            profession = $3,
            city = $4,
            state = $5,
            country = $6
        WHERE id = $7
        """,
        full_name.strip() or None,
        age,
        profession.strip() or None,
        city.strip() or None,
        state.strip() or None,
        country.strip() or None,
        user_id,
    )


async def get_memory_enabled(pool: asyncpg.Pool, user_id: str) -> bool:
    """Return whether long-term memory is enabled for the user (default True)."""
    row = await pool.fetchrow(
        "SELECT memory_enabled FROM users WHERE id = $1", user_id
    )
    if not row:
        return True
    # Column may be None on first run before migration applied — default True
    return row["memory_enabled"] if row["memory_enabled"] is not None else True


async def set_memory_enabled(pool: asyncpg.Pool, user_id: str, enabled: bool) -> None:
    """Enable or disable long-term memory for a specific user."""
    await pool.execute(
        "UPDATE users SET memory_enabled = $1 WHERE id = $2",
        enabled, user_id,
    )
