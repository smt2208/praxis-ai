"""
app/services/chat_stream.py

SSE streaming coordination service.
Encapsulates:
  - Wire protocol formatting (Server-Sent Events)
  - Async stream consumption from the multi-agent orchestrator
  - Message persistence and background post-processing triggers
  - Image persistence to S3 and image summary extraction for cross-turn context
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

# Strong reference set to prevent background tasks from being garbage-collected mid-execution (RUF006)
_background_tasks: set[asyncio.Task] = set()


def _track_background_task(coro) -> asyncio.Task:
    """Schedule a coroutine as an asyncio task with a retained strong reference."""
    task = asyncio.create_task(coro)
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
    return task


def format_sse(event: str, data: dict) -> str:
    """Format an event and JSON payload according to the W3C SSE standard."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def _extract_image_summary(full_answer: str, max_length: int = 200) -> str:
    """
    Extract a brief summary of what the vision agent analyzed from its response.
    Takes the first ~200 chars as a compact description for metadata storage.
    """
    if not full_answer:
        return ""
    # Take the first paragraph or max_length chars, whichever is shorter
    first_para = full_answer.split("\n\n")[0].strip()
    summary = first_para[:max_length]
    if len(first_para) > max_length:
        summary += "..."
    return summary


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
    doc_names: list[str] | None = None,
) -> AsyncGenerator[str, None]:
    """
    Coordinates Server-Sent Events (SSE) streaming for a chat turn.

    Lifecycle:
      1. If images are present, uploads them to S3 for persistence across turns.
      2. Consumes domain events from the multi-agent orchestrator (`astream_graph_events`).
      3. Checks for client TCP disconnects on each event to terminate LLM execution early.
      4. Buffers generated tokens into `full_answer` for message persistence.
      5. In the `finally` block, uses `asyncio.shield` to guarantee database persistence
         even if the HTTP connection is aborted by the client mid-stream.
      6. Dispatches asynchronous background tasks (title generation, memory extraction)
         without delaying client stream termination.
      7. If vision agent was used, extracts an image summary and saves it in metadata.
    """
    full_answer: list[str] = []
    stream_error: bool = False
    executed_route: str = "general"

    # Upload images to S3 in background (non-blocking to stream start)
    image_urls: list[str] = []
    if images:
        try:
            from app.services.storage import upload_images_to_s3
            image_urls = await upload_images_to_s3(images, conversation_id)
            if image_urls:
                try:
                    await pool.execute(
                        """
                        UPDATE messages
                        SET metadata = jsonb_set(COALESCE(metadata, '{}'::jsonb), '{image_urls}', $1::jsonb)
                        WHERE id = (
                            SELECT id FROM messages
                            WHERE conversation_id = $2 AND role = 'user'
                            ORDER BY created_at DESC
                            LIMIT 1
                        )
                        """,
                        json.dumps(image_urls),
                        conversation_id,
                    )
                except Exception as db_exc:
                    logger.warning("[Chat Stream] Could not attach image_urls to user message: %s", db_exc)
        except Exception as exc:
            logger.warning("[Chat Stream] S3 image upload failed (continuing without): %s", exc)

    try:
        async for evt in astream_graph_events(
            query=query,
            history=history,
            user_id=user_id,
            conversation_id=conversation_id,
            has_documents=has_documents,
            images=images,
            image_urls=image_urls,
            user_tz=user_tz,
            memory_enabled=memory_enabled,
            user_profile=user_profile,
            doc_names=doc_names,
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

            # Track which route executed for image summary logic
            if event_type == "done":
                executed_route = data.get("route", executed_route)

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
        saved_cancelled = False

        if final_text:
            # Build assistant message metadata
            assistant_metadata = {}
            if images and executed_route == "vision_agent":
                # Store image summary so future turns know what was in the images
                summary = _extract_image_summary(final_text)
                if summary:
                    assistant_metadata["image_summaries"] = [summary]
                if image_urls:
                    assistant_metadata["image_urls"] = image_urls

            try:
                await asyncio.shield(
                    save_message(
                        pool, conversation_id, "assistant", final_text,
                        metadata=assistant_metadata or None,
                    )
                )
            except asyncio.CancelledError:
                saved_cancelled = True
            except Exception:
                logger.warning("[Chat Stream] Failed to persist assistant message to DB: conv_id=%s", conversation_id)

            # Extract user memories in the background; does not block the streaming completion.
            # We skip memory extraction if `has_documents` is true to prevent document facts
            # from leaking into the user's global memory profile and appearing in other conversations.
            if memory_enabled and not has_documents:
                _track_background_task(store_memories_background(user_id, query, final_text))

        # Auto-title first conversation message asynchronously if still named 'New Conversation'
        if not stream_error:
            try:
                current_title = await asyncio.shield(get_conversation_title(pool, conversation_id))
                if current_title == "New Conversation":
                    _track_background_task(auto_generate_title(pool, conversation_id, query))
            except asyncio.CancelledError:
                saved_cancelled = True
            except Exception as title_err:
                logger.warning("[Chat Stream] Auto-title check failed: %s", title_err)

        if saved_cancelled:
            raise asyncio.CancelledError()
