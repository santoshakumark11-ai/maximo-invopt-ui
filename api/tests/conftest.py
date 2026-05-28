"""
pytest configuration for the api test suite.

Sets the required env vars BEFORE the app modules are imported so
pydantic_settings doesn't complain about missing values.  This keeps every
test file independent of a real .env.
"""
import os

os.environ.setdefault("MAXIMO_BASE_URL", "https://maximo.example.test/maximo")
os.environ.setdefault("MAXIMO_API_KEY",  "test-key")
os.environ.setdefault("JWT_SECRET",      "test-secret-for-jwt-please-rotate")
os.environ.setdefault("DATABASE_URL",    "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("PERSISTENCE_ENABLED", "false")  # default off in unit tests
os.environ.setdefault("AUDIT_HMAC_SECRET", "test-hmac-secret")
os.environ.setdefault("PROMETHEUS_ENABLED", "false")
os.environ.setdefault("LOG_JSON",        "false")
