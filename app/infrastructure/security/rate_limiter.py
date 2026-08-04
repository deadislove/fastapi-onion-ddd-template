"""
Rate limiter setup using slowapi.
"""
from __future__ import annotations

from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config import settings

# Global limiter instance — attach to FastAPI app via app.state.limiter
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[f"{settings.RATE_LIMIT_PER_MINUTE}/minute"],
)
