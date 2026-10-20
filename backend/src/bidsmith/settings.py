from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/src/bidsmith/settings.py -> repo root is three parents above the package dir
REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=REPO_ROOT / ".env", extra="ignore")

    anthropic_api_key: str | None = None
    sam_api_key: str | None = None
    database_url: str = "postgresql+psycopg://bidsmith:bidsmith@localhost:5433/bidsmith"

    model_fast: str = "claude-haiku-5-5"
    model_smart: str = "claude-opus-5-5"
    smart_effort: str = "high"

    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_dim: int = 384

    config_dir: Path = REPO_ROOT / "config"
    data_dir: Path = REPO_ROOT / "data"

    @property
    def profiles_dir(self) -> Path:
        return self.config_dir / "profiles"

    @property
    def cost_dir(self) -> Path:
        return self.data_dir / "cost"

    @property
    def sam_fixture(self) -> Path:
        return self.data_dir / "fixtures" / "sam_opportunities.json"


@lru_cache
def get_settings() -> Settings:
    return Settings()
