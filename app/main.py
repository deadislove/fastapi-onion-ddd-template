"""
FastAPI application entry point.
Configures middleware, routers, OpenAPI/Swagger, and startup/shutdown events.
"""
from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from alembic.config import Config
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from alembic import command
from app.config import settings
from app.infrastructure.database.session import engine
from app.infrastructure.error_handlers import (
    GlobalExceptionHandlerMiddleware,
    register_exception_handlers,
)
from app.infrastructure.observability.logging_config import configure_logging
from app.infrastructure.observability.request_id import RequestIDMiddleware
from app.infrastructure.observability.tracing import configure_tracing
from app.infrastructure.security.rate_limiter import limiter
from app.presentation.api.v1.routers import products, users

configure_logging()

_PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _run_migrations() -> None:
    """
    Apply pending Alembic migrations (sync, run off the event loop via asyncio.to_thread).
    Idempotent: creates the full schema on a fresh database, applies only the delta on an
    existing one, and no-ops once up to date. This is the single source of truth for schema
    changes — the app never calls Base.metadata.create_all() itself.
    """
    alembic_cfg = Config(str(_PROJECT_ROOT / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(_PROJECT_ROOT / "alembic"))
    command.upgrade(alembic_cfg, "head")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan — apply pending migrations on startup, then serve."""
    await asyncio.to_thread(_run_migrations)
    # Alembic's fileConfig resets the root logger's handlers on import — reassert JSON logging.
    configure_logging()
    yield
    await engine.dispose()


def create_app() -> FastAPI:
    """Application factory — creates and configures the FastAPI instance."""
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description=(
            "FastAPI Web API template implementing Onion Architecture and DDD principles. "
            "Features: JWT Auth, Rate Limiting, API Versioning, Result Pattern, "
            "Global Error Handling, and Swagger UI."
        ),
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
        swagger_ui_parameters={"persistAuthorization": True},
        # Configure Bearer Auth security scheme for Swagger UI
        openapi_tags=[
            {"name": "Users", "description": "User registration, authentication, and management."},
            {"name": "Products", "description": "Product catalog management."},
            {"name": "Health", "description": "Health check endpoints."},
        ],
    )

    from fastapi.openapi.utils import get_openapi

    def custom_openapi() -> dict[str, Any]:
        if app.openapi_schema:
            return app.openapi_schema
        schema = get_openapi(
            title=app.title,
            version=app.version,
            description=app.description,
            routes=app.routes,
            tags=app.openapi_tags,
        )
        schema["components"]["securitySchemes"] = {
            "BearerAuth": {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "JWT",
                "description": "Enter your JWT access token.",
            }
        }
        # Apply BearerAuth globally to all operations
        for path in schema.get("paths", {}).values():
            for operation in path.values():
                operation.setdefault("security", [{"BearerAuth": []}])
        app.openapi_schema = schema
        return app.openapi_schema

    app.openapi = custom_openapi  # type: ignore[method-assign]

    app.state.limiter = limiter
    # slowapi's handler is typed for RateLimitExceeded; Starlette's add_exception_handler
    # wants a handler for any Exception. Correct at runtime, just a stub mismatch.
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]
    app.add_middleware(SlowAPIMiddleware)

    # Browsers reject allow_credentials=True combined with a "*" origin.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=settings.ALLOWED_ORIGINS != ["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.add_middleware(GlobalExceptionHandlerMiddleware)
    register_exception_handlers(app)

    # Outermost middleware, so the request ID is bound before anything else runs.
    app.add_middleware(RequestIDMiddleware)

    configure_tracing(app)

    api_v1_prefix = "/api/v1"
    app.include_router(users.router, prefix=api_v1_prefix)
    app.include_router(products.router, prefix=api_v1_prefix)

    from fastapi import APIRouter

    health_router = APIRouter(tags=["Health"])

    @health_router.get("/health", summary="Health check", description="Returns service health status.")
    async def health_check() -> dict:
        return {
            "status": "healthy",
            "service": settings.APP_NAME,
            "version": settings.APP_VERSION,
        }

    app.include_router(health_router)

    return app


app = create_app()
