"""
app/db/messages.py

Chat message read/write queries.
Supports optional JSONB metadata for storing image context across turns.
"""
import json
import asyncpg


async def get_history(pool: asyncpg.Pool, conversation_id: str, limit: int = 20) -> list[dict]:
    """
    Return the last `limit` messages for a conversation in chronological order (oldest first).

    Uses a Common Table Expression (CTE) to fetch the N most recent records using
    the descending timestamp index, then flips them into ascending order so that
    the agent LLM receives a natural chronological dialogue stream.
    Includes the optional metadata JSONB column for image context persistence.
    """
    rows = await pool.fetch(
        """
        WITH recent_messages AS (
            SELECT role, content, metadata, created_at
            FROM messages
            WHERE conversation_id = $1
            ORDER BY created_at DESC
            LIMIT $2
        )
        SELECT role, content, metadata
        FROM recent_messages
        ORDER BY created_at ASC
        """,
        conversation_id,
        limit,
    )
    result = []
    for r in rows:
        row_dict = {"role": r["role"], "content": r["content"]}
        # Parse metadata JSONB — returns a dict if present, else empty dict
        raw_meta = r["metadata"]
        if raw_meta:
            row_dict["metadata"] = json.loads(raw_meta) if isinstance(raw_meta, str) else dict(raw_meta)
        else:
            row_dict["metadata"] = {}
        result.append(row_dict)
    return result


async def save_message(
    pool: asyncpg.Pool,
    conversation_id: str,
    role: str,
    content: str,
    metadata: dict | None = None,
) -> None:
    """
    Insert a single chat message and bump the parent conversation's updated_at timestamp.
    Wrapped in an atomic transaction to ensure data consistency.

    Args:
        metadata: Optional dict stored as JSONB. Used for image_count, image_summaries, etc.
    """
    meta_json = json.dumps(metadata) if metadata else "{}"
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                "INSERT INTO messages (conversation_id, role, content, metadata) VALUES ($1, $2, $3, $4::jsonb)",
                conversation_id, role, content, meta_json,
            )
            await conn.execute(
                "UPDATE conversations SET updated_at = CURRENT_TIMESTAMP WHERE id = $1",
                conversation_id,
            )
