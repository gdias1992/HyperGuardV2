"""Centralized configuration for HyperGuard92.

Settings are loaded from environment variables (optionally populated from a
``.env`` file) using :mod:`pydantic_settings`. Any module that needs a config
value should import :data:`settings` instead of reading ``os.environ`` directly.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

LogLevel = Literal["DEBUG", "INFO", "WARN", "WARNING", "ERROR", "FATAL", "CRITICAL"]


class Settings(BaseSettings):
    """Application settings loaded from env / ``.env``."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    log_level: LogLevel = Field("INFO", description="Minimum log level.")
    log_dir: Path = Field(Path("logs"), description="Directory for log files.")
    log_clear_on_start: bool = Field(
        False, description="Truncate log files when the app starts."
    )

    hg_host: str = Field("127.0.0.1", description="NiceGUI bind address.")
    hg_port: int = Field(8492, ge=1, le=65535, description="NiceGUI TCP port.")
    hg_native: bool = Field(True, description="Run in native desktop window.")

    dry_run: bool = Field(
        False,
        description="When true, never mutate the OS; log intended writes instead.",
    )


settings = Settings()

__all__ = ["Settings", "settings", "LogLevel"]
