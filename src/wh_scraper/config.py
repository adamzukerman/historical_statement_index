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

    openai_api_key: Optional[str] = os.getenv("OPENAI_API_KEY") or None
    openai_embedding_model: str = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
    embedding_batch_size: int = int(os.getenv("EMBEDDING_BATCH_SIZE", "64"))
    chunk_max_tokens: int = int(os.getenv("CHUNK_MAX_TOKENS", "400"))
    chunk_overlap_tokens: int = int(os.getenv("CHUNK_OVERLAP_TOKENS", "40"))


SETTINGS = Settings()
