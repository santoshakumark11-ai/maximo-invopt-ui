"""
Application configuration — all values read from environment variables.
Copy .env.example to .env and fill in the values before running locally.
"""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # ── Maximo MIF ────────────────────────────────────────────────────────────
    # Base URL of the Maximo application server (no trailing slash)
    # e.g. https://manage.maspoc.apps.maspoc.zpih.p1.openshiftapps.com/maximo
    maximo_base_url: str

    # Service-account API key used for all MIF data queries.
    # Generate in Maximo: Profile → API Keys → Add API Key
    maximo_api_key: str

    # Request timeout for MIF OSLC calls (seconds)
    maximo_timeout: int = 30

    # ── JWT ───────────────────────────────────────────────────────────────────
    # HS256 secret — generate with: python -c "import secrets; print(secrets.token_hex(32))"
    jwt_secret: str

    # Token lifetime in seconds (default 8 hours)
    jwt_expire_seconds: int = 28_800

    # ── CORS ─────────────────────────────────────────────────────────────────
    # Comma-separated list of allowed origins for the UI
    # e.g. http://localhost:5173,https://invopt-ui.maspoc.apps.maspoc.zpih.p1.openshiftapps.com
    cors_origins: str = "http://localhost:5173"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    # ── App ───────────────────────────────────────────────────────────────────
    app_env: str = "development"

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
