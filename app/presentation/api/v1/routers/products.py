"""
Product API router — versioned at /api/v1/products.
Handles product CRUD operations.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, status

from app.application.dtos.product_dto import CreateProductDTO, ProductDTO, UpdateProductDTO
from app.domain.exceptions import DomainError, DomainErrorCode
from app.infrastructure.dependencies import ProductFacadeDep
from app.presentation.api.v1.auth_middleware import CurrentUser
from app.presentation.api.v1.pagination import LimitParam, SkipParam
from app.presentation.api.v1.schemas.product_schema import (
    CreateProductRequest,
    ProductResponse,
    UpdateProductRequest,
)
from app.presentation.api.v1.schemas.user_schema import ErrorResponse, MessageResponse

router = APIRouter(prefix="/products", tags=["Products"])

_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    400: {"model": ErrorResponse, "description": "Validation or business rule error."},
    401: {"model": ErrorResponse, "description": "Authentication required."},
    403: {"model": ErrorResponse, "description": "Forbidden — you do not own this product."},
    404: {"model": ErrorResponse, "description": "Product not found."},
    409: {"model": ErrorResponse, "description": "Conflict — product already exists."},
    429: {"model": ErrorResponse, "description": "Too many requests."},
    500: {"model": ErrorResponse, "description": "Internal server error."},
}


def _domain_error_to_http(error: DomainError) -> HTTPException:
    """Map DomainError codes to appropriate HTTP status codes."""
    code_to_status = {
        DomainErrorCode.PRODUCT_NOT_FOUND: status.HTTP_404_NOT_FOUND,
        DomainErrorCode.NOT_FOUND: status.HTTP_404_NOT_FOUND,
        DomainErrorCode.USER_NOT_FOUND: status.HTTP_404_NOT_FOUND,
        DomainErrorCode.PRODUCT_ALREADY_EXISTS: status.HTTP_409_CONFLICT,
        DomainErrorCode.ALREADY_EXISTS: status.HTTP_409_CONFLICT,
        DomainErrorCode.UNAUTHORIZED: status.HTTP_401_UNAUTHORIZED,
        DomainErrorCode.FORBIDDEN: status.HTTP_403_FORBIDDEN,
        DomainErrorCode.VALIDATION_ERROR: status.HTTP_400_BAD_REQUEST,
        DomainErrorCode.INSUFFICIENT_STOCK: status.HTTP_400_BAD_REQUEST,
    }
    http_status = code_to_status.get(error.code, status.HTTP_400_BAD_REQUEST)
    return HTTPException(status_code=http_status, detail=error.message)


def _to_response(dto: ProductDTO) -> ProductResponse:
    return ProductResponse(
        id=dto.id,
        name=dto.name,
        description=dto.description,
        price=dto.price,
        stock=dto.stock,
        owner_id=dto.owner_id,
        is_active=dto.is_active,
        created_at=dto.created_at,
        updated_at=dto.updated_at,
    )


# ─── Public Endpoints ─────────────────────────────────────────────────────────

@router.get(
    "/",
    response_model=list[ProductResponse],
    status_code=status.HTTP_200_OK,
    responses={**_ERROR_RESPONSES},
    summary="List all products",
    description="Returns a paginated list of all active products.",
)
async def list_products(
    facade: ProductFacadeDep,
    skip: SkipParam = 0,
    limit: LimitParam = 100,
) -> list[ProductResponse]:
    result = await facade.get_all_products(skip=skip, limit=limit)
    if result.is_err():
        raise _domain_error_to_http(result.unwrap_err())
    return [_to_response(p) for p in result.unwrap()]


@router.get(
    "/{product_id}",
    response_model=ProductResponse,
    status_code=status.HTTP_200_OK,
    responses={**_ERROR_RESPONSES},
    summary="Get product by ID",
    description="Returns a specific product by its ID.",
)
async def get_product(
    product_id: int,
    facade: ProductFacadeDep,
) -> ProductResponse:
    result = await facade.get_product(product_id)
    if result.is_err():
        raise _domain_error_to_http(result.unwrap_err())
    return _to_response(result.unwrap())


# ─── Authenticated Endpoints ──────────────────────────────────────────────────

@router.post(
    "/",
    response_model=ProductResponse,
    status_code=status.HTTP_201_CREATED,
    responses={**_ERROR_RESPONSES},
    summary="Create a new product",
    description="Create a new product owned by the currently authenticated user.",
)
async def create_product(
    body: CreateProductRequest,
    current_user: CurrentUser,
    facade: ProductFacadeDep,
) -> ProductResponse:
    dto = CreateProductDTO(
        name=body.name,
        description=body.description,
        price=body.price,
        stock=body.stock,
        owner_id=current_user.id,
    )
    result = await facade.create_product(dto)
    if result.is_err():
        raise _domain_error_to_http(result.unwrap_err())
    return _to_response(result.unwrap())


@router.patch(
    "/{product_id}",
    response_model=ProductResponse,
    status_code=status.HTTP_200_OK,
    responses={**_ERROR_RESPONSES},
    summary="Update a product",
    description="Update a product owned by the currently authenticated user.",
)
async def update_product(
    product_id: int,
    body: UpdateProductRequest,
    current_user: CurrentUser,
    facade: ProductFacadeDep,
) -> ProductResponse:
    dto = UpdateProductDTO(
        name=body.name,
        description=body.description,
        price=body.price,
        stock=body.stock,
    )
    result = await facade.update_product(
        product_id=product_id,
        owner_id=current_user.id,
        dto=dto,
    )
    if result.is_err():
        raise _domain_error_to_http(result.unwrap_err())
    return _to_response(result.unwrap())


@router.delete(
    "/{product_id}",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    responses={**_ERROR_RESPONSES},
    summary="Delete a product",
    description="Delete a product owned by the currently authenticated user.",
)
async def delete_product(
    product_id: int,
    current_user: CurrentUser,
    facade: ProductFacadeDep,
) -> MessageResponse:
    result = await facade.delete_product(
        product_id=product_id,
        owner_id=current_user.id,
    )
    if result.is_err():
        raise _domain_error_to_http(result.unwrap_err())
    return MessageResponse(message=f"Product {product_id} deleted successfully.")


@router.get(
    "/owner/{owner_id}",
    response_model=list[ProductResponse],
    status_code=status.HTTP_200_OK,
    responses={**_ERROR_RESPONSES},
    summary="Get products by owner",
    description="Returns all products belonging to a specific user.",
)
async def get_products_by_owner(
    owner_id: int,
    facade: ProductFacadeDep,
    skip: SkipParam = 0,
    limit: LimitParam = 100,
) -> list[ProductResponse]:
    result = await facade.get_products_by_owner(owner_id=owner_id, skip=skip, limit=limit)
    if result.is_err():
        raise _domain_error_to_http(result.unwrap_err())
    return [_to_response(p) for p in result.unwrap()]
