from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Application
    APP_NAME: str = "FastAPI Onion DDD Template"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./dev.db"

    # Redis (token revocation store)
    REDIS_URL: str = "redis://localhost:6379/0"

    # JWT
    JWT_SECRET_KEY: str = "change-me-in-production-super-secret-key"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = 60

    # Observability — structured logging is always on; tracing is opt-in via OTEL_ENABLED
    # (off by default so tests and quick local runs don't need a collector reachable).
    OTEL_ENABLED: bool = False
    OTEL_SERVICE_NAME: str = "fastapi-onion-ddd-template"
    OTEL_EXPORTER_OTLP_ENDPOINT: str = "http://localhost:4318/v1/traces"

    # CORS — "*" can't be combined with credentialed requests; browsers reject it.
    ALLOWED_ORIGINS: list[str] = ["http://localhost:3000"]


settings = Settings()
