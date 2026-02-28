"""CLI helper for semantic search over stored embeddings."""

from __future__ import annotations

import argparse
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Sequence

from openai import OpenAI

from .config import SETTINGS
from .models import DocumentRepository, SearchResult
from .vectorization import OpenAIEmbeddingClient


LOGGER = logging.getLogger(__name__)


@dataclass
class LLMJudgment:
    """Outcome returned by the relevance model."""

    response: str
    valid_response: bool
    explanation: str | None = None


@dataclass
class AdvancedSearchResult:
    """Enriches ANN results with judgments from the relevance model."""

    chunk: SearchResult
    judgment: LLMJudgment


@dataclass
class SearchOutput:
    """Represents a row returned to the CLI or file writer."""

    chunk: SearchResult
    judgment: LLMJudgment | None = None


def format_result(output: SearchOutput, index: int) -> str:
    result = output.chunk
    judgment = output.judgment
    header = f"{index}. {result.title or 'Untitled'}"
    meta = []
    if result.date_published:
        meta.append(result.date_published.isoformat())
    meta.append(result.admin)
    meta_text = ", ".join(meta)
    snippet = result.text.strip().replace("\n", " ")
    if len(snippet) > 280:
        snippet = snippet[:277].rstrip() + "..."
    lines = [
        f"{header} ({meta_text})",
        f"   score={result.score:.4f} chunk={result.chunk_index} url={result.url}",
        f"   {snippet}",
    ]
    if judgment:
        if judgment.valid_response:
            judgment_line = f"   LLM relevance: {judgment.response}"
        else:
            judgment_line = f"   LLM response invalid: {judgment.response or 'empty'}"
        if judgment.explanation:
            judgment_line += f" ({judgment.explanation})"
        lines.append(judgment_line)
    return "\n".join(lines)


def search(
    query: str,
    *,
    limit: int,
    admin_filter: Sequence[str] | None = None,
) -> list[SearchResult]:
    cleaned = query.strip()
    if not cleaned:
        raise ValueError("Query cannot be empty")

    client = OpenAIEmbeddingClient()
    batch = client.embed_texts([cleaned])
    if not batch.vectors:
        return []

    repo = DocumentRepository()
    return repo.search_chunks_by_embedding(
        embedding=batch.vectors[0],
        limit=limit,
        admins=tuple(admin_filter) if admin_filter else None,
    )


def advanced_search(
    query: str,
    *,
    limit: int,
    admin_filter: Sequence[str] | None = None,
) -> list[AdvancedSearchResult]:
    """Run ANN search followed by an LLM-based relevance judge."""

    initial_results = search(query, limit=limit, admin_filter=admin_filter)
    if not initial_results:
        return []

    judge = LLMRelevanceJudge()
    judgments = judge.judge(query, initial_results)
    return judgments


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
        "--advanced",
        action="store_true",
        help="Use an LLM to filter ANN matches for higher precision",
    )
    parser.add_argument(
        "--include-rejected",
        action="store_true",
        help="When combined with --advanced and --to-file, append LLM 'NO' chunks after accepted ones",
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
    results: Sequence[SearchOutput],
    target_name: str,
    separating_lines: int,
    separating_char: str | None,
    *,
    query: str,
    limit: int,
) -> Path:
    """Persist raw chunk text plus metadata (including LLM judgments) to searches/<name>.txt."""

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
    cosine_scores = [1 - output.chunk.score for output in results]
    max_similarity = max(cosine_scores, default=0.0)
    min_similarity = min(cosine_scores, default=0.0)
    unique_documents = len({output.chunk.document_id for output in results})
    has_judgments = any(output.judgment for output in results)
    valid_judgments = [
        output for output in results if output.judgment and output.judgment.valid_response
    ]
    accepted = [
        output
        for output in valid_judgments
        if output.judgment and output.judgment.response == "YES"
    ]
    rejected = [
        output
        for output in valid_judgments
        if output.judgment and output.judgment.response == "NO"
    ]
    metadata_lines = [
        f"Query: {query}",
        f"Limit: {limit}",
        f"Max cosine similarity: {max_similarity:.4f}",
        f"Min cosine similarity: {min_similarity:.4f}",
        f"Unique documents: {unique_documents}",
    ]
    if has_judgments:
        metadata_lines.extend(
            [
                f"LLM valid responses: {len(valid_judgments)}/{len(results)}",
                f"LLM accepted (YES): {len(accepted)}",
                f"LLM rejected (NO): {len(rejected)}",
            ]
        )
    metadata = "\n".join(metadata_lines).rstrip("\n") + "\n\n"

    chunk_sections = []
    for output in results:
        chunk = output.chunk
        date_value = chunk.date_published.isoformat() if chunk.date_published else "Unknown"
        section_lines = [
            f"Title: {chunk.title or 'Untitled'}",
            f"Date published: {date_value}",
            f"Document ID: {chunk.document_id}",
            f"Document URL: {chunk.url}",
            f"Chunk index: {chunk.chunk_index}",
            f"Cosine distance: {chunk.score:.6f}",
        ]
        if output.judgment:
            section_lines.append(f"LLM valid response: {output.judgment.valid_response}")
            section_lines.append(f"LLM relevance: {output.judgment.response or 'N/A'}")
            if output.judgment.explanation:
                section_lines.append(f"LLM explanation: {output.judgment.explanation}")
        section_lines.extend(["", chunk.text.strip()])
        chunk_sections.append("\n".join(section_lines).rstrip())

    chunk_text = separator.join(chunk_sections)
    if chunk_text and not chunk_text.endswith("\n"):
        chunk_text += "\n"

    output_path.write_text(metadata + chunk_text, encoding="utf-8")
    return output_path


