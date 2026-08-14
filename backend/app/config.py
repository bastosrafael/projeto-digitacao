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
    omniroute_vision_model: str = "oc/mimo-v2.5-free"
    omniroute_timeout_seconds: float = Field(default=60.0, gt=0, le=300)
    omniroute_max_retries: int = Field(default=2, ge=0, le=5)
    search_provider: str = "searxng-search"
    search_cache_dir: Path = Path("/data/uploads/.search-cache")
    search_cache_ttl_seconds: int = Field(default=604_800, ge=60)
    fetch_cache_dir: Path = Path("/data/uploads/.fetch-cache")
    fetch_cache_ttl_seconds: int = Field(default=604_800, ge=60)
    fetch_timeout_seconds: float = Field(default=15.0, gt=0, le=60)
    fetch_max_bytes: int = Field(default=3_145_728, ge=65_536, le=5_242_880)
    llm_analysis_cache_dir: Path = Path("/data/uploads/.llm-analysis-cache")
    llm_analysis_cache_ttl_seconds: int = Field(default=604_800, ge=60)
    llm_analysis_timeout_seconds: float = Field(default=90.0, gt=0, le=180)
    llm_analysis_max_input_chars: int = Field(default=18_000, ge=4_000, le=40_000)
    visual_analysis_cache_dir: Path = Path("/data/uploads/.visual-analysis-cache")
    visual_analysis_cache_ttl_seconds: int = Field(default=604_800, ge=60)
    visual_analysis_timeout_seconds: float = Field(default=90.0, gt=0, le=180)
    visual_image_max_bytes: int = Field(default=1_048_576, ge=65_536, le=2_097_152)
    visual_image_max_side: int = Field(default=1280, ge=512, le=1600)
    multimodal_analysis_cache_dir: Path = Path("/data/uploads/.multimodal-analysis-cache")
    multimodal_analysis_cache_ttl_seconds: int = Field(default=604_800, ge=60)
    multimodal_analysis_timeout_seconds: float = Field(default=90.0, gt=0, le=180)
    multimodal_analysis_max_input_chars: int = Field(default=20_000, ge=4_000, le=40_000)
    wash_label_cache_dir: Path = Path("/data/uploads/.wash-label-cache")
    wash_label_cache_ttl_seconds: int = Field(default=604_800, ge=60)
    hangtag_cache_dir: Path = Path("/data/uploads/.hangtag-cache")
    hangtag_cache_ttl_seconds: int = Field(default=604_800, ge=60)
    labels_multimodal_cache_dir: Path = Path("/data/uploads/.labels-multimodal-cache")
    labels_multimodal_cache_ttl_seconds: int = Field(default=604_800, ge=60)
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
