"""
Auth Domain Service — authentication and token management business rules.
Returns Result[T, DomainError] for all operations.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import UTC, datetime

from app.application.dtos.user_dto import TokenDTO
from app.domain.common.result import Err, Ok, Result
from app.domain.exceptions import DomainError


class IPasswordHasher(ABC):
    """Abstract interface for password hashing — implemented in infrastructure."""

    @abstractmethod
    def hash(self, plain_password: str) -> str:
        ...

    @abstractmethod
    def verify(self, plain_password: str, hashed_password: str) -> bool:
        ...


class ITokenService(ABC):
    """Abstract interface for JWT token operations — implemented in infrastructure."""

    @abstractmethod
    def create_access_token(self, subject: str | int, extra_claims: dict | None = None) -> str:
        ...

    @abstractmethod
    def create_refresh_token(self, subject: str | int) -> str:
        ...

    @abstractmethod
    def decode_token(self, token: str, expected_type: str | None = None) -> Result[dict, DomainError]:
        """Decode and verify a token. If expected_type is given ('access' or 'refresh'),
        reject tokens whose 'type' claim doesn't match — prevents using a refresh token
        where an access token is required, or vice versa."""
        ...


class ITokenRevocationStore(ABC):
    """Abstract interface for tracking revoked tokens (logout / refresh rotation) — implemented in infrastructure."""

    @abstractmethod
    async def revoke(self, jti: str, ttl_seconds: int) -> None:
        ...

    @abstractmethod
    async def is_revoked(self, jti: str) -> bool:
        ...


class AuthService:
    """Application service for authentication workflows."""

    def __init__(
        self,
        password_hasher: IPasswordHasher,
        token_service: ITokenService,
        revocation_store: ITokenRevocationStore,
    ) -> None:
        self._hasher = password_hasher
        self._token_service = token_service
        self._revocation_store = revocation_store

    def hash_password(self, plain_password: str) -> Result[str, DomainError]:
        if not plain_password or len(plain_password) < 8:
            return Err(DomainError.validation_error("Password must be at least 8 characters long."))
        hashed = self._hasher.hash(plain_password)
        return Ok(hashed)

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        return self._hasher.verify(plain_password, hashed_password)

    def create_tokens(self, user_id: int, email: str) -> TokenDTO:
        access_token = self._token_service.create_access_token(
            subject=str(user_id),
            extra_claims={"email": email},
        )
        refresh_token = self._token_service.create_refresh_token(subject=str(user_id))
        return TokenDTO(access_token=access_token, refresh_token=refresh_token)

    def decode_access_token(self, token: str) -> Result[dict, DomainError]:
        return self._token_service.decode_token(token, expected_type="access")

    async def get_user_id_from_token(
        self, token: str, expected_type: str = "access"
    ) -> Result[int, DomainError]:
        """Decode a token, enforcing its claimed type ('access' or 'refresh') and
        rejecting it if it has been revoked (logout / refresh rotation)."""
        result = self._token_service.decode_token(token, expected_type=expected_type)
        if result.is_err():
            return result  # type: ignore[return-value]

        payload = result.unwrap()

        jti = payload.get("jti")
        if jti and await self._revocation_store.is_revoked(jti):
            return Err(DomainError.token_revoked())

        sub = payload.get("sub")
        if sub is None:
            return Err(DomainError.invalid_token("Token missing 'sub' claim."))

        try:
            user_id = int(sub)
        except (ValueError, TypeError):
            return Err(DomainError.invalid_token("Invalid user ID in token."))

        return Ok(user_id)

    async def revoke_token(self, token: str) -> None:
        """Best-effort revoke: blacklist the token's jti until its natural expiry.
        Silently no-ops on already-invalid/expired/malformed tokens (logout must be idempotent)."""
        result = self._token_service.decode_token(token)
        if result.is_err():
            return

        payload = result.unwrap()
        jti = payload.get("jti")
        exp = payload.get("exp")
        if not jti or not exp:
            return

        ttl_seconds = int(exp - datetime.now(UTC).timestamp())
        if ttl_seconds > 0:
            await self._revocation_store.revoke(jti, ttl_seconds=ttl_seconds)

    async def logout(self, access_token: str, refresh_token: str | None = None) -> None:
        """Revoke the current access token and, if provided, the refresh token."""
        await self.revoke_token(access_token)
        if refresh_token:
            await self.revoke_token(refresh_token)
