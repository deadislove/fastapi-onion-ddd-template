"""
Product Domain Service — core business rules for product management.
Returns Result[T, DomainError] for all operations.
"""
from __future__ import annotations

from decimal import Decimal

from app.application.services.event_dispatcher import IEventDispatcher
from app.domain.common.result import Err, Ok, Result
from app.domain.entities.product import Product
from app.domain.events import ProductDeletedEvent
from app.domain.exceptions import DomainError
from app.domain.repositories.product_repository import IProductRepository
from app.domain.repositories.user_repository import IUserRepository


class ProductService:
    """Domain service encapsulating product business rules."""

    def __init__(
        self,
        product_repository: IProductRepository,
        user_repository: IUserRepository,
        event_dispatcher: IEventDispatcher,
    ) -> None:
        self._product_repo = product_repository
        self._user_repo = user_repository
        self._dispatcher = event_dispatcher

    async def get_product_by_id(self, product_id: int) -> Result[Product, DomainError]:
        product = await self._product_repo.get_by_id(product_id)
        if product is None:
            return Err(DomainError.product_not_found(product_id))
        return Ok(product)

    async def get_all_products(self, skip: int = 0, limit: int = 100) -> Result[list[Product], DomainError]:
        products = await self._product_repo.get_all(skip=skip, limit=limit)
        return Ok(products)

    async def get_products_by_owner(
        self, owner_id: int, skip: int = 0, limit: int = 100
    ) -> Result[list[Product], DomainError]:
        # Verify owner exists
        owner = await self._user_repo.get_by_id(owner_id)
        if owner is None:
            return Err(DomainError.user_not_found(owner_id))

        products = await self._product_repo.get_by_owner(owner_id, skip=skip, limit=limit)
        return Ok(products)

    async def create_product(
        self,
        name: str,
        description: str,
        price: Decimal | float | str,
        stock: int,
        owner_id: int,
    ) -> Result[Product, DomainError]:
        # Verify owner exists
        owner = await self._user_repo.get_by_id(owner_id)
        if owner is None:
            return Err(DomainError.user_not_found(owner_id))

        # Check for duplicate product name per owner
        if await self._product_repo.exists_by_name(name.strip(), owner_id):
            return Err(DomainError.product_already_exists(name))

        # Create domain entity
        result = Product.create(
            name=name,
            description=description,
            price=price,
            stock=stock,
            owner_id=owner_id,
        )
        if result.is_err():
            return result

        product = result.unwrap()
        # repo.create() calls mark_created() on the *returned* entity — see UserService
        # for why the event has to be collected from the post-save instance.
        saved_product = await self._product_repo.create(product)
        await self._dispatcher.publish_all(saved_product.collect_events())
        return Ok(saved_product)

    async def update_product(
        self,
        product_id: int,
        owner_id: int,
        name: str | None = None,
        description: str | None = None,
        price: Decimal | float | str | None = None,
        stock: int | None = None,
    ) -> Result[Product, DomainError]:
        product = await self._product_repo.get_by_id(product_id)
        if product is None:
            return Err(DomainError.product_not_found(product_id))

        # Ownership check
        if product.owner_id != owner_id:
            return Err(DomainError.unauthorized("You do not own this product."))

        update_result = product.update(
            name=name,
            description=description,
            price=price,
            stock=stock,
        )
        if update_result.is_err():
            return update_result

        # repo.update() returns a *new* entity mapped from the ORM row — collect the
        # event from `product`, the instance whose `.update()` call actually recorded it.
        updated_product = await self._product_repo.update(product)
        await self._dispatcher.publish_all(product.collect_events())
        return Ok(updated_product)

    async def delete_product(self, product_id: int, owner_id: int) -> Result[bool, DomainError]:
        product = await self._product_repo.get_by_id(product_id)
        if product is None:
            return Err(DomainError.product_not_found(product_id))

        # Ownership check
        if product.owner_id != owner_id:
            return Err(DomainError.unauthorized("You do not own this product."))

        deleted = await self._product_repo.delete(product_id)
        if deleted:
            await self._dispatcher.publish(ProductDeletedEvent(product_id=product_id))
        return Ok(deleted)
