"""
Product Application Facade — orchestrates product workflows, manages UoW, and handles DTO mapping.
Controllers call this facade instead of raw services or repositories.
"""
from __future__ import annotations

from app.application.dtos.product_dto import (
    CreateProductDTO,
    ProductDTO,
    UpdateProductDTO,
)
from app.application.services.product_service import ProductService
from app.domain.common.result import Err, Ok, Result
from app.domain.exceptions import DomainError


class ProductFacade:
    """
    Application facade for product-related workflows.
    Orchestrates ProductService and maps domain entities to DTOs.
    """

    def __init__(self, product_service: ProductService) -> None:
        self._product_service = product_service

    async def create_product(self, dto: CreateProductDTO) -> Result[ProductDTO, DomainError]:
        result = await self._product_service.create_product(
            name=dto.name,
            description=dto.description,
            price=dto.price,
            stock=dto.stock,
            owner_id=dto.owner_id,
        )
        if result.is_err():
            return Err(result.unwrap_err())
        return Ok(ProductDTO.from_entity(result.unwrap()))

    async def get_product(self, product_id: int) -> Result[ProductDTO, DomainError]:
        result = await self._product_service.get_product_by_id(product_id)
        if result.is_err():
            return Err(result.unwrap_err())
        return Ok(ProductDTO.from_entity(result.unwrap()))

    async def get_all_products(self, skip: int = 0, limit: int = 100) -> Result[list[ProductDTO], DomainError]:
        result = await self._product_service.get_all_products(skip=skip, limit=limit)
        if result.is_err():
            return Err(result.unwrap_err())
        return Ok([ProductDTO.from_entity(p) for p in result.unwrap()])

    async def get_products_by_owner(
        self, owner_id: int, skip: int = 0, limit: int = 100
    ) -> Result[list[ProductDTO], DomainError]:
        result = await self._product_service.get_products_by_owner(
            owner_id=owner_id, skip=skip, limit=limit
        )
        if result.is_err():
            return Err(result.unwrap_err())
        return Ok([ProductDTO.from_entity(p) for p in result.unwrap()])

    async def update_product(
        self, product_id: int, owner_id: int, dto: UpdateProductDTO
    ) -> Result[ProductDTO, DomainError]:
        result = await self._product_service.update_product(
            product_id=product_id,
            owner_id=owner_id,
            name=dto.name,
            description=dto.description,
            price=dto.price,
            stock=dto.stock,
        )
        if result.is_err():
            return Err(result.unwrap_err())
        return Ok(ProductDTO.from_entity(result.unwrap()))

    async def delete_product(self, product_id: int, owner_id: int) -> Result[bool, DomainError]:
        return await self._product_service.delete_product(product_id=product_id, owner_id=owner_id)
