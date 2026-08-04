"""
Product repository interface — abstract contract for the infrastructure layer.
Zero external dependencies (pure Python ABC).
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.entities.product import Product


class IProductRepository(ABC):
    """Abstract repository interface for Product aggregate."""

    @abstractmethod
    async def get_by_id(self, product_id: int) -> Product | None:
        """Retrieve a product by its primary key."""
        ...

    @abstractmethod
    async def get_by_name(self, name: str) -> Product | None:
        """Retrieve a product by its name."""
        ...

    @abstractmethod
    async def get_all(self, skip: int = 0, limit: int = 100) -> list[Product]:
        """Retrieve a paginated list of all products."""
        ...

    @abstractmethod
    async def get_by_owner(self, owner_id: int, skip: int = 0, limit: int = 100) -> list[Product]:
        """Retrieve all products belonging to a specific owner."""
        ...

    @abstractmethod
    async def create(self, product: Product) -> Product:
        """Persist a new product and return the saved entity (with ID assigned)."""
        ...

    @abstractmethod
    async def update(self, product: Product) -> Product:
        """Persist changes to an existing product."""
        ...

    @abstractmethod
    async def delete(self, product_id: int) -> bool:
        """Delete a product by ID. Returns True if deleted, False if not found."""
        ...

    @abstractmethod
    async def exists_by_name(self, name: str, owner_id: int) -> bool:
        """Check whether a product with the given name already exists for the owner."""
        ...
