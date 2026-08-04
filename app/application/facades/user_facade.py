"""
User Application Facade — orchestrates user workflows, manages UoW, and handles DTO mapping.
Controllers call this facade instead of raw services or repositories.
"""
from __future__ import annotations

from app.application.dtos.user_dto import (
    CreateUserDTO,
    LoginDTO,
    TokenDTO,
    UpdateUserDTO,
    UserDTO,
)
from app.application.services.auth_service import AuthService
from app.application.services.user_service import UserService
from app.domain.common.result import Err, Ok, Result
from app.domain.exceptions import DomainError


class UserFacade:
    """
    Application facade for user-related workflows.
    Orchestrates UserService + AuthService, maps domain entities to DTOs.
    """

    def __init__(
        self,
        user_service: UserService,
        auth_service: AuthService,
    ) -> None:
        self._user_service = user_service
        self._auth_service = auth_service

    async def register(self, dto: CreateUserDTO) -> Result[UserDTO, DomainError]:
        # Hash password
        hash_result = self._auth_service.hash_password(dto.password)
        if hash_result.is_err():
            return Err(hash_result.unwrap_err())

        hashed_password = hash_result.unwrap()

        # Register user via domain service
        result = await self._user_service.register_user(
            email=dto.email,
            hashed_password=hashed_password,
            full_name=dto.full_name,
            is_superuser=dto.is_superuser,
        )
        if result.is_err():
            return Err(result.unwrap_err())

        user = result.unwrap()
        return Ok(UserDTO.from_entity(user))

    async def login(self, dto: LoginDTO) -> Result[TokenDTO, DomainError]:
        # Fetch user by email
        user_result = await self._user_service.get_user_by_email(dto.email)
        if user_result.is_err():
            # Return generic invalid credentials to avoid email enumeration
            return Err(DomainError.invalid_credentials())

        user = user_result.unwrap()

        if not user.is_active:
            return Err(DomainError.unauthorized("User account is deactivated."))

        # Verify password
        if not self._auth_service.verify_password(dto.password, user.hashed_password.hashed_value):
            return Err(DomainError.invalid_credentials())

        # Issue tokens
        tokens = self._auth_service.create_tokens(user_id=user.id, email=str(user.email))  # type: ignore[arg-type]
        return Ok(tokens)

    async def refresh_tokens(self, refresh_token: str) -> Result[TokenDTO, DomainError]:
        user_id_result = await self._auth_service.get_user_id_from_token(
            refresh_token, expected_type="refresh"
        )
        if user_id_result.is_err():
            return Err(user_id_result.unwrap_err())

        user_id = user_id_result.unwrap()
        user_result = await self._user_service.get_user_by_id(user_id)
        if user_result.is_err():
            return Err(user_result.unwrap_err())

        user = user_result.unwrap()
        if not user.is_active:
            return Err(DomainError.unauthorized("User account is deactivated."))

        # Rotation: the used refresh token is single-use — revoke it before issuing a new pair.
        await self._auth_service.revoke_token(refresh_token)

        tokens = self._auth_service.create_tokens(user_id=user.id, email=str(user.email))  # type: ignore[arg-type]
        return Ok(tokens)

    async def logout(self, access_token: str, refresh_token: str | None = None) -> Result[None, DomainError]:
        """Revoke the current access token and, if provided, the refresh token. Idempotent."""
        await self._auth_service.logout(access_token, refresh_token)
        return Ok(None)

    async def get_user(self, user_id: int) -> Result[UserDTO, DomainError]:
        result = await self._user_service.get_user_by_id(user_id)
        if result.is_err():
            return Err(result.unwrap_err())
        return Ok(UserDTO.from_entity(result.unwrap()))

    async def get_all_users(self, skip: int = 0, limit: int = 100) -> Result[list[UserDTO], DomainError]:
        result = await self._user_service.get_all_users(skip=skip, limit=limit)
        if result.is_err():
            return Err(result.unwrap_err())
        return Ok([UserDTO.from_entity(u) for u in result.unwrap()])

    async def update_user(self, user_id: int, dto: UpdateUserDTO) -> Result[UserDTO, DomainError]:
        result = await self._user_service.update_user(
            user_id=user_id,
            full_name=dto.full_name,
        )
        if result.is_err():
            return Err(result.unwrap_err())
        return Ok(UserDTO.from_entity(result.unwrap()))

    async def delete_user(self, user_id: int) -> Result[bool, DomainError]:
        return await self._user_service.delete_user(user_id)

    async def get_current_user(self, token: str) -> Result[UserDTO, DomainError]:
        user_id_result = await self._auth_service.get_user_id_from_token(token, expected_type="access")
        if user_id_result.is_err():
            return Err(user_id_result.unwrap_err())

        return await self.get_user(user_id_result.unwrap())
