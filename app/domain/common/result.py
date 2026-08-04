"""
Result pattern implementation for explicit error handling.
Ok[T] represents success, Err[E] represents failure.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Generic, NoReturn, TypeVar

T = TypeVar("T")
E = TypeVar("E")
U = TypeVar("U")


@dataclass(frozen=True)
class Ok(Generic[T]):
    value: T

    def is_ok(self) -> bool:
        return True

    def is_err(self) -> bool:
        return False

    def unwrap(self) -> T:
        return self.value

    def unwrap_err(self) -> NoReturn:
        raise ValueError("Called unwrap_err on Ok")

    def map(self, fn: Callable[[T], U]) -> Ok[U]:
        return Ok(fn(self.value))

    def map_err(self, fn: Callable) -> Ok[T]:
        return self

    def __repr__(self) -> str:
        return f"Ok({self.value!r})"


@dataclass(frozen=True)
class Err(Generic[E]):
    error: E

    def is_ok(self) -> bool:
        return False

    def is_err(self) -> bool:
        return True

    def unwrap(self) -> NoReturn:
        raise ValueError(f"Called unwrap on Err: {self.error}")

    def unwrap_err(self) -> E:
        return self.error

    def map(self, fn: Callable) -> Err[E]:
        return self

    def map_err(self, fn: Callable[[E], U]) -> Err[U]:
        return Err(fn(self.error))

    def __repr__(self) -> str:
        return f"Err({self.error!r})"


# Type alias for Result
Result = Ok[T] | Err[E]
