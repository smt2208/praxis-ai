import asyncpg
from fastapi import APIRouter, Depends, HTTPException

from app.auth.dependencies import get_current_user
from app.dependencies import get_pool
from app.database import (
    get_history, create_conversation, get_conversations_by_user, delete_conversation,
    get_conversation_documents, verify_conversation_ownership,
    delete_conversation_qdrant_chunks,
)
from app.schemas import (
    ConversationCreateRequest, ConversationResponse,
    ConversationListItem, ConversationListResponse,
    MessageResponse,
)

router = APIRouter(prefix="/api/v1/conversations", tags=["Conversations"])



@router.get("", response_model=ConversationListResponse)
async def list_conversations(
    pool: asyncpg.Pool = Depends(get_pool),
    current_user: dict = Depends(get_current_user),
):
    """Return all conversations belonging to the authenticated user."""
    rows = await get_conversations_by_user(pool, current_user["id"])
    items = [
        ConversationListItem(
            conversation_id=str(r["id"]),
            title=r["title"],
            created_at=r["created_at"],
            updated_at=r["updated_at"],
        )
        for r in rows
    ]
    return ConversationListResponse(conversations=items)


@router.post("", response_model=ConversationResponse, status_code=201)
async def new_conversation(
    body: ConversationCreateRequest,
    pool: asyncpg.Pool = Depends(get_pool),
    current_user: dict = Depends(get_current_user),
):
    """Create a new conversation thread for the authenticated user."""
    conv_id = await create_conversation(pool, current_user["id"], body.title)
    return ConversationResponse(conversation_id=conv_id)


@router.get("/{conversation_id}/messages", response_model=list[MessageResponse])
async def get_messages(
    conversation_id: str,
    pool: asyncpg.Pool = Depends(get_pool),
    current_user: dict = Depends(get_current_user),
):
    """Fetch the message history for a conversation (must belong to the user)."""
    owns = await verify_conversation_ownership(pool, conversation_id, current_user["id"])
    if not owns:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    rows = await get_history(pool, conversation_id, limit=50)
    return [MessageResponse(role=r["role"], content=r["content"]) for r in rows]


@router.get("/{conversation_id}/documents", response_model=list[str])
async def get_documents(
    conversation_id: str,
    pool: asyncpg.Pool = Depends(get_pool),
    current_user: dict = Depends(get_current_user),
):
    """Fetch filenames of ingested documents for a conversation."""
    owns = await verify_conversation_ownership(pool, conversation_id, current_user["id"])
    if not owns:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    return await get_conversation_documents(pool, conversation_id)


@router.delete("/{conversation_id}", status_code=204)
async def delete_conv(
    conversation_id: str,
    pool: asyncpg.Pool = Depends(get_pool),
    current_user: dict = Depends(get_current_user),
):
    """Delete a conversation, its messages, and all its Qdrant vector chunks. Only the owner can delete."""
    # Purge Qdrant vector chunks first — so they're never left orphaned if Postgres succeeds.
    # Errors inside are caught/logged and won't block the user.
    await delete_conversation_qdrant_chunks(conversation_id)

    deleted = await delete_conversation(pool, conversation_id, current_user["id"])
    if not deleted:
        raise HTTPException(status_code=404, detail="Conversation not found.")

