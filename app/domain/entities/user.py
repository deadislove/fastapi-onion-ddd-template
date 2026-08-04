"""
User aggregate root — pure domain entity with no ORM or infrastructure dependencies.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from app.domain.common.result import Err, Ok, Result
from app.domain.events import UserRegisteredEvent, UserUpdatedEvent
from app.domain.exceptions import DomainError
from app.domain.value_objects import Email, Password

if TYPE_CHECKING:
    from app.domain.entities.product import Product


@dataclass
class User:
    """User aggregate root."""

    id: int | None
    email: Email
    hashed_password: Password
    full_name: str
    is_active: bool = True
    is_superuser: bool = False
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    products: list[Product] = field(default_factory=list)

    # Domain events collected during aggregate lifecycle
    _domain_events: list = field(default_factory=list, repr=False, compare=False)

    @classmethod
    def create(
        cls,
        email: str,
        hashed_password: str,
        full_name: str,
        is_superuser: bool = False,
    ) -> Result[User, DomainError]:
        email_result = Email.create(email)
        if email_result.is_err():
            return email_result  # type: ignore[return-value]
        if not hashed_password:
            return Err(DomainError.validation_error("Password is required."))
        if not full_name or not full_name.strip():
            return Err(DomainError.validation_error("Full name is required."))

        user = cls(
            id=None,
            email=email_result.unwrap(),
            hashed_password=Password.from_hash(hashed_password),
            full_name=full_name.strip(),
            is_superuser=is_superuser,
        )
        return Ok(user)

    def mark_registered(self) -> None:
        """
        Records the domain event for a newly persisted user. Called by the repository
        once the entity has a real ID — `id` is None until the INSERT is flushed, so this
        can't happen inside `create()` itself.
        """
        assert self.id is not None, "mark_registered() must be called after the entity is persisted"
        self._domain_events.append(UserRegisteredEvent(user_id=self.id, email=str(self.email)))

    def update_profile(self, full_name: str | None = None) -> Result[User, DomainError]:
        if full_name is not None:
            if not full_name.strip():
                return Err(DomainError.validation_error("Full name cannot be empty."))
            self.full_name = full_name.strip()
        self.updated_at = datetime.now(UTC)
        # No event to record for an entity that was never persisted (id is None).
        if self.id is not None:
            self._domain_events.append(UserUpdatedEvent(user_id=self.id))
        return Ok(self)

    def deactivate(self) -> None:
        self.is_active = False
        self.updated_at = datetime.now(UTC)

    def activate(self) -> None:
        self.is_active = True
        self.updated_at = datetime.now(UTC)

    def collect_events(self) -> list:
        events = list(self._domain_events)
        self._domain_events.clear()
        return events

    def __repr__(self) -> str:
        return f"User(id={self.id}, email={self.email!r}, is_active={self.is_active})"
