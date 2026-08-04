"""
Domain exceptions — pure domain errors with no external dependencies.
These are used as the error type in Result[T, DomainError].
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class DomainErrorCode(StrEnum):
    # Generic
    NOT_FOUND = "NOT_FOUND"
    ALREADY_EXISTS = "ALREADY_EXISTS"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"

    # User-specific
    USER_NOT_FOUND = "USER_NOT_FOUND"
    USER_ALREADY_EXISTS = "USER_ALREADY_EXISTS"
    INVALID_CREDENTIALS = "INVALID_CREDENTIALS"
    INVALID_TOKEN = "INVALID_TOKEN"
    TOKEN_EXPIRED = "TOKEN_EXPIRED"
    TOKEN_REVOKED = "TOKEN_REVOKED"

    # Product-specific
    PRODUCT_NOT_FOUND = "PRODUCT_NOT_FOUND"
    PRODUCT_ALREADY_EXISTS = "PRODUCT_ALREADY_EXISTS"
    INSUFFICIENT_STOCK = "INSUFFICIENT_STOCK"


@dataclass(frozen=True)
class DomainError:
    code: DomainErrorCode
    message: str
    details: dict = field(default_factory=dict)

    def __str__(self) -> str:
        return f"[{self.code}] {self.message}"

    @classmethod
    def not_found(cls, resource: str, identifier: str | int) -> DomainError:
        return cls(
            code=DomainErrorCode.NOT_FOUND,
            message=f"{resource} with identifier '{identifier}' was not found.",
            details={"resource": resource, "identifier": str(identifier)},
        )

    @classmethod
    def already_exists(cls, resource: str, field: str, value: str) -> DomainError:
        return cls(
            code=DomainErrorCode.ALREADY_EXISTS,
            message=f"{resource} with {field}='{value}' already exists.",
            details={"resource": resource, "field": field, "value": value},
        )

    @classmethod
    def validation_error(cls, message: str, details: dict | None = None) -> DomainError:
        return cls(
            code=DomainErrorCode.VALIDATION_ERROR,
            message=message,
            details=details or {},
        )

    @classmethod
    def unauthorized(cls, message: str = "Authentication required.") -> DomainError:
        return cls(code=DomainErrorCode.UNAUTHORIZED, message=message)

    @classmethod
    def invalid_credentials(cls) -> DomainError:
        return cls(
            code=DomainErrorCode.INVALID_CREDENTIALS,
            message="Invalid email or password.",
        )

    @classmethod
    def invalid_token(cls, message: str = "Invalid or malformed token.") -> DomainError:
        return cls(code=DomainErrorCode.INVALID_TOKEN, message=message)

    @classmethod
    def token_expired(cls) -> DomainError:
        return cls(code=DomainErrorCode.TOKEN_EXPIRED, message="Token has expired.")

    @classmethod
    def token_revoked(cls) -> DomainError:
        return cls(code=DomainErrorCode.TOKEN_REVOKED, message="Token has been revoked.")

    @classmethod
    def user_not_found(cls, identifier: str | int) -> DomainError:
        return cls(
            code=DomainErrorCode.USER_NOT_FOUND,
            message=f"User '{identifier}' was not found.",
            details={"identifier": str(identifier)},
        )

    @classmethod
    def user_already_exists(cls, email: str) -> DomainError:
        return cls(
            code=DomainErrorCode.USER_ALREADY_EXISTS,
            message=f"User with email '{email}' already exists.",
            details={"email": email},
        )

    @classmethod
    def product_not_found(cls, identifier: str | int) -> DomainError:
        return cls(
            code=DomainErrorCode.PRODUCT_NOT_FOUND,
            message=f"Product '{identifier}' was not found.",
            details={"identifier": str(identifier)},
        )

    @classmethod
    def product_already_exists(cls, name: str) -> DomainError:
        return cls(
            code=DomainErrorCode.PRODUCT_ALREADY_EXISTS,
            message=f"Product with name '{name}' already exists.",
            details={"name": name},
        )

    @classmethod
    def insufficient_stock(cls, product_id: int, requested: int, available: int) -> DomainError:
        return cls(
            code=DomainErrorCode.INSUFFICIENT_STOCK,
            message=f"Insufficient stock for product {product_id}. Requested: {requested}, Available: {available}.",
            details={"product_id": product_id, "requested": requested, "available": available},
        )
