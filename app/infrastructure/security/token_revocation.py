"""
Redis-backed token revocation store — infrastructure implementation of ITokenRevocationStore.
Blacklists a token's jti for the remainder of its natural lifetime (logout / refresh rotation).
"""
from __future__ import annotations

from redis.asyncio import Redis

from app.application.services.auth_service import ITokenRevocationStore

_KEY_PREFIX = "revoked_jti:"


class RedisTokenRevocationStore(ITokenRevocationStore):
    """Marks a jti as revoked using a Redis key with a TTL matching the token's remaining lifetime."""

    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    async def revoke(self, jti: str, ttl_seconds: int) -> None:
        await self._redis.set(f"{_KEY_PREFIX}{jti}", "1", ex=ttl_seconds)

    async def is_revoked(self, jti: str) -> bool:
        return await self._redis.exists(f"{_KEY_PREFIX}{jti}") > 0
