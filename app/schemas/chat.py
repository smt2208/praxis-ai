"""
app/schemas/chat.py

Chat request and response models.
"""
from pydantic import BaseModel


class ChatRequest(BaseModel):
    conversation_id: str
    message: str


class ChatResponse(BaseModel):
    conversation_id: str
    answer: str
    route_taken: str


class MessageResponse(BaseModel):
    role: str
    content: str
