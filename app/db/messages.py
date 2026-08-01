"""
app/db/messages.py

Chat message read/write queries.
"""
import asyncpg


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
