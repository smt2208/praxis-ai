"""
app/db/documents.py

Document tracking queries and Qdrant vector chunk cleanup.
"""
import asyncio
import logging

import asyncpg
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue

from app.config import get_settings

logger = logging.getLogger(__name__)


async def check_document_exists(pool: asyncpg.Pool, conversation_id: str, filename: str) -> bool:
    """
    Return True if a document with the same filename (case-insensitive) has already
    been ingested into this specific conversation.
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


async def delete_conversation_qdrant_chunks(conversation_id: str) -> None:
    """
    Delete all vector chunks in Qdrant that belong to the given conversation.

    Called immediately before the Postgres conversation row is deleted so that
    vector data never becomes orphaned. Errors are caught and logged — a Qdrant
    blip should not block the user from deleting their conversation in the app.
    """
    cfg = get_settings()

    try:
        client = QdrantClient(url=cfg.qdrant_url, api_key=cfg.qdrant_api_key)

        conv_filter = Filter(
            should=[
                Filter(must=[FieldCondition(key="conversation_id", match=MatchValue(value=conversation_id))]),
                Filter(must=[FieldCondition(key="metadata.conversation_id", match=MatchValue(value=conversation_id))]),
            ]
        )

        await asyncio.to_thread(
            client.delete,
            collection_name=cfg.qdrant_collection_name,
            points_selector=conv_filter,
        )
        logger.info("[qdrant] Deleted chunks for conversation %s", conversation_id)
    except Exception as exc:
        logger.warning("[qdrant] Could not delete chunks for conversation %s: %s", conversation_id, exc)
