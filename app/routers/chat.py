"""
app/routers/chat.py

Chat HTTP endpoints — thin router that delegates to the orchestrator and services.
"""
import asyncio
import json
import logging

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.auth.dependencies import get_current_user
from app.dependencies import get_pool
from app.middleware.rate_limit import limiter
from app.db import (
    get_history, save_message, get_conversation_has_documents,
    get_conversation_title, verify_conversation_ownership,
)
from app.schemas import ChatRequest, ChatResponse
from app.services.chat import auto_generate_title
from agents.orchestrator import invoke_graph, astream_graph_events

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["Chat"])


@router.post("/chat", response_model=ChatResponse)
@limiter.limit("20/minute")
async def chat(
    request: Request,
    body: ChatRequest,
    pool: asyncpg.Pool = Depends(get_pool),
    current_user: dict = Depends(get_current_user),
):
    """
    Main chat endpoint.
    - Reads user identity from JWT.
    - Fetches clean history from DB, runs the multi-agent graph, persists results.
    """
    owns = await verify_conversation_ownership(pool, body.conversation_id, current_user["id"])
    if not owns:
        raise HTTPException(status_code=404, detail="Conversation not found.")

    history, has_documents = await asyncio.gather(
        get_history(pool, body.conversation_id, limit=20),
        get_conversation_has_documents(pool, body.conversation_id),
    )

    await save_message(pool, body.conversation_id, "user", body.message)

    try:
        result = await asyncio.to_thread(
            invoke_graph,
            query=body.message,
            history=history,
            user_id=current_user["id"],
            conversation_id=body.conversation_id,
            has_documents=has_documents,
        )
    except Exception as e:
        logger.error("[Chat] Exception: %s", str(e))
        raise HTTPException(status_code=500, detail="An error occurred while processing your request. Please try again.")

    await save_message(pool, body.conversation_id, "assistant", result["answer"])

    try:
        current_title = await get_conversation_title(pool, body.conversation_id)
        if current_title == "New Conversation":
            asyncio.create_task(auto_generate_title(pool, body.conversation_id, body.message))
    except Exception:
        pass

    return ChatResponse(
        conversation_id=body.conversation_id,
        answer=result["answer"],
        route_taken=result["route"],
    )


@router.post("/chat/stream")
@limiter.limit("20/minute")
async def chat_stream(
    request: Request,
    body: ChatRequest,
    pool: asyncpg.Pool = Depends(get_pool),
    current_user: dict = Depends(get_current_user),
):
    """
    Streaming chat endpoint via Server-Sent Events (SSE).
    """
    owns = await verify_conversation_ownership(pool, body.conversation_id, current_user["id"])
    if not owns:
        raise HTTPException(status_code=404, detail="Conversation not found.")

    history, has_documents = await asyncio.gather(
        get_history(pool, body.conversation_id, limit=20),
        get_conversation_has_documents(pool, body.conversation_id),
    )

    await save_message(pool, body.conversation_id, "user", body.message)

    user_tz = request.headers.get("x-user-timezone")

    async def event_generator():
        full_answer = []
        stream_error = False

        try:
            async for evt in astream_graph_events(
                query=body.message,
                history=history,
                user_id=current_user["id"],
                conversation_id=body.conversation_id,
                has_documents=has_documents,
                user_tz=user_tz,
            ):
                if await request.is_disconnected():
                    break

                event_type = evt.get("event", "message")
                data = evt.get("data", {})

                if event_type == "token":
                    content = data.get("content", "")
                    if content:
                        full_answer.append(content)

                yield f"event: {event_type}\ndata: {json.dumps(data)}\n\n"

        except Exception as err:
            stream_error = True
            logger.error("[Chat Stream] Exception: %s", str(err))
            yield f"event: error\ndata: {json.dumps({'message': 'An error occurred while processing your request. Please try again.'})}\n\n"

        finally:
            # Always persist whatever was generated — even partial responses on error.
            # This prevents orphaned user messages with no assistant reply.
            final_text = "".join(full_answer)
            if final_text:
                try:
                    await save_message(pool, body.conversation_id, "assistant", final_text)
                except Exception:
                    logger.warning("[Chat Stream] Failed to persist assistant message.")

            if not stream_error:
                try:
                    current_title = await get_conversation_title(pool, body.conversation_id)
                    if current_title == "New Conversation":
                        asyncio.create_task(auto_generate_title(pool, body.conversation_id, body.message))
                except Exception:
                    pass

    return StreamingResponse(event_generator(), media_type="text/event-stream")
