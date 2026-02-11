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
    output_dir: str = Field(default="output", description="Output directory for data")


def get_settings() -> Settings:
    """Get application settings.

    Returns:
        Application settings instance
    """
    return Settings()
