"""
SQLAlchemy v2 implementation of IUserRepository.
Maps between ORM UserModel and domain User entity.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.user import User
from app.domain.repositories.user_repository import IUserRepository
from app.domain.value_objects import Email, Password
from app.infrastructure.database.models import UserModel


def _to_entity(model: UserModel) -> User:
    """Convert ORM model to domain entity."""
    return User(
        id=model.id,
        email=Email(value=model.email),
        hashed_password=Password.from_hash(model.hashed_password),
        full_name=model.full_name,
        is_active=model.is_active,
        is_superuser=model.is_superuser,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def _to_model(entity: User) -> UserModel:
    """Convert domain entity to ORM model (for create)."""
    return UserModel(
        email=str(entity.email),
        hashed_password=entity.hashed_password.hashed_value,
        full_name=entity.full_name,
        is_active=entity.is_active,
        is_superuser=entity.is_superuser,
        created_at=entity.created_at,
        updated_at=entity.updated_at,
    )


class SQLAlchemyUserRepository(IUserRepository):
    """SQLAlchemy async implementation of the user repository."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, user_id: int) -> User | None:
        result = await self._session.execute(
            select(UserModel).where(UserModel.id == user_id)
        )
        model = result.scalar_one_or_none()
        return _to_entity(model) if model else None

    async def get_by_email(self, email: str) -> User | None:
        result = await self._session.execute(
            select(UserModel).where(UserModel.email == email.lower())
        )
        model = result.scalar_one_or_none()
        return _to_entity(model) if model else None

    async def get_all(self, skip: int = 0, limit: int = 100) -> list[User]:
        result = await self._session.execute(
            select(UserModel).offset(skip).limit(limit)
        )
        models = result.scalars().all()
        return [_to_entity(m) for m in models]

    async def create(self, user: User) -> User:
        model = _to_model(user)
        self._session.add(model)
        await self._session.flush()  # Flush to get the generated ID
        await self._session.refresh(model)
        saved = _to_entity(model)
        saved.mark_registered()
        return saved

    async def update(self, user: User) -> User:
        result = await self._session.execute(
            select(UserModel).where(UserModel.id == user.id)
        )
        model = result.scalar_one_or_none()
        if model is None:
            raise ValueError(f"User with id={user.id} not found for update.")

        model.email = str(user.email)
        model.hashed_password = user.hashed_password.hashed_value
        model.full_name = user.full_name
        model.is_active = user.is_active
        model.is_superuser = user.is_superuser
        model.updated_at = user.updated_at

        await self._session.flush()
        await self._session.refresh(model)
        return _to_entity(model)

    async def delete(self, user_id: int) -> bool:
        result = await self._session.execute(
            select(UserModel).where(UserModel.id == user_id)
        )
        model = result.scalar_one_or_none()
        if model is None:
            return False
        await self._session.delete(model)
        await self._session.flush()
        return True

    async def exists_by_email(self, email: str) -> bool:
        result = await self._session.execute(
            select(UserModel.id).where(UserModel.email == email.lower())
        )
        return result.scalar_one_or_none() is not None
