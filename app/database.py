import asyncpg
from app.config import Settings


# --- DDL ---------------------------------------------------------------

_CREATE_TABLES_SQL = """
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email           VARCHAR(255) UNIQUE NOT NULL,
    hashed_password TEXT NOT NULL DEFAULT '',
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS conversations (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID REFERENCES users(id) ON DELETE CASCADE,
    title       VARCHAR(255) DEFAULT 'New Conversation',
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS messages (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID REFERENCES conversations(id) ON DELETE CASCADE,
    role            VARCHAR(50) CHECK (role IN ('user', 'assistant', 'system')) NOT NULL,
    content         TEXT NOT NULL,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS refresh_tokens (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id    UUID REFERENCES users(id) ON DELETE CASCADE NOT NULL,
    token      TEXT UNIQUE NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS conversation_documents (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID REFERENCES conversations(id) ON DELETE CASCADE NOT NULL,
    filename        VARCHAR(255) NOT NULL,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

_ADD_HASHED_PASSWORD_COL = """
ALTER TABLE users ADD COLUMN IF NOT EXISTS hashed_password TEXT NOT NULL DEFAULT '';
"""

# Tracks whether a conversation has ever had at least one document ingested for it.
# The CEO uses this as a hard gate — knowledge_team is never reachable if False.
_ADD_CONVERSATION_HAS_DOCUMENTS_COL = """
ALTER TABLE conversations ADD COLUMN IF NOT EXISTS has_documents BOOLEAN NOT NULL DEFAULT FALSE;
"""

# --- Pool lifecycle ----------------------------------------------------

async def init_db_pool(settings: Settings) -> asyncpg.Pool:
    """Create the asyncpg connection pool and ensure all tables exist."""
    pool = await asyncpg.create_pool(
        host=settings.postgres_host,
        port=settings.postgres_port,
        user=settings.postgres_user,
        password=settings.postgres_password,
        database=settings.postgres_db,
        min_size=2,
        max_size=10,
    )
    async with pool.acquire() as conn:
        await conn.execute(_CREATE_TABLES_SQL)
        await conn.execute(_ADD_HASHED_PASSWORD_COL)
        await conn.execute(_ADD_CONVERSATION_HAS_DOCUMENTS_COL)  # idempotent — safe on every startup
    return pool


# --- Query helpers -----------------------------------------------------

async def get_history(pool: asyncpg.Pool, conversation_id: str, limit: int = 20) -> list[dict]:
    """Return the last `limit` messages for a conversation, oldest first."""
    rows = await pool.fetch(
        """
        WITH recent_messages AS (
            SELECT role, content, created_at
            FROM messages
            WHERE conversation_id = $1
            ORDER BY created_at DESC
            LIMIT $2
        )
        SELECT role, content
        FROM recent_messages
        ORDER BY created_at ASC
        """,
        conversation_id,
        limit,
    )
    return [dict(r) for r in rows]


async def save_message(pool: asyncpg.Pool, conversation_id: str, role: str, content: str) -> None:
    """Insert a single message and bump the conversation updated_at."""
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                "INSERT INTO messages (conversation_id, role, content) VALUES ($1, $2, $3)",
                conversation_id, role, content,
            )
            await conn.execute(
                "UPDATE conversations SET updated_at = CURRENT_TIMESTAMP WHERE id = $1",
                conversation_id,
            )


async def create_conversation(pool: asyncpg.Pool, user_id: str, title: str = "New Conversation") -> str:
    """Create a new conversation and return its UUID."""
    row = await pool.fetchrow(
        "INSERT INTO conversations (user_id, title) VALUES ($1, $2) RETURNING id",
        user_id, title,
    )
    return str(row["id"])


async def get_conversations_by_user(pool: asyncpg.Pool, user_id: str) -> list[dict]:
    """Return all conversations belonging to a user, newest first. Auto-prunes empty unused ones."""
    # Delete unused empty conversations (no messages and no documents)
    await pool.execute(
        """
        DELETE FROM conversations
        WHERE user_id = $1
          AND has_documents = FALSE
          AND id NOT IN (SELECT DISTINCT conversation_id FROM messages)
        """,
        user_id,
    )
    rows = await pool.fetch(
        """
        SELECT id, title, created_at, updated_at
        FROM conversations
        WHERE user_id = $1
        ORDER BY updated_at DESC
        """,
        user_id,
    )
    return [dict(r) for r in rows]


async def delete_conversation(pool: asyncpg.Pool, conversation_id: str, user_id: str) -> bool:
    """
    Delete a conversation (and all its messages via CASCADE).
    Returns True if a row was deleted, False if not found or not owned by user.
    """
    result = await pool.execute(
        "DELETE FROM conversations WHERE id = $1 AND user_id = $2",
        conversation_id, user_id,
    )
    # asyncpg returns 'DELETE N' — check if 1 row was affected
    return result == "DELETE 1"


async def verify_conversation_ownership(pool: asyncpg.Pool, conversation_id: str, user_id: str) -> bool:
    """Return True if the conversation belongs to the given user."""
    row = await pool.fetchrow(
        "SELECT id FROM conversations WHERE id = $1 AND user_id = $2",
        conversation_id, user_id,
    )
    return row is not None


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
        "SELECT id, email, hashed_password FROM users WHERE email = $1",
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


# --- Refresh token helpers --------------------------------------------

async def save_refresh_token(
    pool: asyncpg.Pool,
    user_id: str,
    token: str,
    expires_at,          # datetime object
) -> None:
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


# --- Document ownership flag ------------------------------------------

async def mark_conversation_has_documents(pool: asyncpg.Pool, conversation_id: str) -> None:
    """
    Flip has_documents = TRUE for a conversation after its first successful ingest.
    Using OR to make it idempotent — safe to call on every ingest.
    """
    await pool.execute(
        "UPDATE conversations SET has_documents = TRUE WHERE id = $1",
        conversation_id,
    )


async def get_conversation_has_documents(pool: asyncpg.Pool, conversation_id: str) -> bool:
    """
    Return True if the conversation has ever had at least one document ingested.
    Used by the CEO as a hard gate before routing to knowledge_team.
    """
    row = await pool.fetchrow(
        "SELECT has_documents FROM conversations WHERE id = $1",
        conversation_id,
    )
    return bool(row["has_documents"]) if row else False


async def get_conversation_title(pool: asyncpg.Pool, conversation_id: str) -> str:
    """Return the current title of a conversation."""
    row = await pool.fetchrow(
        "SELECT title FROM conversations WHERE id = $1",
        conversation_id,
    )
    return row["title"] if row else "New Conversation"


async def update_conversation_title(pool: asyncpg.Pool, conversation_id: str, title: str) -> None:
    """Update the title of a conversation."""
    await pool.execute(
        "UPDATE conversations SET title = $1, updated_at = CURRENT_TIMESTAMP WHERE id = $2",
        title, conversation_id,
    )


async def check_document_exists(pool: asyncpg.Pool, conversation_id: str, filename: str) -> bool:
    """
    Return True if a document with the same filename (case-insensitive) has already
    been ingested into this specific conversation.

    Scope: per-conversation only — the same filename in a different conversation
    (even by the same user) is a completely independent upload and is allowed.
    """
    row = await pool.fetchrow(
        """
        SELECT id FROM conversation_documents
        WHERE conversation_id = $1
          AND LOWER(filename) = LOWER($2)
        LIMIT 1
        """,
        conversation_id, filename,
    )
    return row is not None


async def add_conversation_document(pool: asyncpg.Pool, conversation_id: str, filename: str) -> None:
    """Record an ingested document for a conversation."""
    await pool.execute(
        "INSERT INTO conversation_documents (conversation_id, filename) VALUES ($1, $2)",
        conversation_id, filename,
    )


async def get_conversation_documents(pool: asyncpg.Pool, conversation_id: str) -> list[str]:
    """Fetch distinct filenames of ingested documents for a conversation."""
    rows = await pool.fetch(
        "SELECT DISTINCT filename FROM conversation_documents WHERE conversation_id = $1 ORDER BY filename ASC",
        conversation_id,
    )
    return [r["filename"] for r in rows]


