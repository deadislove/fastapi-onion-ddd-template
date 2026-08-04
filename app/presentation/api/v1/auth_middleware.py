"""
Auth middleware / dependency — extracts and validates Bearer JWT tokens.
Provides get_current_user and get_current_superuser FastAPI dependencies.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.application.dtos.user_dto import UserDTO
from app.application.facades.user_facade import UserFacade
from app.domain.exceptions import DomainErrorCode
from app.infrastructure.dependencies import get_user_facade

_bearer_scheme = HTTPBearer(auto_error=True)


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(_bearer_scheme)],
    user_facade: Annotated[UserFacade, Depends(get_user_facade)],
) -> UserDTO:
    """
    FastAPI dependency that extracts the Bearer token, decodes it,
    and returns the authenticated UserDTO.
    Raises HTTP 401 on invalid/expired tokens.
    """
    token = credentials.credentials
    result = await user_facade.get_current_user(token)

    if result.is_err():
        error = result.unwrap_err()
        if error.code in (DomainErrorCode.TOKEN_EXPIRED, DomainErrorCode.INVALID_TOKEN):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=error.message,
                headers={"WWW-Authenticate": "Bearer"},
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=error.message,
            headers={"WWW-Authenticate": "Bearer"},
        )

    return result.unwrap()


async def get_current_active_user(
    current_user: Annotated[UserDTO, Depends(get_current_user)],
) -> UserDTO:
    """Ensures the authenticated user is active."""
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated.",
        )
    return current_user


async def get_current_superuser(
    current_user: Annotated[UserDTO, Depends(get_current_active_user)],
) -> UserDTO:
    """Ensures the authenticated user has superuser privileges."""
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Superuser privileges required.",
        )
    return current_user


# Annotated type aliases for cleaner route signatures
CurrentUser = Annotated[UserDTO, Depends(get_current_active_user)]
CurrentSuperUser = Annotated[UserDTO, Depends(get_current_superuser)]
BearerToken = Annotated[HTTPAuthorizationCredentials, Depends(_bearer_scheme)]
