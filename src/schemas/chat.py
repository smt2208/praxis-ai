from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
from typing import List, Optional

class MessageCreate(BaseModel):
    content: str
    # Optional parameters for generation behavior
    model: str = "gpt-5.4-mini-2026-03-17"
    enable_web_search: bool = False
    generate_document: bool = False
    stream: bool = False

class MessageResponse(BaseModel):
    id: UUID
    conversation_id: UUID
    role: str
    content: str
    created_at: datetime

    class Config:
        from_attributes = True

class ConversationCreate(BaseModel):
    title: str

class ConversationResponse(BaseModel):
    id: UUID
    user_id: UUID
    title: str
    created_at: datetime

    class Config:
        from_attributes = True
