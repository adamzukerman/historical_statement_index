"""Flask application that exposes UI for browsing and searching stored documents."""

from __future__ import annotations

import math
import time
from datetime import date
from typing import Sequence

from flask import Flask, abort, jsonify, render_template, request

from ..config import SETTINGS
from ..models import DocumentDetail, DocumentRepository, SearchResult
from ..search import LLMRelevanceJudge, search as semantic_search


PAGE_SIZE = 25
MAX_QUERY_LENGTH = 200
MAX_SEARCH_RESULTS = 250
ALLOWED_SORTS = {"relevance", "date_desc", "date_asc"}


def _advanced_available() -> bool:
    return bool(SETTINGS.openai_api_key)


def _sanitize_admin_filter(raw_value) -> list[str] | None:
    if raw_value is None:
        return None

    if isinstance(raw_value, str):
        candidates = [raw_value]
    elif isinstance(raw_value, Sequence):
        candidates = list(raw_value)
    else:
        raise ValueError("admin_filter must be a list of strings")

    cleaned = []
    for value in candidates:
        text = str(value).strip()
        if text and text not in cleaned:
            cleaned.append(text)
    return cleaned or None


def _sort_results(results: Sequence[SearchResult], sort_key: str) -> list[SearchResult]:
    if sort_key == "relevance":
        return list(results)

    reverse = sort_key == "date_desc"

    def sort_value(result: SearchResult) -> tuple[date, int]:
        published = result.date_published or date.min
        return (published, result.document_id)

    return sorted(results, key=sort_value, reverse=reverse)


def _similarity(distance: float) -> float:
    similarity = 1.0 - distance
    if similarity < 0:
        return 0.0
    if similarity > 1:
        return 1.0
    return similarity


def _serialize_search_result(
    result: SearchResult,
    *,
    verdict: str | None = None,
    verdict_explanation: str | None = None,
    verdict_valid: bool = False,
) -> dict:
    similarity = _similarity(result.score)
    payload = {
        "chunk_id": result.chunk_id,
        "document_id": result.document_id,
        "chunk_index": result.chunk_index,
        "title": result.title or "Untitled briefing",
        "admin": result.admin,
        "publish_date": result.date_published.isoformat() if result.date_published else None,
        "source_url": result.url,
        "chunk": result.text,
        "cosine_score": similarity,
        "verdict": verdict if verdict_valid else None,
        "verdict_reason": verdict_explanation if verdict_valid else None,
        "rejected": verdict_valid and verdict == "NO",
    }
    return payload


def _serialize_detail(detail: DocumentDetail) -> dict:
    """Convert a DocumentDetail dataclass into JSON-serializable payload."""

    return {
        "id": detail.id,
        "admin": detail.admin,
        "title": detail.title,
        "url": detail.url,
        "date_published": detail.date_published.isoformat() if detail.date_published else None,
        "datetime_published": detail.datetime_published.isoformat()
        if detail.datetime_published
        else None,
        "location": detail.location,
        "clean_text": detail.clean_text,
        "scrape_status": detail.scrape_status,
    }


