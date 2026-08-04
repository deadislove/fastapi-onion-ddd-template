"""
Product aggregate root — pure domain entity with no ORM or infrastructure dependencies.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal

from app.domain.common.result import Err, Ok, Result
from app.domain.events import ProductCreatedEvent, ProductUpdatedEvent
from app.domain.exceptions import DomainError
from app.domain.value_objects import Money, ProductName


@dataclass
class Product:
    """Product aggregate root. Owned by a User (One-to-Many)."""

    id: int | None
    name: ProductName
    description: str
    price: Money
    stock: int
    owner_id: int
    is_active: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    # Domain events collected during aggregate lifecycle
    _domain_events: list = field(default_factory=list, repr=False, compare=False)

    @classmethod
    def create(
        cls,
        name: str,
        description: str,
        price: Decimal | float | str,
        stock: int,
        owner_id: int,
    ) -> Result[Product, DomainError]:
        name_result = ProductName.create(name)
        if name_result.is_err():
            return name_result  # type: ignore[return-value]
        price_result = Money.create(price)
        if price_result.is_err():
            return price_result  # type: ignore[return-value]
        if stock < 0:
            return Err(DomainError.validation_error("Stock cannot be negative."))
        if owner_id <= 0:
            return Err(DomainError.validation_error("Valid owner ID is required."))

        product = cls(
            id=None,
            name=name_result.unwrap(),
            description=description.strip() if description else "",
            price=price_result.unwrap(),
            stock=stock,
            owner_id=owner_id,
        )
        return Ok(product)

    def mark_created(self) -> None:
        """
        Records the domain event for a newly persisted product. Called by the repository
        once the entity has a real ID — `id` is None until the INSERT is flushed, so this
        can't happen inside `create()` itself.
        """
        assert self.id is not None, "mark_created() must be called after the entity is persisted"
        self._domain_events.append(
            ProductCreatedEvent(product_id=self.id, owner_id=self.owner_id, name=str(self.name))
        )

    def update(
        self,
        name: str | None = None,
        description: str | None = None,
        price: Decimal | float | str | None = None,
        stock: int | None = None,
    ) -> Result[Product, DomainError]:
        if name is not None:
            name_result = ProductName.create(name)
            if name_result.is_err():
                return name_result  # type: ignore[return-value]
            self.name = name_result.unwrap()
        if description is not None:
            self.description = description.strip()
        if price is not None:
            price_result = Money.create(price)
            if price_result.is_err():
                return price_result  # type: ignore[return-value]
            self.price = price_result.unwrap()
        if stock is not None:
            if stock < 0:
                return Err(DomainError.validation_error("Stock cannot be negative."))
            self.stock = stock
        self.updated_at = datetime.now(UTC)
        # No event to record for an entity that was never persisted (id is None) —
        # e.g. Product.create() followed by .update() before the repository saves it.
        if self.id is not None:
            self._domain_events.append(ProductUpdatedEvent(product_id=self.id))
        return Ok(self)

    def reduce_stock(self, quantity: int) -> Result[Product, DomainError]:
        if quantity <= 0:
            return Err(DomainError.validation_error("Quantity must be positive."))
        if self.stock < quantity:
            return Err(DomainError.insufficient_stock(self.id or 0, quantity, self.stock))
        self.stock -= quantity
        self.updated_at = datetime.now(UTC)
        if self.id is not None:
            self._domain_events.append(ProductUpdatedEvent(product_id=self.id))
        return Ok(self)

    def deactivate(self) -> None:
        self.is_active = False
        self.updated_at = datetime.now(UTC)

    def collect_events(self) -> list:
        events = list(self._domain_events)
        self._domain_events.clear()
        return events

    def __repr__(self) -> str:
        return f"Product(id={self.id}, name={self.name!r}, price={self.price}, stock={self.stock})"
