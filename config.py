"""Configuration loader for Telegram Video Downloader."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


class ConfigError(Exception):
    """Raised when configuration is invalid or missing."""


def load_config() -> dict:
    """Load configuration from .env file."""
    env_path = Path(".env")
    if not env_path.exists():
        raise ConfigError(
            ".env file not found.\n"
            "Copy .env.example to .env and add API_ID and API_HASH."
        )

    load_dotenv(env_path)

    api_id = os.getenv("API_ID", "").strip()
    api_hash = os.getenv("API_HASH", "").strip()

    if not api_id or not api_id.isdigit():
        raise ConfigError("API_ID is invalid or missing from the .env file")

    if not api_hash or len(api_hash) < 20:
        raise ConfigError("API_HASH is invalid or missing from the .env file")

    return {
        "api_id": int(api_id),
        "api_hash": api_hash,
        "session_name": "teledo",
    }