from pydantic_settings import BaseSettings
from pydantic import validator
from typing import List
from functools import lru_cache
import os


class Settings(BaseSettings):
    database_url: str = "postgresql://nuclear_user:nuclear_pass@localhost:5432/nuclear_forecast"
    redis_url: str = "redis://localhost:6379/0"
    eia_api_key: str = ""
    nerc_api_key: str = ""
    worldbank_api_key: str = ""
    debug: bool = False
    log_level: str = "INFO"
    secret_key: str = "change-this-in-production"
    eia_refresh_interval: int = 60
    nerc_refresh_interval: int = 30
    worldbank_refresh_interval: int = 1440
    forecast_start_year: int = 2025
    forecast_end_year: int = 2050
    model_retrain_interval: int = 24
    jwt_secret_key: str = "change-this-jwt-secret"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    sentry_dsn: str = ""
    prometheus_enabled: bool = True
    allowed_origins: List[str] = ["*"]
    
    @validator('log_level')
    def validate_log_level(cls, v):
        valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if v.upper() not in valid_levels:
            raise ValueError(f'log_level must be one of {valid_levels}')
        return v.upper()
    
    @validator('allowed_origins', pre=True)
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            return [i.strip() for i in v.split(",")]
        return v
    
    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    return Settings()
