"""Application configuration using Pydantic Settings."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables.

    Environment variables are loaded by direnv from config.toml and 1Password.
    Prefix: EDFRINGE_
    """

    model_config = SettingsConfigDict(
        env_prefix="EDFRINGE_",
        env_nested_delimiter="__",
    )

    # General settings
    debug: bool = Field(default=False, description="Enable debug mode")
    log_level: str = Field(default="INFO", description="Logging level")

    # Scraping settings
    base_url: str = Field(
        default="https://www.edfringe.com",
        description="Edinburgh Fringe website base URL",
    )
    output_dir: str = Field(default="data/raw", description="Output directory for data")

    # Scraping Dog API settings
    scrapingdog_api_key: str | None = Field(
        default=None,
        description="Scraping Dog API key (from 1Password)",
    )
    request_delay_ms: int = Field(
        default=2000,
        description="Delay between requests in milliseconds",
    )
    js_wait_ms: int = Field(
        default=15000,
        ge=0,
        le=35000,
        description="JavaScript rendering wait time in milliseconds (max 35000)",
    )
    default_year: int = Field(
        default=2026,
        description="Default year for date parsing",
    )

    # Email settings for daily updates
    email_to: str | None = Field(
        default=None,
        description="Recipient email address for daily updates",
    )
    email_from: str | None = Field(
        default=None,
        description="Sender email address (defaults to smtp_user)",
    )
    smtp_host: str = Field(
        default="smtp.gmail.com",
        description="SMTP server hostname",
    )
    smtp_port: int = Field(
        default=587,
        description="SMTP server port (587 for TLS, 465 for SSL)",
    )
    smtp_user: str | None = Field(
        default=None,
        description="SMTP username",
    )
    smtp_password: str | None = Field(
        default=None,
        description="SMTP password or app password (from 1Password)",
    )

    # Snapshot settings
    snapshot_dir: str = Field(
        default="data/snapshots",
        description="Directory for daily snapshots",
    )

    # Current/canonical data settings
    current_dir: str = Field(
        default="data/current",
        description="Directory for canonical current-state files",
    )


def get_settings() -> Settings:
    """Get application settings.

    Returns:
        Application settings instance
    """
    return Settings()
