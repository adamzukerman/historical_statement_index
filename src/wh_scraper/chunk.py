"""CLI entry point for chunking scraped documents."""

from __future__ import annotations

import argparse
import logging
from typing import Iterable

from .config import SETTINGS
from .models import DocumentRepository
from .vectorization import TextChunker


LOGGER = logging.getLogger(__name__)


def chunk_documents(*, limit: int) -> int:
    repo = DocumentRepository()
    chunker = TextChunker(
        max_tokens=SETTINGS.chunk_max_tokens,
        overlap_tokens=SETTINGS.chunk_overlap_tokens,
    )

    documents = repo.list_documents_without_chunks(limit)
    if not documents:
        LOGGER.info("No documents are pending chunking")
        return 0

    processed = 0
    for document in documents:
        chunks = chunker.chunk_text(document.clean_text)
        if not chunks:
            LOGGER.warning("Document %s has no chunkable text, skipping", document.id)
            continue

        repo.insert_document_chunks(document_id=document.id, chunks=chunks)
        processed += 1
        LOGGER.info(
            "Chunked document %s (%s) into %d chunks",
            document.id,
            document.title or "untitled",
            len(chunks),
        )

    LOGGER.info("Chunking complete: %d documents processed", processed)
    return processed


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Chunk scraped documents")
    parser.add_argument(
        "--limit",
        type=int,
        default=25,
        help="Maximum number of documents to chunk in this run",
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

    chunk_documents(limit=args.limit)


if __name__ == "__main__":
    main()
