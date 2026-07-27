import asyncio
import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Request

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

from app.auth.dependencies import get_current_user
from app.dependencies import get_pool
from app.middleware.rate_limit import limiter
from app.database import (
    get_history, save_message, get_conversation_has_documents,
    get_conversation_title, update_conversation_title,
    verify_conversation_ownership,
)
from app.schemas import ChatRequest, ChatResponse
from agents.orchestrator import invoke_graph

router = APIRouter(prefix="/api/v1", tags=["Chat"])


@router.post("/chat", response_model=ChatResponse)
@limiter.limit("20/minute")            # 20 messages per minute per user
async def chat(
    request: Request,                  # required by slowapi
    body: ChatRequest,
    pool: asyncpg.Pool = Depends(get_pool),
    current_user: dict = Depends(get_current_user),
):
    """
    Main chat endpoint.
    - Reads user identity from JWT.
    - Fetches clean history from DB, runs the multi-agent graph, persists results.
    """
    # 0. Verify the user owns this conversation
    owns = await verify_conversation_ownership(pool, body.conversation_id, current_user["id"])
    if not owns:
        raise HTTPException(status_code=404, detail="Conversation not found.")

    # 1. Fetch conversation history + check if conversation has documents (one concurrent batch)
    history, has_documents = await asyncio.gather(
        get_history(pool, body.conversation_id, limit=20),
        get_conversation_has_documents(pool, body.conversation_id),
    )

    # Persist the user's turn first (never lost even if the graph fails)
    await save_message(pool, body.conversation_id, "user", body.message)

    # 2. Run the stateless multi-agent graph
    try:
        # Offload the synchronous LangGraph execution to a worker thread
        result = await asyncio.to_thread(
            invoke_graph,
            query=body.message,
            history=history,
            user_id=current_user["id"],
            conversation_id=body.conversation_id,
            has_documents=has_documents,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent error: {str(e)}")

    # 3. Persist the assistant reply after generation succeeds
    await save_message(pool, body.conversation_id, "assistant", result["answer"])

    # 4. Auto-generate conversation title if still named 'New Conversation'
    try:
        current_title = await get_conversation_title(pool, body.conversation_id)
        if current_title == "New Conversation":
            asyncio.create_task(_auto_generate_title(pool, body.conversation_id, body.message))
    except Exception:
        pass

    return ChatResponse(
        conversation_id=body.conversation_id,
        answer=result["answer"],
        route_taken=result["route"],
    )


async def _auto_generate_title(pool: asyncpg.Pool, conversation_id: str, first_message: str):
    """Background task to generate a descriptive 3-5 word title like ChatGPT/Claude."""
    try:
        title_llm = ChatOpenAI(model="gpt-5.4-mini-2026-03-17", temperature=0.5)
        response = await asyncio.to_thread(
            title_llm.invoke,
            [
                SystemMessage(content="Create a concise, 3-5 word title summarizing the user's prompt. Do NOT use quotes or trailing punctuation. Keep it short like a ChatGPT sidebar title."),
                HumanMessage(content=first_message),
            ]
        )
        new_title = response.content.strip().strip('"').strip("'")
        if new_title:
            await update_conversation_title(pool, conversation_id, new_title)
    except Exception as e:
        print(f"[auto-title] Warning: Could not auto-title conversation: {e}")
