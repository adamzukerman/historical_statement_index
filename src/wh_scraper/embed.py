"""CLI entry point for generating embeddings for document chunks."""

from __future__ import annotations

import argparse
import logging
from typing import Iterable, List

from .models import DocumentRepository
from .vectorization import OpenAIEmbeddingClient


LOGGER = logging.getLogger(__name__)


def embed_pending_chunks(*, limit: int) -> int:
    repo = DocumentRepository()
    pending_chunks = repo.list_chunks_without_embeddings(limit)
    if not pending_chunks:
        LOGGER.info("No chunks awaiting embeddings")
        return 0

    client = OpenAIEmbeddingClient()
    total_updated = 0
    texts: List[str] = [chunk.text for chunk in pending_chunks]

    try:
        batch = client.embed_in_batches(texts)
    except Exception as exc:  # pragma: no cover - network path
        LOGGER.error("Embedding API error: %s", exc)
        return 0

    for chunk, vector in zip(pending_chunks, batch.vectors):
        repo.update_chunk_embedding(
            chunk_id=chunk.id,
            embedding=vector,
            embedding_model=batch.model,
            embedding_dimensions=batch.dimensions,
        )
        total_updated += 1
        LOGGER.debug(
            "Stored embedding for chunk %s (document %s, index %s)",
            chunk.id,
            chunk.document_id,
            chunk.chunk_index,
        )

    LOGGER.info("Embedded %d chunks", total_updated)
    return total_updated


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate embeddings for document chunks")
    parser.add_argument(
        "--limit",
        type=int,
        default=200,
        help="Maximum number of chunk rows to embed in this run",
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

    embed_pending_chunks(limit=args.limit)


if __name__ == "__main__":
    main()
