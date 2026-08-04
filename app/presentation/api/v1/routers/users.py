"""
User API router — versioned at /api/v1/users.
Handles registration, login, token refresh, and user CRUD.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request, status

from app.application.dtos.user_dto import CreateUserDTO, LoginDTO, UpdateUserDTO
from app.domain.exceptions import DomainError, DomainErrorCode
from app.infrastructure.dependencies import UserFacadeDep
from app.infrastructure.security.rate_limiter import limiter
from app.presentation.api.v1.auth_middleware import BearerToken, CurrentSuperUser, CurrentUser
from app.presentation.api.v1.pagination import LimitParam, SkipParam
from app.presentation.api.v1.schemas.user_schema import (
    ErrorResponse,
    LoginRequest,
    LogoutRequest,
    MessageResponse,
    RefreshTokenRequest,
    RegisterRequest,
    TokenResponse,
    UpdateUserRequest,
    UserResponse,
)

router = APIRouter(prefix="/users", tags=["Users"])

_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    400: {"model": ErrorResponse, "description": "Validation or business rule error."},
    401: {"model": ErrorResponse, "description": "Authentication required or token invalid."},
    403: {"model": ErrorResponse, "description": "Forbidden — insufficient permissions."},
    404: {"model": ErrorResponse, "description": "User not found."},
    409: {"model": ErrorResponse, "description": "Conflict — user already exists."},
    429: {"model": ErrorResponse, "description": "Too many requests."},
    500: {"model": ErrorResponse, "description": "Internal server error."},
}


def _domain_error_to_http(error: DomainError) -> HTTPException:
    """Map DomainError codes to appropriate HTTP status codes."""
    code_to_status = {
        DomainErrorCode.USER_NOT_FOUND: status.HTTP_404_NOT_FOUND,
        DomainErrorCode.NOT_FOUND: status.HTTP_404_NOT_FOUND,
        DomainErrorCode.USER_ALREADY_EXISTS: status.HTTP_409_CONFLICT,
        DomainErrorCode.ALREADY_EXISTS: status.HTTP_409_CONFLICT,
        DomainErrorCode.INVALID_CREDENTIALS: status.HTTP_401_UNAUTHORIZED,
        DomainErrorCode.INVALID_TOKEN: status.HTTP_401_UNAUTHORIZED,
        DomainErrorCode.TOKEN_EXPIRED: status.HTTP_401_UNAUTHORIZED,
        DomainErrorCode.TOKEN_REVOKED: status.HTTP_401_UNAUTHORIZED,
        DomainErrorCode.UNAUTHORIZED: status.HTTP_401_UNAUTHORIZED,
        DomainErrorCode.FORBIDDEN: status.HTTP_403_FORBIDDEN,
        DomainErrorCode.VALIDATION_ERROR: status.HTTP_400_BAD_REQUEST,
    }
    http_status = code_to_status.get(error.code, status.HTTP_400_BAD_REQUEST)
    return HTTPException(status_code=http_status, detail=error.message)


# ─── Auth Endpoints ───────────────────────────────────────────────────────────

@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    responses={**_ERROR_RESPONSES},
    summary="Register a new user",
    description="Create a new user account with email, password, and full name.",
)
@limiter.limit("10/minute")
async def register(
    request: Request,
    body: RegisterRequest,
    facade: UserFacadeDep,
) -> UserResponse:
    dto = CreateUserDTO(
        email=body.email,
        password=body.password,
        full_name=body.full_name,
    )
    result = await facade.register(dto)
    if result.is_err():
        raise _domain_error_to_http(result.unwrap_err())
    user = result.unwrap()
    return UserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        is_active=user.is_active,
        is_superuser=user.is_superuser,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    responses={**_ERROR_RESPONSES},
    summary="Login and obtain JWT tokens",
    description="Authenticate with email and password to receive access and refresh tokens.",
)
@limiter.limit("20/minute")
async def login(
    request: Request,
    body: LoginRequest,
    facade: UserFacadeDep,
) -> TokenResponse:
    dto = LoginDTO(email=body.email, password=body.password)
    result = await facade.login(dto)
    if result.is_err():
        raise _domain_error_to_http(result.unwrap_err())
    tokens = result.unwrap()
    return TokenResponse(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        token_type=tokens.token_type,
    )


@router.post(
    "/refresh",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    responses={**_ERROR_RESPONSES},
    summary="Refresh access token",
    description="Exchange a valid refresh token for a new access/refresh token pair.",
)
@limiter.limit("30/minute")
async def refresh_tokens(
    request: Request,
    body: RefreshTokenRequest,
    facade: UserFacadeDep,
) -> TokenResponse:
    result = await facade.refresh_tokens(body.refresh_token)
    if result.is_err():
        raise _domain_error_to_http(result.unwrap_err())
    tokens = result.unwrap()
    return TokenResponse(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        token_type=tokens.token_type,
    )


@router.post(
    "/logout",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    responses={**_ERROR_RESPONSES},
    summary="Logout and revoke tokens",
    description=(
        "Revokes the access token used to authenticate this request and, if supplied, "
        "the refresh token — both become unusable immediately. Idempotent."
    ),
)
async def logout(
    credentials: BearerToken,
    body: LogoutRequest,
    facade: UserFacadeDep,
) -> MessageResponse:
    await facade.logout(credentials.credentials, body.refresh_token)
    return MessageResponse(message="Logged out successfully.")


# ─── User Profile Endpoints ───────────────────────────────────────────────────

@router.get(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    responses={**_ERROR_RESPONSES},
    summary="Get current user profile",
    description="Returns the profile of the currently authenticated user.",
)
async def get_me(current_user: CurrentUser) -> UserResponse:
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name,
        is_active=current_user.is_active,
        is_superuser=current_user.is_superuser,
        created_at=current_user.created_at,
        updated_at=current_user.updated_at,
    )


@router.patch(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    responses={**_ERROR_RESPONSES},
    summary="Update current user profile",
    description="Update the full name of the currently authenticated user.",
)
async def update_me(
    body: UpdateUserRequest,
    current_user: CurrentUser,
    facade: UserFacadeDep,
) -> UserResponse:
    dto = UpdateUserDTO(full_name=body.full_name)
    result = await facade.update_user(current_user.id, dto)
    if result.is_err():
        raise _domain_error_to_http(result.unwrap_err())
    user = result.unwrap()
    return UserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        is_active=user.is_active,
        is_superuser=user.is_superuser,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


# ─── Admin Endpoints ──────────────────────────────────────────────────────────

@router.get(
    "/",
    response_model=list[UserResponse],
    status_code=status.HTTP_200_OK,
    responses={**_ERROR_RESPONSES},
    summary="List all users (superuser only)",
    description="Returns a paginated list of all registered users. Requires superuser privileges.",
)
async def list_users(
    facade: UserFacadeDep,
    current_user: CurrentSuperUser,
    skip: SkipParam = 0,
    limit: LimitParam = 100,
) -> list[UserResponse]:
    result = await facade.get_all_users(skip=skip, limit=limit)
    if result.is_err():
        raise _domain_error_to_http(result.unwrap_err())
    return [
        UserResponse(
            id=u.id,
            email=u.email,
            full_name=u.full_name,
            is_active=u.is_active,
            is_superuser=u.is_superuser,
            created_at=u.created_at,
            updated_at=u.updated_at,
        )
        for u in result.unwrap()
    ]


@router.get(
    "/{user_id}",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    responses={**_ERROR_RESPONSES},
    summary="Get user by ID (superuser only)",
    description="Returns a specific user by their ID. Requires superuser privileges.",
)
async def get_user(
    user_id: int,
    facade: UserFacadeDep,
    current_user: CurrentSuperUser,
) -> UserResponse:
    result = await facade.get_user(user_id)
    if result.is_err():
        raise _domain_error_to_http(result.unwrap_err())
    user = result.unwrap()
    return UserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        is_active=user.is_active,
        is_superuser=user.is_superuser,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


@router.delete(
    "/{user_id}",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    responses={**_ERROR_RESPONSES},
    summary="Delete user by ID (superuser only)",
    description="Permanently deletes a user by their ID. Requires superuser privileges.",
)
async def delete_user(
    user_id: int,
    facade: UserFacadeDep,
    current_user: CurrentSuperUser,
) -> MessageResponse:
    result = await facade.delete_user(user_id)
    if result.is_err():
        raise _domain_error_to_http(result.unwrap_err())
    return MessageResponse(message=f"User {user_id} deleted successfully.")
