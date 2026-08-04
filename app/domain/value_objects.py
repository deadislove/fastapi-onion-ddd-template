"""
Domain Value Objects — immutable, self-validating objects with no identity.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from app.domain.common.result import Err, Ok, Result
from app.domain.exceptions import DomainError

EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")


@dataclass(frozen=True)
class Email:
    value: str

    def __post_init__(self) -> None:
        if not EMAIL_REGEX.match(self.value):
            raise ValueError(f"Invalid email address: {self.value}")

    @classmethod
    def create(cls, value: str) -> Result[Email, DomainError]:
        if not value or not value.strip():
            return Err(DomainError.validation_error("Email cannot be empty."))
        value = value.strip().lower()
        if not EMAIL_REGEX.match(value):
            return Err(DomainError.validation_error(f"Invalid email address: '{value}'."))
        return Ok(cls(value=value))

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class Password:
    """Hashed password value object. The raw password is never stored."""
    hashed_value: str

    @classmethod
    def from_hash(cls, hashed_value: str) -> Password:
        return cls(hashed_value=hashed_value)

    def __str__(self) -> str:
        return "***"

    def __repr__(self) -> str:
        return "Password(***)"


@dataclass(frozen=True)
class ProductName:
    value: str

    @classmethod
    def create(cls, value: str) -> Result[ProductName, DomainError]:
        if not value or not value.strip():
            return Err(DomainError.validation_error("Product name cannot be empty."))
        value = value.strip()
        if len(value) > 255:
            return Err(DomainError.validation_error("Product name cannot exceed 255 characters."))
        return Ok(cls(value=value))

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class Money:
    """
    A monetary amount, stored as an exact Decimal — never float. Float arithmetic
    accumulates rounding drift (0.1 + 0.2 != 0.3) which is unacceptable for money;
    Decimal is exact for base-10 values like currency.
    """
    amount: Decimal
    currency: str = "USD"

    @classmethod
    def create(cls, amount: Decimal | float | str, currency: str = "USD") -> Result[Money, DomainError]:
        try:
            # str(amount) first: constructing Decimal directly from a float would capture
            # that float's own binary imprecision (e.g. Decimal(99.99) has 15+ trailing
            # digits of noise); routing through str() captures the shortest round-trip
            # decimal representation instead, which is what a client actually sent.
            decimal_amount = Decimal(str(amount)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        except (InvalidOperation, ValueError, TypeError):
            return Err(DomainError.validation_error(f"Invalid monetary amount: '{amount}'."))
        if decimal_amount < 0:
            return Err(DomainError.validation_error("Price cannot be negative."))
        return Ok(cls(amount=decimal_amount, currency=currency.upper()))

    def __str__(self) -> str:
        return f"{self.amount:.2f} {self.currency}"
