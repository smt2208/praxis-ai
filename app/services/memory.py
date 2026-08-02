"""
app/services/memory.py

Long-term user memory powered by Mem0 (self-hosted) + existing Qdrant.

Two public functions:
  - retrieve_memories()  → called BEFORE the LLM to inject context
  - store_memories()     → called AFTER the response in the background

Mem0 auto-creates its Qdrant collection on first use — zero manual setup.
"""
import asyncio
import logging
from functools import lru_cache

from mem0 import Memory

from app.config import get_settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Singleton: one Mem0 Memory instance shared across all requests
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def _get_memory() -> Memory:
    """Build and cache the Mem0 Memory instance using app settings."""
    settings = get_settings()

    config = {
        "vector_store": {
            "provider": "qdrant",
            "config": {
                "collection_name": settings.mem0_collection_name,
                "url": settings.qdrant_url,
                "api_key": settings.qdrant_api_key,
            },
        },
        "llm": {
            "provider": "openai",
            "config": {
                "model": "gpt-4o-mini",
                "api_key": settings.openai_api_key,
            },
        },
        "embedder": {
            "provider": "openai",
            "config": {
                "model": "text-embedding-3-small",
                "api_key": settings.openai_api_key,
            },
        },
    }

    logger.info("[memory] Initializing Mem0 with Qdrant collection '%s'", settings.mem0_collection_name)
    return Memory.from_config(config)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def retrieve_memories(user_id: str, query: str, limit: int = 5) -> str:
    """
    Search Mem0 for memories relevant to the current query.

    Returns a formatted string ready to inject into a system prompt.
    Returns empty string if no memories found or on error (non-blocking).
    """
    try:
        mem = _get_memory()
        # Handle both v1 (user_id="...") and v2 (filters={"user_id": "..."}) search formats defensively
        try:
            results = mem.search(query=query, filters={"user_id": user_id}, limit=limit)
        except Exception:
            results = mem.search(query=query, user_id=user_id, limit=limit)

        if isinstance(results, list):
            memories = results
        elif isinstance(results, dict):
            memories = results.get("results", [])
        else:
            memories = []

        if not memories:
            return ""

        lines = [m["memory"] for m in memories if isinstance(m, dict) and m.get("memory")]
        if not lines:
            return ""

        return "What you remember about this user from past conversations:\n" + "\n".join(f"- {line}" for line in lines)

    except Exception as exc:
        logger.error("[memory] Failed to retrieve memories for user %s: %s", user_id, exc)
        return ""


def store_memories(user_id: str, user_message: str, assistant_response: str) -> None:
    """
    Extract and store new facts from a conversation turn.

    This is a synchronous, blocking call — always run via
    asyncio.create_task(store_memories_background(...)) from async code.
    """
    try:
        mem = _get_memory()
        conversation_turn = f"User: {user_message}\nAssistant: {assistant_response}"
        mem.add(conversation_turn, user_id=user_id)
        logger.info("[memory] Successfully stored memory for user %s", user_id)

    except Exception as exc:
        # Log error clearly for diagnostics
        logger.error("[memory] Failed to store memory for user %s: %s", user_id, exc, exc_info=True)



async def store_memories_background(user_id: str, user_message: str, assistant_response: str) -> None:
    """
    Async wrapper — runs store_memories() in a thread pool so it
    doesn't block the event loop. Designed to be fire-and-forget via
    asyncio.create_task().
    """
    await asyncio.to_thread(store_memories, user_id, user_message, assistant_response)


def delete_all_memories(user_id: str) -> None:
    """Delete all long-term memories for a given user."""
    try:
        mem = _get_memory()
        mem.delete_all(user_id=user_id)
        logger.info("[memory] Cleared all memories for user %s", user_id)
    except Exception as exc:
        logger.warning("[memory] Failed to delete memories for user %s: %s", user_id, exc)

