"""
Domain Events — represent something that happened in the domain.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID, uuid4


@dataclass(frozen=True)
class DomainEvent:
    event_id: UUID = field(default_factory=uuid4)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True)
class UserRegisteredEvent(DomainEvent):
    user_id: int = 0
    email: str = ""


@dataclass(frozen=True)
class UserUpdatedEvent(DomainEvent):
    user_id: int = 0


@dataclass(frozen=True)
class UserDeletedEvent(DomainEvent):
    user_id: int = 0


@dataclass(frozen=True)
class ProductCreatedEvent(DomainEvent):
    product_id: int = 0
    owner_id: int = 0
    name: str = ""


@dataclass(frozen=True)
class ProductUpdatedEvent(DomainEvent):
    product_id: int = 0


@dataclass(frozen=True)
class ProductDeletedEvent(DomainEvent):
    product_id: int = 0
