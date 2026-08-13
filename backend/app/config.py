from functools import lru_cache
from pathlib import Path

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
    search_provider: str = "searxng-search"
    search_cache_dir: Path = Path("/data/uploads/.search-cache")
    search_cache_ttl_seconds: int = Field(default=604_800, ge=60)
    max_upload_size_mb: int = Field(default=200, gt=0)
    upload_dir: Path = Path("/data/uploads")
    cors_allowed_origins: str = "https://projeto-digitacao.netlify.app"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def max_upload_size_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024

    @property
    def allowed_origins(self) -> list[str]:
        return [
            origin.strip().rstrip("/")
            for origin in self.cors_allowed_origins.split(",")
            if origin.strip()
        ]


@lru_cache
def get_settings() -> Settings:
    return Settings()
