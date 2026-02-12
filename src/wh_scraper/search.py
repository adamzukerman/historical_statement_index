"""CLI helper for semantic search over stored embeddings."""

from __future__ import annotations

import argparse
import logging
from typing import Iterable

from .models import DocumentRepository, SearchResult
from .vectorization import OpenAIEmbeddingClient


LOGGER = logging.getLogger(__name__)


def format_result(result: SearchResult, index: int) -> str:
    header = f"{index}. {result.title or 'Untitled'}"
    meta = []
    if result.date_published:
        meta.append(result.date_published.isoformat())
    meta.append(result.admin)
    meta_text = ", ".join(meta)
    snippet = result.text.strip().replace("\n", " ")
    if len(snippet) > 280:
        snippet = snippet[:277].rstrip() + "..."
    return (
        f"{header} ({meta_text})\n"
        f"   score={result.score:.4f} chunk={result.chunk_index} url={result.url}\n"
        f"   {snippet}"
    )


def search(query: str, *, limit: int) -> list[SearchResult]:
    cleaned = query.strip()
    if not cleaned:
        raise ValueError("Query cannot be empty")

    client = OpenAIEmbeddingClient()
    batch = client.embed_texts([cleaned])
    if not batch.vectors:
        return []

    repo = DocumentRepository()
    return repo.search_chunks_by_embedding(embedding=batch.vectors[0], limit=limit)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Semantic search over WH transcripts")
    parser.add_argument("query", help="Free text to search for")
    parser.add_argument(
        "--limit",
        type=int,
        default=5,
        help="Number of chunks to return",
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

    try:
        results = search(args.query, limit=args.limit)
    except Exception as exc:
        LOGGER.error("Search failed: %s", exc)
        raise SystemExit(1) from exc

    if not results:
        print("No matches found")
        return

    for index, result in enumerate(results, start=1):
        print(format_result(result, index))
        print()


if __name__ == "__main__":
    main()
