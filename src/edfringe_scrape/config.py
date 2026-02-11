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
        default=5000,
        ge=0,
        le=35000,
        description="JavaScript rendering wait time in milliseconds (max 35000)",
    )
    default_year: int = Field(
        default=2026,
        description="Default year for date parsing",
    )


def get_settings() -> Settings:
    """Get application settings.

    Returns:
        Application settings instance
    """
    return Settings()
