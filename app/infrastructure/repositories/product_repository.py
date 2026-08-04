"""
SQLAlchemy v2 implementation of IProductRepository.
Maps between ORM ProductModel and domain Product entity.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.product import Product
from app.domain.repositories.product_repository import IProductRepository
from app.domain.value_objects import Money, ProductName
from app.infrastructure.database.models import ProductModel


def _to_entity(model: ProductModel) -> Product:
    """Convert ORM model to domain entity."""
    return Product(
        id=model.id,
        name=ProductName(value=model.name),
        description=model.description,
        price=Money(amount=model.price),
        stock=model.stock,
        owner_id=model.owner_id,
        is_active=model.is_active,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def _to_model(entity: Product) -> ProductModel:
    """Convert domain entity to ORM model (for create)."""
    return ProductModel(
        name=str(entity.name),
        description=entity.description,
        price=entity.price.amount,
        stock=entity.stock,
        owner_id=entity.owner_id,
        is_active=entity.is_active,
        created_at=entity.created_at,
        updated_at=entity.updated_at,
    )


class SQLAlchemyProductRepository(IProductRepository):
    """SQLAlchemy async implementation of the product repository."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, product_id: int) -> Product | None:
        result = await self._session.execute(
            select(ProductModel).where(ProductModel.id == product_id)
        )
        model = result.scalar_one_or_none()
        return _to_entity(model) if model else None

    async def get_by_name(self, name: str) -> Product | None:
        result = await self._session.execute(
            select(ProductModel).where(ProductModel.name == name)
        )
        model = result.scalar_one_or_none()
        return _to_entity(model) if model else None

    async def get_all(self, skip: int = 0, limit: int = 100) -> list[Product]:
        result = await self._session.execute(
            select(ProductModel).offset(skip).limit(limit)
        )
        models = result.scalars().all()
        return [_to_entity(m) for m in models]

    async def get_by_owner(self, owner_id: int, skip: int = 0, limit: int = 100) -> list[Product]:
        result = await self._session.execute(
            select(ProductModel)
            .where(ProductModel.owner_id == owner_id)
            .offset(skip)
            .limit(limit)
        )
        models = result.scalars().all()
        return [_to_entity(m) for m in models]

    async def create(self, product: Product) -> Product:
        model = _to_model(product)
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        saved = _to_entity(model)
        saved.mark_created()
        return saved

    async def update(self, product: Product) -> Product:
        result = await self._session.execute(
            select(ProductModel).where(ProductModel.id == product.id)
        )
        model = result.scalar_one_or_none()
        if model is None:
            raise ValueError(f"Product with id={product.id} not found for update.")

        model.name = str(product.name)
        model.description = product.description
        model.price = product.price.amount
        model.stock = product.stock
        model.is_active = product.is_active
        model.updated_at = product.updated_at

        await self._session.flush()
        await self._session.refresh(model)
        return _to_entity(model)

    async def delete(self, product_id: int) -> bool:
        result = await self._session.execute(
            select(ProductModel).where(ProductModel.id == product_id)
        )
        model = result.scalar_one_or_none()
        if model is None:
            return False
        await self._session.delete(model)
        await self._session.flush()
        return True

    async def exists_by_name(self, name: str, owner_id: int) -> bool:
        result = await self._session.execute(
            select(ProductModel.id).where(
                ProductModel.name == name,
                ProductModel.owner_id == owner_id,
            )
        )
        return result.scalar_one_or_none() is not None
