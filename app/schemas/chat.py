"""
app/schemas/chat.py

Chat request and response models.
"""
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    conversation_id: str
    message: str = ""
    images: list[str] = Field(default=[], description="Base64 data URIs, max 5 images")


class ChatResponse(BaseModel):
    conversation_id: str
    answer: str
    route_taken: str


class MessageResponse(BaseModel):
    role: str
    content: str
