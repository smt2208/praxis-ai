"""
app/schemas/auth.py

Authentication request and response models.
"""
from pydantic import BaseModel, Field, EmailStr


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
    needs_verification: bool = False


class RefreshRequest(BaseModel):
    """Send the stored refresh_token to get a new access_token."""
    refresh_token: str


class LogoutRequest(BaseModel):
    """Send the refresh_token to revoke it on the server."""
    refresh_token: str
    logout_all_devices: bool = False


class UserMeResponse(BaseModel):
    user_id: str
    email: str
    is_verified: bool = False


class VerifyEmailRequest(BaseModel):
    token: str
