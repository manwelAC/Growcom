"""Configuration settings for the Central Data API."""

from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    central_api_host: str = "127.0.0.1"
    central_api_port: int = 8000
    internal_api_key: str = "growcom-dev-internal-key"

    items_dat_path: Path = PROJECT_ROOT / "services" / "central-data-api" / "data" / "items.dat"
    textures_dir: Path = PROJECT_ROOT / "services" / "central-data-api" / "data" / "textures"

    event_timezone: str = "Asia/Manila"

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    def model_post_init(self, __context) -> None:
        if not self.items_dat_path.is_absolute():
            self.items_dat_path = PROJECT_ROOT / self.items_dat_path
        if not self.textures_dir.is_absolute():
            self.textures_dir = PROJECT_ROOT / self.textures_dir


settings = Settings()
