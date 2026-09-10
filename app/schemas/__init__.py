"""
app/schemas — Pydantic request/response models.

Re-exports all models so consumers can use:
    from app.schemas import ChatRequest, TokenResponse, ...
"""
from app.schemas.auth import (
    RegisterRequest,
    LoginRequest,
    TokenResponse,
    RefreshRequest,
    LogoutRequest,
    UserMeResponse,
    VerifyEmailRequest,
    ForgotPasswordRequest,
    ResetPasswordRequest,
    UpdateProfileRequest,
)

from app.schemas.chat import (
    ChatRequest,
    MessageResponse,
)

from app.schemas.conversations import (
    ConversationCreateRequest,
    ConversationResponse,
    ConversationListItem,
    ConversationListResponse,
)

from app.schemas.ingest import (
    IngestRequest,
    IngestResponse,
)

from app.schemas.health import (
    HealthResponse,
)

from app.schemas.memory import (
    MemoryToggleRequest,
)

__all__ = [
    "RegisterRequest",
    "LoginRequest",
    "TokenResponse",
    "RefreshRequest",
    "LogoutRequest",
    "UserMeResponse",
    "VerifyEmailRequest",
    "ForgotPasswordRequest",
    "ResetPasswordRequest",
    "UpdateProfileRequest",
    "ChatRequest",
    "MessageResponse",
    "ConversationCreateRequest",
    "ConversationResponse",
    "ConversationListItem",
    "ConversationListResponse",
    "IngestRequest",
    "IngestResponse",
    "HealthResponse",
    "MemoryToggleRequest",
]

