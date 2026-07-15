import asyncpg
from app.config import Settings


# --- DDL ---------------------------------------------------------------

_CREATE_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS users (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email       VARCHAR(255) UNIQUE NOT NULL,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
    return pool


# --- Query helpers -----------------------------------------------------

async def get_history(pool: asyncpg.Pool, conversation_id: str, limit: int = 20) -> list[dict]:
    """Return the last `limit` messages for a conversation, oldest first."""
    rows = await pool.fetch(
        """
        SELECT role, content FROM messages
        WHERE conversation_id = $1
        ORDER BY created_at ASC
        LIMIT $2
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


async def create_user(pool: asyncpg.Pool, email: str) -> str:
    """Create a new user (or return existing) and return its UUID."""
    row = await pool.fetchrow(
        """
        INSERT INTO users (email) VALUES ($1)
        ON CONFLICT (email) DO UPDATE SET email = EXCLUDED.email
        RETURNING id
        """,
        email,
    )
    return str(row["id"])
