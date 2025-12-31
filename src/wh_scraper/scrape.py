"""Detail page scraper that enriches pending documents."""

from __future__ import annotations

import argparse
import logging
from typing import Iterable, Optional

import requests
from bs4 import BeautifulSoup

from .models import DocumentRepository
from .utils import extract_clean_text, fetch_html, parse_date, parse_datetime


LOGGER = logging.getLogger(__name__)


def _class_contains(value: object, needle: str) -> bool:
    if isinstance(value, str):
        return needle in value.lower()
    if isinstance(value, (list, tuple, set)):
        return any(isinstance(part, str) and needle in part.lower() for part in value)
    return False


def _select_main_content(soup: BeautifulSoup) -> BeautifulSoup:
    selectors = [
        "article .entry-content",
        "article .page-content",
        "article .content",
        ".entry-content",
        ".page-content",
        ".content",
    ]

    for selector in selectors:
        node = soup.select_one(selector)
        if node:
            return node

    article = soup.find("article")
    if article:
        return article
    if soup.body:
        return soup.body
    return soup


def _extract_location(soup: BeautifulSoup) -> Optional[str]:
    candidate = soup.find(class_=lambda c: _class_contains(c, "location"))
    if candidate:
        text = candidate.get_text(" ", strip=True)
        if text:
            return text

    strong_labels = soup.find_all("strong")
    for strong in strong_labels:
        label = strong.get_text(strip=True)
        if label and label.lower().startswith("location"):
            parent_text = strong.parent.get_text(" ", strip=True)
            return parent_text

    return None


def parse_detail_page(html: str) -> dict:
    soup = BeautifulSoup(html, "lxml")
    main_content = _select_main_content(soup)

    title_el = soup.find("h1") or main_content.find("h1")
    title = title_el.get_text(strip=True) if title_el else None

    time_el = soup.find("time") or main_content.find("time")
    datetime_value = None
    date_value = None
    if time_el:
        date_source = time_el.get("datetime") or time_el.get_text(strip=True)
        datetime_value = parse_datetime(date_source)
        date_value = datetime_value.date() if datetime_value else parse_date(date_source)
    else:
        date_block = soup.find(class_=lambda c: _class_contains(c, "date"))
        if date_block:
            date_value = parse_date(date_block.get_text(strip=True))

    clean_text = extract_clean_text(main_content)
    if not clean_text:
        clean_text = soup.get_text(" ", strip=True)

    raw_html = str(main_content)
    location = _extract_location(soup)

    return {
        "title": title,
        "date_published": date_value,
        "datetime_published": datetime_value,
        "location": location,
        "raw_html": raw_html,
        "clean_text": clean_text,
    }


def scrape(*, limit: int) -> None:
    repo = DocumentRepository()
    pending = repo.list_pending(limit)
    if not pending:
        LOGGER.info("No pending documents found")
        return

    session = requests.Session()
    successes = 0

    for document in pending:
        LOGGER.info("Scraping %s", document.url)
        try:
            html = fetch_html(document.url, session=session)
            parsed = parse_detail_page(html)
            repo.mark_scraped(document_id=document.id, **parsed)
            successes += 1
        except requests.RequestException as exc:
            LOGGER.error("Network error for %s: %s", document.url, exc)
            repo.mark_error(document_id=document.id, error=str(exc))
        except Exception as exc:  # pragma: no cover - defensive guard
            LOGGER.exception("Failed parsing %s", document.url)
            repo.mark_error(document_id=document.id, error=str(exc))

    LOGGER.info("Scrape completed: %d succeeded, %d attempted", successes, len(pending))


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Scrape pending document detail pages")
    parser.add_argument(
        "--limit",
        type=int,
        default=100,
        help="Maximum number of pending records to process",
    )
    return parser


def main(argv: Iterable[str] | None = None) -> None:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )

    if args.limit < 1:
        parser.error("--limit must be >= 1")

    scrape(limit=args.limit)


if __name__ == "__main__":
    main()
