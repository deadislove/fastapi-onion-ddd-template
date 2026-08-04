"""
JWT token handler — infrastructure implementation of ITokenService.
Uses PyJWT for token creation and decoding.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt

from app.application.services.auth_service import ITokenService
from app.config import settings
from app.domain.common.result import Err, Ok, Result
from app.domain.exceptions import DomainError


class JWTTokenService(ITokenService):
    """PyJWT-based implementation of the token service."""

    def __init__(
        self,
        secret_key: str = settings.JWT_SECRET_KEY,
        algorithm: str = settings.JWT_ALGORITHM,
        access_token_expire_minutes: int = settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES,
        refresh_token_expire_days: int = settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS,
    ) -> None:
        self._secret_key = secret_key
        self._algorithm = algorithm
        self._access_expire_minutes = access_token_expire_minutes
        self._refresh_expire_days = refresh_token_expire_days

    def create_access_token(self, subject: str | int, extra_claims: dict | None = None) -> str:
        now = datetime.now(UTC)
        expire = now + timedelta(minutes=self._access_expire_minutes)
        payload: dict = {
            "sub": str(subject),
            "iat": now,
            "exp": expire,
            "type": "access",
            "jti": str(uuid4()),
        }
        if extra_claims:
            payload.update(extra_claims)
        return jwt.encode(payload, self._secret_key, algorithm=self._algorithm)

    def create_refresh_token(self, subject: str | int) -> str:
        now = datetime.now(UTC)
        expire = now + timedelta(days=self._refresh_expire_days)
        payload: dict = {
            "sub": str(subject),
            "iat": now,
            "exp": expire,
            "type": "refresh",
            "jti": str(uuid4()),
        }
        return jwt.encode(payload, self._secret_key, algorithm=self._algorithm)

    def decode_token(self, token: str, expected_type: str | None = None) -> Result[dict, DomainError]:
        try:
            payload = jwt.decode(
                token,
                self._secret_key,
                algorithms=[self._algorithm],
            )
        except jwt.ExpiredSignatureError:
            return Err(DomainError.token_expired())
        except jwt.InvalidTokenError as exc:
            return Err(DomainError.invalid_token(str(exc)))

        if expected_type is not None and payload.get("type") != expected_type:
            return Err(DomainError.invalid_token(f"Expected a '{expected_type}' token."))

        return Ok(payload)
