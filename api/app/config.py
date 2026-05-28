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

    # ── Q1.1: Persistence ────────────────────────────────────────────────────
    # SQLAlchemy URL.  Default is an on-disk SQLite that lives next to the
    # uvicorn working directory; production should set DATABASE_URL to a
    # postgresql+asyncpg://... DSN.  When persistence is unavailable the API
    # silently falls back to the in-memory store (existing demo behaviour).
    database_url: str = "sqlite+aiosqlite:///./invopt.db"

    # Toggle DB persistence on/off.  When false the API never touches the DB
    # and behaves identically to the pre-Q1 build — useful for the live demo.
    persistence_enabled: bool = True

    # ── Q1.1: WORM audit log ─────────────────────────────────────────────────
    # HMAC secret used to sign each audit row.  Independent rotation: changing
    # this does NOT invalidate historical audit chains because each row
    # carries the signature it was written with.
    audit_hmac_secret: str = "change-me-audit-hmac-secret"

    # ── Q1.1: Writeback saga ─────────────────────────────────────────────────
    # Master switch for the Maximo MIF writeback path.  When false, /approve
    # only changes the recommendation status (current behaviour); when true,
    # /approve fans out to writeback.saga.apply() which posts to MXINV_INVENTORY_V1.
    writeback_enabled: bool = False

    # Name of the custom Object Structure used for writeback (DLD Appendix A).
    writeback_os_name: str = "MXINV_INVENTORY_V1"

    # Per-saga retry policy on Maximo failures.
    writeback_max_retries: int = 3
    writeback_retry_backoff_ms: int = 500

    # ── Q1.1: Observability ──────────────────────────────────────────────────
    prometheus_enabled: bool = True
    log_json: bool = True
    log_level: str = "INFO"

    # ── Q1.2: Forecasting & optimisation ─────────────────────────────────────
    # Recommendation emitted only when the proposed value differs from the
    # current value by more than this fraction (DLD §13 default 5%).
    recommendation_delta_threshold_pct: float = 5.0

    # Service-level targets β routed by criticality (DLD §4.3).
    service_level_non_critical:    float = 0.95
    service_level_critical:        float = 0.99
    service_level_safety_critical: float = 0.995

    # When true, the per-pattern statsforecast models are loaded; when false
    # (or when statsforecast is not installed), the API uses the NumPy
    # bootstrap path inside forecasting.service.
    forecasting_use_statsforecast: bool = True

    # ── Q2.1: Substitution recommender ───────────────────────────────────
    # Embedding model for item-description similarity.  sentence-transformers
    # model name; only loaded when sentence-transformers is installed.
    substitution_embedding_model: str = "all-MiniLM-L6-v2"
    substitution_top_k: int = 10

    # ── Q2.1: Agentic auto-apply ─────────────────────────────────────────
    # Master switch for the agent.  Default OFF — operator flips it after
    # confirming the recommendation quality and the writeback path.
    agent_auto_apply_enabled: bool = False
    # Only auto-apply recs below this working-capital delta (USD).
    agent_max_delta_wc: float = 5_000.0
    # Only auto-apply these criticality levels.
    agent_allowed_criticalities: str = "LOW"
    # Only auto-apply these recommendation types.
    agent_allowed_types: str = "ROP,SS,EOQ"

    # ── Q2.2: LLM gateway ───────────────────────────────────────────────
    # Provider: "mock" (default, no LLM call), "azure_openai", "watsonx".
    llm_provider: str = "mock"
    llm_endpoint: str = ""
    llm_api_key: str = ""
    llm_model: str = ""            # e.g. "gpt-4o-mini" or "ibm/granite-13b-chat-v2"
    llm_deployment: str = ""       # Azure OpenAI deployment name (only for azure_openai)
    llm_project_id: str = ""       # watsonx project ID (only for watsonx)
    llm_max_tokens: int = 512
    llm_temperature: float = 0.3   # low temp for factual rationale

    # ── Q1.2: Scheduler ──────────────────────────────────────────────────────
    # When true and APScheduler is installed, the orchestrator runs on the
    # configured cron.  Default false so the first run is always operator-
    # initiated via POST /v1/recommendations:run.
    scheduler_enabled: bool = False
    # Cron expression (5-field form: min hour day-of-month month day-of-week).
    # Default: every day at 02:00 local time (DLD §4.1 ForecastAllItemsWorkflow).
    scheduler_cron: str = "0 2 * * *"
    # History months to pass to the orchestrator on each run.
    scheduler_history_months: int = 24


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
