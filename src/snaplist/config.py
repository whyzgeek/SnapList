import os
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "SnapList"
    host: str = "127.0.0.1"
    port: int = 8000

    # "mock" runs the full flow offline (no keys, no network); "litellm" routes live.
    llm_provider: str = "mock"

    vision_model: str = "gemma3:4b"
    text_model: str = "gemma3:4b"

    litellm_base_url: str | None = None
    litellm_api_key: str | None = None

    # Local llama.cpp router (OpenAI-compatible). Used only for text generation,
    # so the local router can carry text while vision still routes to another
    # base (e.g. OpenRouter). Defaults to the router's documented address.
    text_base_url: str | None = "http://127.0.0.1:18080/v1"
    text_api_key: str | None = None

    cloud_vision_enabled: bool = False
    cloud_text_enabled: bool = False
    cloud_vision_model: str = "claude-3-5-sonnet-latest"
    cloud_text_model: str = "claude-3-5-sonnet-latest"

    lan_mode_enabled: bool = False
    lan_access_token: str | None = None

    secret_key_name: str = "snaplist_secret"
    db_path: str = "data/snaplist.db"

    @property
    def photo_dir(self) -> str:
        """Persistent photo storage, next to the database (never /tmp)."""
        import tempfile
        if not self.db_path or self.db_path == ":memory:":
            return os.path.join(tempfile.gettempdir(), "snaplist_photos")
        return os.path.join(os.path.dirname(os.path.abspath(self.db_path)), "photos")

    def uses_cloud(self, job_kind: str) -> bool:
        """Off-machine (cloud) use is opt-in and flagged per job type."""
        if job_kind == "vision":
            return self.cloud_vision_enabled
        if job_kind == "text":
            return self.cloud_text_enabled
        return False


@lru_cache
def get_settings() -> Settings:
    return Settings()
