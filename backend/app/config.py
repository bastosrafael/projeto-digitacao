from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Projeto Digitação API"
    log_level: str = "INFO"
    omniroute_base_url: str = "http://192.168.15.112:20128/v1"
    omniroute_api_key: str = ""
    omniroute_model: str = "auto/coding:free"
    omniroute_timeout_seconds: float = Field(default=60.0, gt=0, le=300)
    omniroute_max_retries: int = Field(default=2, ge=0, le=5)

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()

