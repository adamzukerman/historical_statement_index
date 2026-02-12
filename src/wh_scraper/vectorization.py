"""Helpers for chunking transcripts and generating embeddings."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Iterable, List, Sequence

import tiktoken
from openai import OpenAI

from .config import SETTINGS


LOGGER = logging.getLogger(__name__)


@dataclass
class EmbeddingBatch:
    """Holds a batch of embeddings."""

    model: str
    dimensions: int
    vectors: List[Sequence[float]]


class TextChunker:
    """Token-aware chunker that builds overlapping windows."""

    def __init__(
        self,
        *,
        max_tokens: int,
        overlap_tokens: int,
        encoding_name: str = "cl100k_base",
    ) -> None:
        if max_tokens <= 0:
            raise ValueError("max_tokens must be positive")
        if overlap_tokens < 0:
            raise ValueError("overlap_tokens cannot be negative")
        if overlap_tokens >= max_tokens:
            raise ValueError("overlap_tokens must be smaller than max_tokens")

        self.max_tokens = max_tokens
        self.overlap_tokens = overlap_tokens
        self.encoding = tiktoken.get_encoding(encoding_name)

    def chunk_text(self, text: str) -> List[str]:
        stripped = text.strip()
        if not stripped:
            return []

        token_ids = self.encoding.encode(stripped)
        total_tokens = len(token_ids)
        if total_tokens <= self.max_tokens:
            return [stripped]

        chunks: List[str] = []
        start = 0
        while start < total_tokens:
            end = min(start + self.max_tokens, total_tokens)
            chunk_tokens = token_ids[start:end]
            chunk_text = self.encoding.decode(chunk_tokens).strip()
            if chunk_text:
                chunks.append(chunk_text)

            if end == total_tokens:
                break

            if self.overlap_tokens:
                next_start = end - self.overlap_tokens
                if next_start >= end:
                    next_start = end
                if next_start <= start:
                    next_start = end
                start = next_start
            else:
                start = end

        return chunks


class OpenAIEmbeddingClient:
    """Thin wrapper that batches embedding requests."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str | None = None,
        batch_size: int | None = None,
    ) -> None:
        key = api_key or SETTINGS.openai_api_key
        if not key:
            raise RuntimeError("OPENAI_API_KEY is required for embedding generation")

        self.model = model or SETTINGS.openai_embedding_model
        self.batch_size = batch_size or SETTINGS.embedding_batch_size
        self.client = OpenAI(api_key=key)

    def embed_texts(self, texts: Sequence[str]) -> EmbeddingBatch:
        if not texts:
            return EmbeddingBatch(model=self.model, dimensions=0, vectors=[])

        response = self.client.embeddings.create(model=self.model, input=list(texts))
        dimensions = len(response.data[0].embedding)
        vectors = [record.embedding for record in response.data]
        return EmbeddingBatch(model=self.model, dimensions=dimensions, vectors=vectors)

    def embed_in_batches(self, texts: Sequence[str]) -> EmbeddingBatch:
        vectors: List[Sequence[float]] = []
        if not texts:
            return EmbeddingBatch(model=self.model, dimensions=0, vectors=vectors)

        dimensions = 0
        for start in range(0, len(texts), self.batch_size):
            batch = texts[start : start + self.batch_size]
            batch_result = self.embed_texts(batch)
            dimensions = batch_result.dimensions
            vectors.extend(batch_result.vectors)
            LOGGER.info("Embedded %d texts (total %d/%d)", len(batch), len(vectors), len(texts))

        return EmbeddingBatch(model=self.model, dimensions=dimensions, vectors=vectors)
