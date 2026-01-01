from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import Optional


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql://oil_prices:oil_prices_dev@localhost:5432/oil_prices"
    
    # Redis
    redis_url: str = "redis://localhost:6379/0"
    
    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8028
    secret_key: str = "dev_secret_key_change_in_prod"
    log_level: str = "INFO"
    
    # CORS
    cors_origins: list[str] = ["http://localhost:8080", "http://localhost:3000"]
    
    # External APIs
    eia_api_key: Optional[str] = None
    
    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
