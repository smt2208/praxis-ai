from pydantic import BaseModel, ConfigDict, Field
from uuid import UUID
from datetime import datetime

class MessageCreate(BaseModel):
    content: str = Field(min_length=1)
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

    model_config = ConfigDict(from_attributes=True)

class ConversationCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)

class ConversationResponse(BaseModel):
    id: UUID
    user_id: UUID
    title: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
