"""
app/routers/chat.py

Chat HTTP endpoints — thin router that delegates to the orchestrator and services.
"""
import asyncio
import logging

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.core.dependencies import get_current_user, get_pool
from app.middleware.rate_limit import limiter
from app.db import (
    get_history, save_message, get_conversation_has_documents,
    verify_conversation_ownership, get_memory_enabled, get_user_by_id,
)
from app.schemas import ChatRequest
from app.services.chat_stream import stream_chat_response

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["Chat"])


@router.post("/chat/stream")
@limiter.limit("7/minute")
async def chat_stream(
    request: Request,
    body: ChatRequest,
    pool: asyncpg.Pool = Depends(get_pool),
    current_user: dict = Depends(get_current_user),
):
    """
    Streaming chat endpoint via Server-Sent Events (SSE).

    Flow:
      1. Validates presence of either text message or uploaded image.
      2. Verifies session ownership to prevent cross-tenant message injection.
      3. Concurrently fetches conversation history, document status, memory settings,
         and user profile via asyncio.gather to minimize latency before stream start.
      4. Saves the incoming user message to Postgres.
      5. Returns a Starlette StreamingResponse with headers tuned to disable reverse-proxy buffering.
    """
    if not body.message.strip() and not body.images:
        raise HTTPException(
            status_code=400,
            detail="Either a message or at least one image is required.",
        )

    owns = await verify_conversation_ownership(pool, body.conversation_id, current_user["id"])
    if not owns:
        raise HTTPException(status_code=404, detail="Conversation not found.")

    # Concurrently execute 4 database lookups in parallel instead of sequentially
    history, has_documents, mem_enabled, user_profile = await asyncio.gather(
        get_history(pool, body.conversation_id, limit=20),
        get_conversation_has_documents(pool, body.conversation_id),
        get_memory_enabled(pool, current_user["id"]),
        get_user_by_id(pool, current_user["id"]),
    )

    saved_user_msg = body.message.strip() if body.message.strip() else "[Image attached]"
    await save_message(pool, body.conversation_id, "user", saved_user_msg)
    user_tz = request.headers.get("x-user-timezone")

    event_generator = stream_chat_response(
        request=request,
        pool=pool,
        user_id=current_user["id"],
        conversation_id=body.conversation_id,
        query=body.message,
        history=history,
        has_documents=has_documents,
        images=body.images,
        user_tz=user_tz,
        memory_enabled=mem_enabled,
        user_profile=user_profile,
    )

    return StreamingResponse(
        event_generator,
        media_type="text/event-stream",
        headers={
            # Prevent browser and intermediate caching of the streaming responses
            "Cache-Control": "no-cache",
            # Maintain persistent HTTP connection for the duration of the stream
            "Connection": "keep-alive",
            # Disables response buffering in Nginx and Cloudflare so SSE chunks stream immediately
            "X-Accel-Buffering": "no",
        },
    )

