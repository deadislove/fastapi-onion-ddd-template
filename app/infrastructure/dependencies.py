"""
FastAPI dependency injection wiring.
Provides factory functions that build and inject application services/facades.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.facades.product_facade import ProductFacade
from app.application.facades.user_facade import UserFacade
from app.application.facades.user_product_facade import UserProductFacade
from app.application.services.auth_service import AuthService
from app.application.services.event_dispatcher import IEventDispatcher
from app.application.services.product_service import ProductService
from app.application.services.user_service import UserService
from app.config import settings
from app.infrastructure.database.session import get_db_session
from app.infrastructure.observability.event_dispatcher import LoggingEventDispatcher
from app.infrastructure.repositories.product_repository import SQLAlchemyProductRepository
from app.infrastructure.repositories.user_repository import SQLAlchemyUserRepository
from app.infrastructure.security.jwt_handler import JWTTokenService
from app.infrastructure.security.password_hasher import BcryptPasswordHasher
from app.infrastructure.security.token_revocation import RedisTokenRevocationStore

# ─── Singletons (stateless, safe to reuse) ────────────────────────────────────
_password_hasher = BcryptPasswordHasher()
_token_service = JWTTokenService()
_redis_client = Redis.from_url(settings.REDIS_URL, decode_responses=True)
_revocation_store = RedisTokenRevocationStore(_redis_client)
_event_dispatcher: IEventDispatcher = LoggingEventDispatcher()


# ─── Session dependency ────────────────────────────────────────────────────────
DBSession = Annotated[AsyncSession, Depends(get_db_session)]


# ─── Repository factories ──────────────────────────────────────────────────────
def get_user_repository(session: DBSession) -> SQLAlchemyUserRepository:
    return SQLAlchemyUserRepository(session)


def get_product_repository(session: DBSession) -> SQLAlchemyProductRepository:
    return SQLAlchemyProductRepository(session)


# ─── Service factories ─────────────────────────────────────────────────────────
def get_auth_service() -> AuthService:
    return AuthService(
        password_hasher=_password_hasher,
        token_service=_token_service,
        revocation_store=_revocation_store,
    )


def get_event_dispatcher() -> IEventDispatcher:
    return _event_dispatcher


def get_user_service(
    user_repo: Annotated[SQLAlchemyUserRepository, Depends(get_user_repository)],
    event_dispatcher: Annotated[IEventDispatcher, Depends(get_event_dispatcher)],
) -> UserService:
    return UserService(user_repository=user_repo, event_dispatcher=event_dispatcher)


def get_product_service(
    product_repo: Annotated[SQLAlchemyProductRepository, Depends(get_product_repository)],
    user_repo: Annotated[SQLAlchemyUserRepository, Depends(get_user_repository)],
    event_dispatcher: Annotated[IEventDispatcher, Depends(get_event_dispatcher)],
) -> ProductService:
    return ProductService(
        product_repository=product_repo,
        user_repository=user_repo,
        event_dispatcher=event_dispatcher,
    )


# ─── Facade factories ──────────────────────────────────────────────────────────
def get_user_facade(
    user_service: Annotated[UserService, Depends(get_user_service)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> UserFacade:
    return UserFacade(user_service=user_service, auth_service=auth_service)


def get_product_facade(
    product_service: Annotated[ProductService, Depends(get_product_service)],
) -> ProductFacade:
    return ProductFacade(product_service=product_service)


def get_user_product_facade(
    user_facade: Annotated[UserFacade, Depends(get_user_facade)],
    product_facade: Annotated[ProductFacade, Depends(get_product_facade)],
) -> UserProductFacade:
    return UserProductFacade(user_facade=user_facade, product_facade=product_facade)


# ─── Annotated type aliases for cleaner route signatures ──────────────────────
UserFacadeDep = Annotated[UserFacade, Depends(get_user_facade)]
ProductFacadeDep = Annotated[ProductFacade, Depends(get_product_facade)]
UserProductFacadeDep = Annotated[UserProductFacade, Depends(get_user_product_facade)]
AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]
