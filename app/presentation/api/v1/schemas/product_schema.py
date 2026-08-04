"""
Product Pydantic request/response schemas for the presentation layer.
Annotated with Swagger/OpenAPI examples.
"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

# Request Schemas

class CreateProductRequest(BaseModel):
    name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        examples=["Wireless Headphones"],
        description="Product name.",
    )
    description: str = Field(
        default="",
        max_length=2000,
        examples=["High-quality noise-cancelling wireless headphones."],
        description="Product description.",
    )
    price: float = Field(
        ...,
        ge=0.0,
        examples=[99.99],
        description="Product price (must be >= 0).",
    )
    stock: int = Field(
        ...,
        ge=0,
        examples=[50],
        description="Available stock quantity (must be >= 0).",
    )


class UpdateProductRequest(BaseModel):
    name: str | None = Field(
        default=None,
        min_length=1,
        max_length=255,
        examples=["Premium Wireless Headphones"],
        description="Updated product name.",
    )
    description: str | None = Field(
        default=None,
        max_length=2000,
        examples=["Updated description."],
        description="Updated product description.",
    )
    price: float | None = Field(
        default=None,
        ge=0.0,
        examples=[129.99],
        description="Updated price.",
    )
    stock: int | None = Field(
        default=None,
        ge=0,
        examples=[75],
        description="Updated stock quantity.",
    )


# Response Schemas

class ProductResponse(BaseModel):
    id: int = Field(..., examples=[1])
    name: str = Field(..., examples=["Wireless Headphones"])
    description: str = Field(..., examples=["High-quality noise-cancelling wireless headphones."])
    price: float = Field(..., examples=[99.99])
    stock: int = Field(..., examples=[50])
    owner_id: int = Field(..., examples=[1])
    is_active: bool = Field(..., examples=[True])
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
