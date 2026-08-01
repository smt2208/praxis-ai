"""
app/schemas/conversations.py

Conversation list and create models.
"""
from datetime import datetime
from pydantic import BaseModel


class ConversationCreateRequest(BaseModel):
    title: str = "New Conversation"


class ConversationResponse(BaseModel):
    conversation_id: str


class ConversationListItem(BaseModel):
    conversation_id: str
    title: str
    created_at: datetime
    updated_at: datetime


class ConversationListResponse(BaseModel):
    conversations: list[ConversationListItem]
