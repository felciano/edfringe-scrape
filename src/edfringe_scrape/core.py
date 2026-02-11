"""Core business logic for Edinburgh Fringe scraping."""

from pathlib import Path

from .config import Settings


def ensure_output_dir(settings: Settings) -> Path:
    """Ensure output directory exists.

    Args:
        settings: Application settings

    Returns:
        Path to output directory
    """
    output_path = Path(settings.output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    return output_path