def trim_text(text: str, max_words: int) -> str:
    words = text.split()
    if len(words) <= max_words:
        return text.strip()
    trimmed = " ".join(words[:max_words]).strip()
    if not trimmed:
        return text.strip()
    return f"{trimmed}..."


class LLMRelevanceJudge:
    """Batches ANN hits through a chat model to confirm relevance."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str | None = None,
        batch_size: int | None = None,
        max_words: int | None = None,
    ) -> None:
        key = api_key or SETTINGS.openai_api_key
        if not key:
            raise RuntimeError("OPENAI_API_KEY is required for advanced search")

        self.model = model or SETTINGS.openai_relevance_model
        self.batch_size = batch_size or SETTINGS.relevance_batch_size
        self.max_words = max_words or SETTINGS.relevance_max_words
        self.client = OpenAI(api_key=key)

    def judge(self, query: str, results: Sequence[SearchResult]) -> list[AdvancedSearchResult]:
        enriched: list[AdvancedSearchResult] = []
        if not results:
            return enriched

        trimmed_chunks: list[tuple[SearchResult, str]] = [
            (result, trim_text(result.text, self.max_words)) for result in results
        ]
        for start in range(0, len(trimmed_chunks), self.batch_size):
            batch = trimmed_chunks[start : start + self.batch_size]
            prompt = self._build_prompt(query, batch)
            response_text = self._invoke(prompt)
            judgments = self._parse_response(response_text, expected=len(batch))
            for (result, _), judgment in zip(batch, judgments):
                enriched.append(AdvancedSearchResult(chunk=result, judgment=judgment))

        return enriched

    def _build_prompt(self, query: str, batch: Sequence[tuple[SearchResult, str]]) -> str:
        sections = []
        for offset, (result, trimmed_text) in enumerate(batch, start=1):
            published = result.date_published.isoformat() if result.date_published else "Unknown"
            sections.append(
                f"Chunk {offset} (title: {result.title or 'Untitled'}, date: {published}):\n{trimmed_text}"
            )

        instructions = (
            "You are a precise relevance judge. "
            "For each chunk determine if it directly helps answer the query.\n"
            "Respond with a JSON array in the same order as the chunks. "
            "Each array entry must be an object with:\n"
            '{"answer":"YES" or "NO","explanation":"short reason"}\n'
            "Only answer YES when the chunk is clearly helpful. "
            "If the chunk is clearly helpful, additionally state what part of the query it relates to. "
            "Keep in mind that if the query is nonsense, then nothing should be helpful to answering the query. "
        )
        sections_text = "\n\n".join(sections)
        return f"{instructions}\n\nQuery:\n{query.strip()}\n\nChunks:\n{sections_text}"

    def _invoke(self, prompt: str) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            temperature=0,
            messages=[
                {
                    "role": "system",
                    "content": "You judge relevance and only reply with JSON that matches the request.",
                },
                {"role": "user", "content": prompt},
            ],
        )
        message = response.choices[0].message.content
        return message.strip() if message else ""

    def _parse_response(self, payload_text: str, *, expected: int) -> list[LLMJudgment]:
        cleaned_text = self._strip_code_fence(payload_text)
        if not cleaned_text:
            return [
                LLMJudgment(response="empty response from model", valid_response=False) for _ in range(expected)
            ]

        try:
            payload = json.loads(cleaned_text)
        except json.JSONDecodeError:
            return [
                LLMJudgment(response=payload_text.strip(), valid_response=False)
                for _ in range(expected)
            ]

        if isinstance(payload, dict):
            if isinstance(payload.get("answers"), list):
                payload = payload["answers"]
            elif isinstance(payload.get("results"), list):
                payload = payload["results"]
            else:
                payload = [payload]

        if not isinstance(payload, list):
            payload = [payload]

        judgments: List[LLMJudgment] = []
        for index in range(expected):
            entry = payload[index] if index < len(payload) else None
            judgments.append(self._extract_judgment(entry))
        return judgments

    @staticmethod
    def _strip_code_fence(payload_text: str) -> str:
        """Remove Markdown code fences (```...```) which break JSON parsing."""

        if not payload_text:
            return ""

        stripped = payload_text.strip()
        if not stripped.startswith("```"):
            return stripped

        # Remove first fence line that may contain a language identifier.
        lines = stripped.splitlines()
        if len(lines) >= 2 and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        return "\n".join(lines).strip()

    @staticmethod
    def _extract_judgment(entry: object) -> LLMJudgment:
        if entry is None:
            return LLMJudgment(response="", valid_response=False, explanation="missing entry")

        explanation: str | None = None
        if isinstance(entry, str):
            answer = entry.strip()
        elif isinstance(entry, dict):
            raw_answer = entry.get("answer") or entry.get("decision")
            explanation = entry.get("explanation") or entry.get("reason")
            if raw_answer is None:
                answer = ""
            else:
                answer = str(raw_answer).strip()
        else:
            answer = str(entry).strip()

        normalized = answer.upper()
        if normalized in {"YES", "NO"}:
            return LLMJudgment(response=normalized, valid_response=True, explanation=explanation)

        return LLMJudgment(response=answer, valid_response=False, explanation=explanation)


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
        if args.advanced:
            advanced_results = advanced_search(args.query, limit=args.limit)
        else:
            simple_results = search(args.query, limit=args.limit)
    except Exception as exc:
        LOGGER.error("Search failed: %s", exc)
        raise SystemExit(1) from exc

    outputs: list[SearchOutput]
    if args.advanced:
        if not advanced_results:
            print("No matches found (advanced search)")
            return
        outputs = [SearchOutput(chunk=result.chunk, judgment=result.judgment) for result in advanced_results]
    else:
        if not simple_results:
            print("No matches found (simple search)")
            return
        outputs = [SearchOutput(chunk=result) for result in simple_results]

    for index, output in enumerate(outputs, start=1):
        print(format_result(output, index))
        print()

    if not args.to_file:
        return

    to_write = outputs
    if args.advanced:
        accepted_outputs = [
            output
            for output in outputs
            if output.judgment and output.judgment.valid_response and output.judgment.response == "YES"
        ]
        rejected_outputs = [
            output
            for output in outputs
            if output.judgment and output.judgment.valid_response and output.judgment.response == "NO"
        ]
        if accepted_outputs:
            to_write = accepted_outputs[:]
            if args.include_rejected and rejected_outputs:
                to_write += rejected_outputs
        elif rejected_outputs and args.include_rejected:
            LOGGER.warning("LLM rejected every chunk; writing only rejected results.")
            to_write = rejected_outputs
        else:
            LOGGER.warning("LLM rejected all chunks or responses invalid; writing ANN results instead.")

    try:
        path = write_results_to_file(
            to_write,
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
    print(f"Wrote {len(to_write)} chunks to {relative_path}")


if __name__ == "__main__":
    main()
