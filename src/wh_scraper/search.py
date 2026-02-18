"""CLI helper for semantic search over stored embeddings."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import Iterable, Sequence

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
    parser.add_argument(
        "--to-file",
        metavar="NAME",
        help="Optional base filename to write full chunk text to under searches/",
    )
    parser.add_argument(
        "--separating-lines",
        type=int,
        default=2,
        help="Number of blank lines between chunks in the output file (default: 2)",
    )
    parser.add_argument(
        "--separating-char",
        metavar="CHAR",
        help="Optional single, non-whitespace character used as a separator line",
    )
    return parser


def write_results_to_file(
    results: Sequence[SearchResult],
    target_name: str,
    separating_lines: int,
    separating_char: str | None,
    *,
    query: str,
    limit: int,
) -> Path:
    """Persist raw chunk text plus metadata to searches/<name>.txt."""

    cleaned_name = target_name.strip()
    if not cleaned_name:
        raise ValueError("--to-file name cannot be empty")

    safe_name = Path(cleaned_name).name
    if not safe_name:
        raise ValueError("--to-file name cannot be empty")

    if not safe_name.lower().endswith(".txt"):
        safe_name = f"{safe_name}.txt"

    project_root = Path(__file__).resolve().parents[2]
    output_dir = project_root / "searches"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / safe_name

    line_breaks = "\n" * max(separating_lines, 0)
    separator_parts = ["\n"]
    if line_breaks:
        separator_parts.append(line_breaks)
    if separating_char:
        separator_parts.append(separating_char * 80)
        separator_parts.append("\n")
    separator = "".join(separator_parts)
    # Convert distances (0 = identical) to cosine similarities (1 = identical) for reporting.
    cosine_scores = [1 - result.score for result in results]
    max_similarity = max(cosine_scores, default=0.0)
    min_similarity = min(cosine_scores, default=0.0)
    unique_documents = len({result.document_id for result in results})
    metadata_lines = [
        f"Query: {query}",
        f"Limit: {limit}",
        f"Max cosine similarity: {max_similarity:.4f}",
        f"Min cosine similarity: {min_similarity:.4f}",
        f"Unique documents: {unique_documents}",
    ]
    metadata = "\n".join(metadata_lines).rstrip("\n") + "\n\n"

    chunk_sections = []
    for result in results:
        date_value = result.date_published.isoformat() if result.date_published else "Unknown"
        section_lines = [
            f"Title: {result.title or 'Untitled'}",
            f"Date published: {date_value}",
            f"Document ID: {result.document_id}",
            f"Document URL: {result.url}",
            "",
            result.text.strip(),
        ]
        chunk_sections.append("\n".join(section_lines).rstrip())

    chunk_text = separator.join(chunk_sections)
    if chunk_text and not chunk_text.endswith("\n"):
        chunk_text += "\n"

    output_path.write_text(metadata + chunk_text, encoding="utf-8")
    return output_path


def main(argv: Iterable[str] | None = None) -> None:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )

    if args.limit < 1:
        parser.error("--limit must be >= 1")
    if args.separating_lines < 0:
        parser.error("--separating-lines must be >= 0")
    if args.separating_char is not None:
        if len(args.separating_char) != 1:
            parser.error("--separating-char must be a single character")
        if args.separating_char.isspace():
            parser.error("--separating-char cannot be whitespace")

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

    if args.to_file:
        try:
            path = write_results_to_file(
                results,
                args.to_file,
                args.separating_lines,
                args.separating_char,
                query=args.query,
                limit=args.limit,
            )
        except Exception as exc:  # pragma: no cover - CLI level guard
            LOGGER.error("Unable to write results to file: %s", exc)
            raise SystemExit(1) from exc
        relative_path = path.relative_to(Path(__file__).resolve().parents[2])
        print(f"Wrote {len(results)} chunks to {relative_path}")


if __name__ == "__main__":
    main()
