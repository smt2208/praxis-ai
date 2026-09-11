"""
app/schemas/chat.py

Chat request and response models.
"""
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """Payload for initiating or continuing an SSE chat streaming session."""
    conversation_id: str = Field(description="UUID of the conversation thread.")
    message: str = Field(default="", description="User query text. Can be empty if images are provided.")
    images: list[str] = Field(default_factory=list, description="List of base64 data URIs or image URLs, max 5 images.")


class MessageResponse(BaseModel):
    """Historical message representation returned by conversation history endpoints."""
    role: str = Field(description="Message author role: 'user', 'assistant', or 'system'.")
    content: str = Field(description="Raw markdown message content.")
    images: list[str] = Field(default_factory=list, description="List of image URLs or URIs attached to this message.")
    metadata: dict = Field(default_factory=dict, description="Arbitrary message metadata including image summaries.")
