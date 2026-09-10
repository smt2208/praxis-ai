"""
app/services/chat_stream.py

SSE streaming coordination service.
Encapsulates:
  - Wire protocol formatting (Server-Sent Events)
  - Async stream consumption from the multi-agent orchestrator
  - Message persistence and background post-processing triggers
"""
import asyncio
import json
import logging
from typing import AsyncGenerator

import asyncpg
from fastapi import Request

from app.db import save_message, get_conversation_title
from app.services.chat import auto_generate_title
from app.services.memory import store_memories_background
from app.agents.orchestrator import astream_graph_events

logger = logging.getLogger(__name__)


def format_sse(event: str, data: dict) -> str:
    """Format an event and JSON payload according to the W3C SSE standard."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


async def stream_chat_response(
    request: Request,
    pool: asyncpg.Pool,
    user_id: str,
    conversation_id: str,
    query: str,
    history: list,
    has_documents: bool,
    images: list[str] | None,
    user_tz: str | None,
    memory_enabled: bool,
    user_profile: dict | None,
) -> AsyncGenerator[str, None]:
    """
    Coordinates Server-Sent Events (SSE) streaming for a chat turn.

    Lifecycle:
      1. Consumes domain events from the multi-agent orchestrator (`astream_graph_events`).
      2. Checks for client TCP disconnects on each event to terminate LLM execution early.
      3. Buffers generated tokens into `full_answer` for message persistence.
      4. In the `finally` block, uses `asyncio.shield` to guarantee database persistence
         even if the HTTP connection is aborted by the client mid-stream.
      5. Dispatches asynchronous background tasks (title generation, memory extraction)
         without delaying client stream termination.
    """
    full_answer: list[str] = []
    stream_error: bool = False

    try:
        async for evt in astream_graph_events(
            query=query,
            history=history,
            user_id=user_id,
            conversation_id=conversation_id,
            has_documents=has_documents,
            images=images,
            user_tz=user_tz,
            memory_enabled=memory_enabled,
            user_profile=user_profile,
        ):
            # Check if the client closed their browser tab or aborted the fetch connection.
            # Terminating here avoids wasting LLM token generation for disconnected clients.
            if await request.is_disconnected():
                logger.info("[Chat Stream] Client disconnected prematurely: conv_id=%s", conversation_id)
                break

            event_type = evt.get("event", "message")
            data = evt.get("data", {})

            if event_type == "token":
                content = data.get("content", "")
                if content:
                    full_answer.append(content)

            yield format_sse(event_type, data)

    except Exception as err:
        stream_error = True
        logger.error("[Chat Stream] Stream generation failed: %s", err, exc_info=True)
        yield format_sse("error", {"message": "An error occurred while processing your request. Please try again."})

    finally:
        # Guarantee persistence of the generated content (or partial response on failure/disconnect).
        # Wrapped in asyncio.shield so the database write completes even if this coroutine's task
        # was cancelled due to an aborted client TCP connection.
        final_text = "".join(full_answer)
        if final_text:
            try:
                await asyncio.shield(save_message(pool, conversation_id, "assistant", final_text))
            except asyncio.CancelledError:
                pass
            except Exception:
                logger.warning("[Chat Stream] Failed to persist assistant message to DB: conv_id=%s", conversation_id)

            # Extract user memories in the background; does not block the streaming completion.
            if memory_enabled:
                asyncio.create_task(store_memories_background(user_id, query, final_text))

        # Auto-title first conversation message asynchronously if still named 'New Conversation'
        if not stream_error:
            try:
                current_title = await asyncio.shield(get_conversation_title(pool, conversation_id))
                if current_title == "New Conversation":
                    asyncio.create_task(auto_generate_title(pool, conversation_id, query))
            except (asyncio.CancelledError, Exception):
                pass

