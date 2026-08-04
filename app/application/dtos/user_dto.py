"""
User Application DTOs — data transfer objects for the application layer.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.domain.entities.user import User


@dataclass(frozen=True)
class CreateUserDTO:
    email: str
    password: str
    full_name: str
    is_superuser: bool = False


@dataclass(frozen=True)
class UpdateUserDTO:
    full_name: str | None = None


@dataclass(frozen=True)
class UserDTO:
    id: int
    email: str
    full_name: str
    is_active: bool
    is_superuser: bool
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_entity(cls, user: User) -> UserDTO:
        return cls(
            id=user.id,  # type: ignore[arg-type]
            email=str(user.email),
            full_name=user.full_name,
            is_active=user.is_active,
            is_superuser=user.is_superuser,
            created_at=user.created_at,
            updated_at=user.updated_at,
        )


@dataclass(frozen=True)
class LoginDTO:
    email: str
    password: str


@dataclass(frozen=True)
class TokenDTO:
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


@dataclass(frozen=True)
class RefreshTokenDTO:
    refresh_token: str
