"""
Product Application DTOs — data transfer objects for the application layer.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.domain.entities.product import Product


@dataclass(frozen=True)
class CreateProductDTO:
    name: str
    description: str
    price: float
    stock: int
    owner_id: int


@dataclass(frozen=True)
class UpdateProductDTO:
    name: str | None = None
    description: str | None = None
    price: float | None = None
    stock: int | None = None


@dataclass(frozen=True)
class ProductDTO:
    id: int
    name: str
    description: str
    price: float
    stock: int
    owner_id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_entity(cls, product: Product) -> ProductDTO:
        return cls(
            id=product.id,  # type: ignore[arg-type]
            name=str(product.name),
            description=product.description,
            price=float(product.price.amount),
            stock=product.stock,
            owner_id=product.owner_id,
            is_active=product.is_active,
            created_at=product.created_at,
            updated_at=product.updated_at,
        )
