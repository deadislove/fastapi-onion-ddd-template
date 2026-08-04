"""
UserProduct Application Facade — orchestrates cross-aggregate workflows between User and Product.
"""
from __future__ import annotations

from app.application.dtos.product_dto import CreateProductDTO, ProductDTO
from app.application.dtos.user_dto import UserDTO
from app.application.facades.product_facade import ProductFacade
from app.application.facades.user_facade import UserFacade
from app.domain.common.result import Err, Ok, Result
from app.domain.exceptions import DomainError


class UserProductFacade:
    """
    Cross-aggregate facade for workflows that span both User and Product domains.
    Example: creating a product on behalf of the currently authenticated user.
    """

    def __init__(
        self,
        user_facade: UserFacade,
        product_facade: ProductFacade,
    ) -> None:
        self._user_facade = user_facade
        self._product_facade = product_facade

    async def create_product_for_user(
        self,
        owner_id: int,
        name: str,
        description: str,
        price: float,
        stock: int,
    ) -> Result[ProductDTO, DomainError]:
        """Create a product owned by the given user, verifying the user exists first."""
        # Verify user exists
        user_result = await self._user_facade.get_user(owner_id)
        if user_result.is_err():
            return Err(user_result.unwrap_err())

        dto = CreateProductDTO(
            name=name,
            description=description,
            price=price,
            stock=stock,
            owner_id=owner_id,
        )
        return await self._product_facade.create_product(dto)

    async def get_user_with_products(
        self, user_id: int, skip: int = 0, limit: int = 100
    ) -> Result[tuple[UserDTO, list[ProductDTO]], DomainError]:
        """Retrieve a user along with all their products."""
        user_result = await self._user_facade.get_user(user_id)
        if user_result.is_err():
            return Err(user_result.unwrap_err())

        products_result = await self._product_facade.get_products_by_owner(
            owner_id=user_id, skip=skip, limit=limit
        )
        if products_result.is_err():
            return Err(products_result.unwrap_err())

        return Ok((user_result.unwrap(), products_result.unwrap()))
