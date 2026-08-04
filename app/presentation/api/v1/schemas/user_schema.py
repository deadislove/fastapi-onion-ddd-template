"""
User Pydantic request/response schemas for the presentation layer.
Annotated with Swagger/OpenAPI examples.
"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator

# ─── Request Schemas ──────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    email: EmailStr = Field(
        ...,
        examples=["alice@example.com"],
        description="User's email address.",
    )
    password: str = Field(
        ...,
        min_length=8,
        examples=["Str0ngP@ssword!"],
        description="Password (minimum 8 characters).",
    )
    full_name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        examples=["Alice Smith"],
        description="User's full name.",
    )

    @field_validator("email")
    @classmethod
    def lowercase_email(cls, v: str) -> str:
        return v.strip().lower()


class LoginRequest(BaseModel):
    email: EmailStr = Field(
        ...,
        examples=["alice@example.com"],
        description="Registered email address.",
    )
    password: str = Field(
        ...,
        examples=["Str0ngP@ssword!"],
        description="Account password.",
    )


class UpdateUserRequest(BaseModel):
    full_name: str | None = Field(
        default=None,
        min_length=1,
        max_length=255,
        examples=["Alice Johnson"],
        description="Updated full name.",
    )


class RefreshTokenRequest(BaseModel):
    refresh_token: str = Field(
        ...,
        description="A valid refresh token issued during login.",
    )


class LogoutRequest(BaseModel):
    refresh_token: str | None = Field(
        default=None,
        description="Refresh token to revoke alongside the current access token (optional).",
    )


# ─── Response Schemas ─────────────────────────────────────────────────────────

class UserResponse(BaseModel):
    id: int = Field(..., examples=[1])
    email: str = Field(..., examples=["alice@example.com"])
    full_name: str = Field(..., examples=["Alice Smith"])
    is_active: bool = Field(..., examples=[True])
    is_superuser: bool = Field(..., examples=[False])
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    access_token: str = Field(..., description="JWT access token.")
    refresh_token: str = Field(..., description="JWT refresh token.")
    token_type: str = Field(default="bearer", examples=["bearer"])


class MessageResponse(BaseModel):
    message: str = Field(..., examples=["Operation completed successfully."])


class ErrorResponse(BaseModel):
    """RFC 7807 Problem Details error response."""
    type: str = Field(..., examples=["https://httpstatuses.com/400"])
    title: str = Field(..., examples=["Bad Request"])
    status: int = Field(..., examples=[400])
    detail: str = Field(..., examples=["Validation failed."])
    instance: str | None = Field(default=None, examples=["/api/v1/users"])
