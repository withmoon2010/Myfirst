from __future__ import annotations

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # API Keys
    anthropic_api_key: str = ""
    newsapi_key: str = ""

    # Claude Model
    claude_model: str = "claude-sonnet-4-20250514"

    # Email (SMTP)
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    sender_email: str = ""
    sender_name: str = "Daily Macro Brief"
    recipient_emails: str = ""  # comma-separated

    # Newsletter Settings
    news_lookback_hours: int = 24
    max_items_per_source: int = 50
    newsapi_enabled: bool = True
    log_level: str = "INFO"

    # Regions
    primary_regions: list[str] = ["US", "CN"]
    secondary_regions: list[str] = ["JP", "KR", "TW", "IN", "SEA", "LATAM"]

    @property
    def all_regions(self) -> list[str]:
        return self.primary_regions + self.secondary_regions + ["Global"]

    @property
    def recipient_list(self) -> list[str]:
        return [e.strip() for e in self.recipient_emails.split(",") if e.strip()]

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}
