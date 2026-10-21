from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/src/bidsmith/settings.py -> repo root is three parents above the package dir
REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=REPO_ROOT / ".env", extra="ignore")

    anthropic_api_key: str | None = None
    # Read as BIDSMITH_ANTHROPIC_BASE_URL so the generic ANTHROPIC_BASE_URL in a parent shell is ignored.
    anthropic_base_url: str = Field("https://api.anthropic.com", validation_alias="BIDSMITH_ANTHROPIC_BASE_URL")
    sam_api_key: str | None = None
    sam_env: str = "production"  # "production" (sam.gov key) or "alpha" (alpha.sam.gov prod-like key)
    sam_max_requests: int = 8  # per fetch; public keys allow only a few requests per day
    include_sample_opportunities: bool = True
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
        """Bundled illustrative samples (SAMPLE-* ids)."""
        return self.data_dir / "fixtures" / "sam_opportunities.json"

    @property
    def sam_live_file(self) -> Path:
        """Results of `bidsmith fetch-sam`, kept separate so samples are never overwritten."""
        return self.data_dir / "fixtures" / f"sam_live_{self.sam_env}.json"


@lru_cache
def get_settings() -> Settings:
    return Settings()