def create_app() -> Flask:
    app = Flask(__name__, template_folder="templates", static_folder="static")
    repo = DocumentRepository()

    @app.get("/")
    def documents() -> str:
        admin_filter = request.args.get("admin") or None
        status_filter = request.args.get("status") or None
        page = max(int(request.args.get("page", "1") or 1), 1)
        offset = (page - 1) * PAGE_SIZE

        documents = repo.list_documents(
            admin=admin_filter,
            scrape_status=status_filter,
            limit=PAGE_SIZE,
            offset=offset,
        )
        total_count = repo.count_documents(admin=admin_filter, scrape_status=status_filter)
        total_pages = max(1, math.ceil(total_count / PAGE_SIZE)) if total_count else 1

        admins = repo.list_admins()
        statuses = repo.list_statuses()

        return render_template(
            "documents.html",
            documents=documents,
            admin_filter=admin_filter,
            status_filter=status_filter,
            admins=admins,
            statuses=statuses,
            page=page,
            total_pages=total_pages,
            total_count=total_count,
            page_size=PAGE_SIZE,
            active_tab="documents",
        )

    @app.get("/search")
    def search_page() -> str:
        admins = repo.list_admins()
        return render_template(
            "search.html",
            admins=admins,
            page_size=PAGE_SIZE,
            advanced_available=_advanced_available(),
            active_tab="search",
        )

    @app.get("/api/documents/<int:document_id>")
    def document_detail(document_id: int):
        detail = repo.get_document(document_id)
        if not detail:
            abort(404)
        return jsonify(_serialize_detail(detail))

    @app.post("/api/search")
    def api_search():
        payload = request.get_json(silent=True) or {}
        query = (payload.get("query") or "").strip()
        if not query:
            return jsonify({"error": "Query cannot be empty."}), 400
        if len(query) > MAX_QUERY_LENGTH:
            return jsonify({"error": "Query must be 200 characters or fewer."}), 400

        mode = (payload.get("mode") or "simple").lower()
        if mode not in {"simple", "advanced"}:
            return jsonify({"error": "Mode must be 'simple' or 'advanced'."}), 400

        sort = (payload.get("sort") or "relevance").lower()
        if sort not in ALLOWED_SORTS:
            return jsonify({"error": "Unsupported sort order."}), 400

        try:
            admin_filter = _sanitize_admin_filter(payload.get("admin_filter"))
        except ValueError as exc:  # pragma: no cover - validation guard
            return jsonify({"error": str(exc)}), 400

        page_size = int(payload.get("page_size") or PAGE_SIZE)
        page_size = min(max(page_size, 1), PAGE_SIZE)
        page = max(int(payload.get("page") or 1), 1)
        include_rejected = bool(payload.get("include_rejected", False))

        advanced_available = _advanced_available()
        if mode == "advanced" and not advanced_available:
            return jsonify({"error": "Advanced search is not available right now."}), 503

        start_time = time.perf_counter()
        try:
            raw_results = semantic_search(
                query,
                limit=MAX_SEARCH_RESULTS,
                admin_filter=admin_filter,
            )
        except RuntimeError as exc:
            app.logger.exception("Search unavailable: %s", exc)
            return (
                jsonify({"error": "Search is temporarily unavailable. Please try again later."}),
                503,
            )
        except Exception as exc:  # pragma: no cover - defensive logging
            app.logger.exception("Search failed: %s", exc)
            return jsonify({"error": "Something went wrong while searching. Please try again."}), 500

        sorted_results = _sort_results(raw_results, sort)
        total_results = len(sorted_results)
        total_pages = math.ceil(total_results / page_size) if total_results else 0

        if total_pages and page > total_pages:
            page = total_pages
        if page == 0:
            page = 1

        start_index = (page - 1) * page_size
        end_index = start_index + page_size
        page_items = sorted_results[start_index:end_index]

        if mode == "advanced" and page_items:
            judge = LLMRelevanceJudge()
            enriched = judge.judge(query, page_items)
            results_payload = [
                _serialize_search_result(
                    result.chunk,
                    verdict=result.judgment.response,
                    verdict_explanation=result.judgment.explanation,
                    verdict_valid=result.judgment.valid_response,
                )
                for result in enriched
            ]
        else:
            results_payload = [_serialize_search_result(result) for result in page_items]

        elapsed_ms = int((time.perf_counter() - start_time) * 1000)

        response = {
            "query": query,
            "mode": mode,
            "advanced_available": advanced_available,
            "filters": {
                "admin": admin_filter or [],
                "sort": sort,
                "include_rejected": include_rejected,
            },
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total_results": total_results,
                "total_pages": total_pages,
            },
            "results": results_payload,
            "metadata": {"query_length": len(query), "elapsed_ms": elapsed_ms},
        }
        return jsonify(response)

    return app
