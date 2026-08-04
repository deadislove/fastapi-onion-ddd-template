"""
User Domain Service — core business rules for user management.
Returns Result[T, DomainError] for all operations.
"""
from __future__ import annotations

from app.application.services.event_dispatcher import IEventDispatcher
from app.domain.common.result import Err, Ok, Result
from app.domain.entities.user import User
from app.domain.events import UserDeletedEvent
from app.domain.exceptions import DomainError
from app.domain.repositories.user_repository import IUserRepository


class UserService:
    """Domain service encapsulating user business rules."""

    def __init__(self, user_repository: IUserRepository, event_dispatcher: IEventDispatcher) -> None:
        self._repo = user_repository
        self._dispatcher = event_dispatcher

    async def get_user_by_id(self, user_id: int) -> Result[User, DomainError]:
        user = await self._repo.get_by_id(user_id)
        if user is None:
            return Err(DomainError.user_not_found(user_id))
        return Ok(user)

    async def get_user_by_email(self, email: str) -> Result[User, DomainError]:
        user = await self._repo.get_by_email(email.strip().lower())
        if user is None:
            return Err(DomainError.user_not_found(email))
        return Ok(user)

    async def get_all_users(self, skip: int = 0, limit: int = 100) -> Result[list[User], DomainError]:
        users = await self._repo.get_all(skip=skip, limit=limit)
        return Ok(users)

    async def register_user(
        self,
        email: str,
        hashed_password: str,
        full_name: str,
        is_superuser: bool = False,
    ) -> Result[User, DomainError]:
        # Check for duplicate email
        if await self._repo.exists_by_email(email.strip().lower()):
            return Err(DomainError.user_already_exists(email))

        # Create domain entity
        result = User.create(
            email=email,
            hashed_password=hashed_password,
            full_name=full_name,
            is_superuser=is_superuser,
        )
        if result.is_err():
            return result

        user = result.unwrap()
        # repo.create() calls mark_registered() on the *returned* entity — the id is
        # None (and thus unusable in the event) until the INSERT is flushed, so the
        # event is queued on saved_user, not on the pre-save `user` instance.
        saved_user = await self._repo.create(user)
        await self._dispatcher.publish_all(saved_user.collect_events())
        return Ok(saved_user)

    async def update_user(
        self,
        user_id: int,
        full_name: str | None = None,
    ) -> Result[User, DomainError]:
        user = await self._repo.get_by_id(user_id)
        if user is None:
            return Err(DomainError.user_not_found(user_id))

        update_result = user.update_profile(full_name=full_name)
        if update_result.is_err():
            return update_result

        # repo.update() maps the ORM row back into a *new* entity instance, which never
        # saw update_profile()'s event — collect from `user`, the instance that recorded it.
        updated_user = await self._repo.update(user)
        await self._dispatcher.publish_all(user.collect_events())
        return Ok(updated_user)

    async def delete_user(self, user_id: int) -> Result[bool, DomainError]:
        user = await self._repo.get_by_id(user_id)
        if user is None:
            return Err(DomainError.user_not_found(user_id))

        deleted = await self._repo.delete(user_id)
        if deleted:
            await self._dispatcher.publish(UserDeletedEvent(user_id=user_id))
        return Ok(deleted)

    async def deactivate_user(self, user_id: int) -> Result[User, DomainError]:
        user = await self._repo.get_by_id(user_id)
        if user is None:
            return Err(DomainError.user_not_found(user_id))

        user.deactivate()
        updated_user = await self._repo.update(user)
        return Ok(updated_user)
