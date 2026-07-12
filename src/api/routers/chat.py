from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from src.db.session import get_db
from src.core.security import get_current_user
from src.db.models import User
from src.schemas.chat import ConversationCreate, ConversationResponse, MessageCreate, MessageResponse
from src.services.chat_service import create_conversation, get_user_conversations, process_chat_message, delete_conversation
import uuid
from typing import List

router = APIRouter(prefix="/chat", tags=["chat"])

@router.post("/conversations", response_model=ConversationResponse)
async def start_conversation(
    conv: ConversationCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    return await create_conversation(db, current_user.id, conv.title)

@router.get("/conversations", response_model=List[ConversationResponse])
async def list_conversations(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    return await get_user_conversations(db, current_user.id)

@router.delete("/conversations/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation_route(
    conversation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    try:
        await delete_conversation(db, current_user.id, conversation_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

from fastapi.responses import StreamingResponse

@router.post("/conversations/{conversation_id}/messages")
async def send_message(
    conversation_id: uuid.UUID,
    msg: MessageCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    try:
        if msg.stream:
            from src.services.chat_service import stream_chat_message
            return StreamingResponse(
                stream_chat_message(db, current_user.id, conversation_id, msg),
                media_type="text/event-stream"
            )
        else:
            response_msg = await process_chat_message(db, current_user.id, conversation_id, msg)
            return response_msg
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")
