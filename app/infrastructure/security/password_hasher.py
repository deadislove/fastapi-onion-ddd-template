"""
Bcrypt password hasher — infrastructure implementation of IPasswordHasher.
Uses the `bcrypt` library directly: passlib is unmaintained and incompatible with
bcrypt>=4.1's stricter 72-byte secret handling (raises instead of silently truncating).
"""
from __future__ import annotations

import bcrypt

from app.application.services.auth_service import IPasswordHasher

# bcrypt only uses the first 72 bytes of the secret; truncate ourselves so hashing
# never raises on long inputs (matches bcrypt's own historical behavior).
_MAX_SECRET_BYTES = 72


class BcryptPasswordHasher(IPasswordHasher):
    """Bcrypt-based password hashing using the `bcrypt` library."""

    def hash(self, plain_password: str) -> str:
        secret = plain_password.encode("utf-8")[:_MAX_SECRET_BYTES]
        return bcrypt.hashpw(secret, bcrypt.gensalt()).decode("utf-8")

    def verify(self, plain_password: str, hashed_password: str) -> bool:
        secret = plain_password.encode("utf-8")[:_MAX_SECRET_BYTES]
        try:
            return bcrypt.checkpw(secret, hashed_password.encode("utf-8"))
        except ValueError:
            return False
