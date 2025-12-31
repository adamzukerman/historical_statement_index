"""Configuration helpers for the scraper package."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

from dotenv import load_dotenv


load_dotenv()


@dataclass(frozen=True)
class Settings:
    """Holds runtime configuration derived from the environment."""

    db_host: str = os.getenv("DB_HOST", "localhost")
    db_port: int = int(os.getenv("DB_PORT", "5432"))
    db_name: str = os.getenv("DB_NAME", "wh_briefings")
    db_user: str = os.getenv("DB_USER", "wh_user")
    db_password: Optional[str] = os.getenv("DB_PASSWORD") or None

    request_timeout: int = int(os.getenv("REQUEST_TIMEOUT_SECONDS", "20"))
    request_delay: float = float(os.getenv("REQUEST_DELAY_SECONDS", "1.0"))


SETTINGS = Settings()

