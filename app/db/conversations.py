"""
app/db/conversations.py

Conversation CRUD, ownership verification, and metadata queries.
"""
import asyncpg


async def create_conversation(pool: asyncpg.Pool, user_id: str, title: str = "New Conversation") -> str:
    """Create a new conversation and return its UUID."""
    row = await pool.fetchrow(
        "INSERT INTO conversations (user_id, title) VALUES ($1, $2) RETURNING id",
        user_id, title,
    )
    return str(row["id"])


async def get_conversations_by_user(pool: asyncpg.Pool, user_id: str) -> list[dict]:
    """Return all conversations belonging to a user, newest first. Auto-prunes empty unused ones."""
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
    return result == "DELETE 1"


async def verify_conversation_ownership(pool: asyncpg.Pool, conversation_id: str, user_id: str) -> bool:
    """Return True if the conversation belongs to the given user."""
    row = await pool.fetchrow(
        "SELECT id FROM conversations WHERE id = $1 AND user_id = $2",
        conversation_id, user_id,
    )
    return row is not None


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


async def mark_conversation_has_documents(pool: asyncpg.Pool, conversation_id: str) -> None:
    """Flip has_documents = TRUE for a conversation after its first successful ingest."""
    await pool.execute(
        "UPDATE conversations SET has_documents = TRUE WHERE id = $1",
        conversation_id,
    )


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
