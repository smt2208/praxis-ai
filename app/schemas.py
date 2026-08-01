from pydantic import BaseModel, Field, EmailStr
from typing import Optional
from datetime import datetime


# -----------------------------------------------------------------------
# Auth
# -----------------------------------------------------------------------

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, description="Minimum 8 characters")

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    """Returned on register and login. Client stores both tokens."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    needs_verification: bool = False  # True right after registration — tells UI to show "check inbox"

class RefreshRequest(BaseModel):
    """Send the stored refresh_token to get a new access_token."""
    refresh_token: str

class LogoutRequest(BaseModel):
    """Send the refresh_token to revoke it on the server."""
    refresh_token: str
    logout_all_devices: bool = False   # True → revoke ALL tokens for this user

class UserMeResponse(BaseModel):
    user_id: str
    email: str
    is_verified: bool = False


class VerifyEmailRequest(BaseModel):
    token: str


# -----------------------------------------------------------------------
# Conversations
# -----------------------------------------------------------------------

class ConversationCreateRequest(BaseModel):
    title: str = "New Conversation"      # user_id now comes from JWT

class ConversationResponse(BaseModel):
    conversation_id: str

class ConversationListItem(BaseModel):
    conversation_id: str
    title: str
    created_at: datetime
    updated_at: datetime

class ConversationListResponse(BaseModel):
    conversations: list[ConversationListItem]


# -----------------------------------------------------------------------
# Chat
# -----------------------------------------------------------------------

class ChatRequest(BaseModel):
    conversation_id: str
    message: str                          # user_id removed — read from JWT


class ChatResponse(BaseModel):
    conversation_id: str
    answer: str
    route_taken: str   # Transparency: which department handled this


# -----------------------------------------------------------------------
# Messages
# -----------------------------------------------------------------------

class MessageResponse(BaseModel):
    role: str
    content: str


# -----------------------------------------------------------------------
# Ingestion
# -----------------------------------------------------------------------

class IngestRequest(BaseModel):
    """Trigger document ingestion from an S3 URL or local path."""
    source_url: str = Field(..., description="S3 URL or public URL of the document to ingest")
    conversation_id: str = Field(..., description="The conversation ID to scope this document to")


class IngestResponse(BaseModel):
    message: str
    documents_stored: int


# -----------------------------------------------------------------------
# Health
# -----------------------------------------------------------------------

class HealthResponse(BaseModel):
    status: str
    database: str
    qdrant: str
