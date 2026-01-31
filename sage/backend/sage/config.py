"""Configuration settings for Sage."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Application
    app_name: str = "Sage"
    app_version: str = "0.1.0"
    debug: bool = False
    secret_key: str = "change-me-in-production"

    # Database
    database_url: str = "postgresql+asyncpg://sage:sagepassword@localhost:5432/sage"

    # Vector database
    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "emails"

    # Redis
    redis_url: str = "redis://localhost:6379"

    # Anthropic
    anthropic_api_key: str = ""
    claude_model: str = "claude-sonnet-4-20250514"

    # Google OAuth
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/api/v1/auth/google/callback"

    # External APIs
    fireflies_api_key: str = ""
    alpha_vantage_api_key: str = ""

    # JWT
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24 * 7  # 7 days

    # Email sync
    email_sync_interval_minutes: int = 5
    email_sync_max_results: int = 100
    email_sync_labels: list[str] = ["INBOX", "SENT"]  # Gmail system labels to sync
    email_sync_custom_labels: list[str] = ["Signal"]  # Custom labels to sync

    # Follow-up settings
    followup_reminder_days: int = 2
    followup_escalation_days: int = 7

    # Briefing settings
    morning_briefing_hour: int = 6
    morning_briefing_minute: int = 30
    timezone: str = "America/New_York"

    # Orchestrator settings
    use_orchestrator: bool = True  # Feature flag to enable orchestrator (vs direct Claude)


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
