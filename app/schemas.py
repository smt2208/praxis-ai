from pydantic import BaseModel, Field
from typing import Optional


# --- Requests ----------------------------------------------------------

class UserCreateRequest(BaseModel):
    email: str

class ConversationCreateRequest(BaseModel):
    user_id: str
    title: str = "New Conversation"

class ChatRequest(BaseModel):
    conversation_id: str
    user_id: str
    message: str

class IngestRequest(BaseModel):
    """Trigger document ingestion from an S3 URL or local path."""
    source_url: str = Field(..., description="S3 URL or public URL of the document to ingest")
    collection_name: Optional[str] = None  # Defaults to settings.qdrant_collection_name


# --- Responses ---------------------------------------------------------

class UserResponse(BaseModel):
    user_id: str
    email: str

class ConversationResponse(BaseModel):
    conversation_id: str

class ChatResponse(BaseModel):
    conversation_id: str
    answer: str
    route_taken: str   # Transparency: which department handled this

class MessageResponse(BaseModel):
    role: str
    content: str

class IngestResponse(BaseModel):
    message: str
    documents_stored: int

class HealthResponse(BaseModel):
    status: str
    database: str
    qdrant: str
