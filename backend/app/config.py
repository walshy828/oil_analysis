from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import Optional
import logging
import secrets

logger = logging.getLogger(__name__)

_INSECURE_DEFAULT_KEY = "dev-insecure-key-change-me"


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql://oil_prices:oil_prices_dev@localhost:5432/oil_prices"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8028
    secret_key: str = _INSECURE_DEFAULT_KEY
    log_level: str = "INFO"

    # Auth — set API_KEY env var; required in production
    api_key: str = _INSECURE_DEFAULT_KEY

    # CORS
    cors_origins: list[str] = ["http://localhost:8080", "http://localhost:3000"]

    # External APIs
    eia_api_key: Optional[str] = None

    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    s = Settings()
    if s.api_key == _INSECURE_DEFAULT_KEY:
        logger.warning(
            "API_KEY is using the insecure default value. "
            "Set the API_KEY environment variable before exposing this service. "
            "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
        )
    if s.secret_key == _INSECURE_DEFAULT_KEY:
        logger.warning("SECRET_KEY is using the insecure default value. Set SECRET_KEY in your environment.")
    return s


settings = get_settings()
