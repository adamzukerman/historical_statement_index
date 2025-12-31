"""Listing page crawler that seeds the documents table."""

from __future__ import annotations

import argparse
import logging
from typing import Iterable, List
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from .models import DocumentListing, DocumentRepository
from .utils import fetch_html, parse_date


LOGGER = logging.getLogger(__name__)
LISTING_ROOT = "https://bidenwhitehouse.archives.gov/briefing-room/press-briefings/"


def _class_contains(value: object, needle: str) -> bool:
    if isinstance(value, str):
        return needle in value.lower()
    if isinstance(value, (list, tuple, set)):
        return any(isinstance(part, str) and needle in part.lower() for part in value)
    return False


def build_listing_url(page: int) -> str:
    if page <= 1:
        return LISTING_ROOT
    return urljoin(LISTING_ROOT, f"page/{page}/")


def parse_listing(html: str) -> List[DocumentListing]:
    soup = BeautifulSoup(html, "lxml")
    articles = soup.select("article")
    results: List[DocumentListing] = []

    for article in articles:
        header = article.find(["h2", "h3"])
        if not header:
            continue

        anchor = header.find("a", href=True)
        if not anchor:
            continue

        full_url = urljoin(LISTING_ROOT, anchor["href"].strip())
        title = anchor.get_text(strip=True) or None

        time_el = article.find("time")
        date_source = None
        if time_el:
            date_source = time_el.get("datetime") or time_el.get_text(strip=True)
        else:
            date_candidate = article.find(class_=lambda c: _class_contains(c, "date"))
            if date_candidate:
                date_source = date_candidate.get_text(strip=True)

        results.append(
            DocumentListing(
                url=full_url,
                title=title,
                date_published=parse_date(date_source),
            )
        )

    return results


def discover(*, start_page: int, end_page: int) -> int:
    repo = DocumentRepository()
    session = requests.Session()
    total_records = 0

    for page in range(start_page, end_page + 1):
        listing_url = build_listing_url(page)
        LOGGER.info("Fetching listing page %s", listing_url)

        try:
            html = fetch_html(listing_url, session=session)
        except requests.RequestException as exc:  # pragma: no cover - network error path
            LOGGER.error("Failed to fetch %s: %s", listing_url, exc)
            continue

        listings = parse_listing(html)
        if not listings:
            LOGGER.warning("No listings found for %s", listing_url)
            continue

        repo.upsert_listings(listings)
        total_records += len(listings)
        LOGGER.info("Processed %d listings from page %d", len(listings), page)

    LOGGER.info("Completed discover run: %d records touched", total_records)
    return total_records


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Discover press briefing URLs")
    parser.add_argument("--start-page", type=int, default=1, help="First listing page to crawl")
    parser.add_argument(
        "--end-page",
        type=int,
        default=116,
        help="Last listing page to crawl (inclusive)",
    )
    return parser


def main(argv: Iterable[str] | None = None) -> None:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )

    if args.start_page < 1:
        parser.error("--start-page must be >= 1")
    if args.end_page < args.start_page:
        parser.error("--end-page must be >= --start-page")

    discover(start_page=args.start_page, end_page=args.end_page)


if __name__ == "__main__":
    main()
