"""Utility helpers shared between discover and scrape workflows."""

from __future__ import annotations

import logging
import time
from datetime import date, datetime
from typing import Optional

import requests
from bs4 import BeautifulSoup
from dateutil import parser as date_parser

from .config import SETTINGS


LOGGER = logging.getLogger(__name__)
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_4) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 Safari/605.1.15"
)


def fetch_html(url: str, *, session: Optional[requests.Session] = None) -> str:
    """Fetch a URL using a short polite delay and return the HTML text."""

    LOGGER.debug("Fetching %s", url)
    time.sleep(max(SETTINGS.request_delay, 0))

    sess = session or requests.Session()
    headers = {"User-Agent": USER_AGENT}
    response = sess.get(url, headers=headers, timeout=SETTINGS.request_timeout)
    response.raise_for_status()
    return response.text


def parse_date(value: Optional[str]) -> Optional[date]:
    if not value:
        return None

    try:
        parsed = date_parser.parse(value)
        return parsed.date()
    except (ValueError, OverflowError):
        LOGGER.debug("Unable to parse date from value: %s", value)
        return None


def parse_datetime(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None

    try:
        return date_parser.parse(value)
    except (ValueError, OverflowError):
        LOGGER.debug("Unable to parse datetime from value: %s", value)
        return None


def extract_clean_text(container: BeautifulSoup) -> str:
    """Convert a soup container into a lightly formatted plain-text block."""

    pieces = []
    block_tags = ["p", "blockquote", "li", "h2", "h3"]

    for tag in container.find_all(block_tags):
        text = tag.get_text(" ", strip=True)
        if text:
            pieces.append(text)

    return "\n\n".join(pieces).strip()
