"""Flask application that exposes a simple UI for browsing stored documents."""

from __future__ import annotations

import math

from flask import Flask, abort, jsonify, render_template, request

from ..models import DocumentDetail, DocumentRepository


PAGE_SIZE = 25


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
        )

    @app.get("/api/documents/<int:document_id>")
    def document_detail(document_id: int):
        detail = repo.get_document(document_id)
        if not detail:
            abort(404)
        return jsonify(_serialize_detail(detail))

    return app
