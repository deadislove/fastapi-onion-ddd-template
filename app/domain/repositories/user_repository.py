"""
User repository interface — abstract contract for the infrastructure layer.
Zero external dependencies (pure Python ABC).
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.entities.user import User


class IUserRepository(ABC):
    """Abstract repository interface for User aggregate."""

    @abstractmethod
    async def get_by_id(self, user_id: int) -> User | None:
        """Retrieve a user by their primary key."""
        ...

    @abstractmethod
    async def get_by_email(self, email: str) -> User | None:
        """Retrieve a user by their email address."""
        ...

    @abstractmethod
    async def get_all(self, skip: int = 0, limit: int = 100) -> list[User]:
        """Retrieve a paginated list of all users."""
        ...

    @abstractmethod
    async def create(self, user: User) -> User:
        """Persist a new user and return the saved entity (with ID assigned)."""
        ...

    @abstractmethod
    async def update(self, user: User) -> User:
        """Persist changes to an existing user."""
        ...

    @abstractmethod
    async def delete(self, user_id: int) -> bool:
        """Delete a user by ID. Returns True if deleted, False if not found."""
        ...

    @abstractmethod
    async def exists_by_email(self, email: str) -> bool:
        """Check whether a user with the given email already exists."""
        ...
