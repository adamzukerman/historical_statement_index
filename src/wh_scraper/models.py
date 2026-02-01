"""Data models and repository helpers for White House transcripts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Iterable, List, Optional, Sequence

from psycopg2.extras import execute_values

from .db import get_cursor


@dataclass
class DocumentListing:
    """Represents a normalized entry discovered from the listing pages."""

    url: str
    title: Optional[str]
    date_published: Optional[date]
    admin: str = "biden"
    source_site: str = "bidenwhitehouse.archives.gov"
    content_type: str = "press_briefing"


@dataclass
class DocumentPending:
    """Represents a pending row that still needs scraping."""

    id: int
    url: str


@dataclass
class DocumentSummary:
    """Lightweight projection for listing documents."""

    id: int
    admin: str
    title: Optional[str]
    date_published: Optional[date]
    scrape_status: str


@dataclass
class DocumentDetail:
    """Full information needed to render a document page."""

    id: int
    admin: str
    title: Optional[str]
    url: str
    date_published: Optional[date]
    datetime_published: Optional[datetime]
    location: Optional[str]
    clean_text: Optional[str]
    scrape_status: str


class DocumentRepository:
    """Encapsulates reads/writes to the `wh.documents` table."""

    def upsert_listings(self, rows: Sequence[DocumentListing]) -> int:
        if not rows:
            return 0

        values = [
            (
                row.admin,
                row.source_site,
                row.content_type,
                row.url,
                row.title,
                row.date_published,
                "pending",
            )
            for row in rows
        ]

        insert_sql = """
            INSERT INTO wh.documents (
                admin,
                source_site,
                content_type,
                url,
                title,
                date_published,
                scrape_status
            ) VALUES %s
            ON CONFLICT (url) DO UPDATE SET
                title = EXCLUDED.title,
                date_published = EXCLUDED.date_published,
                updated_at = NOW();
        """

        with get_cursor(commit=True) as cur:
            execute_values(cur, insert_sql, values)

        return len(rows)

    def list_pending(self, limit: int) -> List[DocumentPending]:
        query = """
            SELECT id, url
            FROM wh.documents
            WHERE scrape_status = 'pending'
            ORDER BY id
            LIMIT %s;
        """

        with get_cursor(dict_cursor=True) as cur:
            cur.execute(query, (limit,))
            rows = cur.fetchall()

        return [DocumentPending(id=row["id"], url=row["url"]) for row in rows]

    def mark_scraped(
        self,
        *,
        document_id: int,
        title: Optional[str],
        date_published: Optional[date],
        datetime_published: Optional[datetime],
        location: Optional[str],
        raw_html: str,
        clean_text: str,
    ) -> None:
        query = """
            UPDATE wh.documents
            SET
                title = COALESCE(%s, title),
                date_published = %s,
                datetime_published = %s,
                location = %s,
                raw_html = %s,
                clean_text = %s,
                scrape_status = 'scraped',
                last_error = NULL,
                updated_at = NOW()
            WHERE id = %s;
        """

        with get_cursor(commit=True) as cur:
            cur.execute(
                query,
                (
                    title,
                    date_published,
                    datetime_published,
                    location,
                    raw_html,
                    clean_text,
                    document_id,
                ),
            )

    def mark_error(self, *, document_id: int, error: str) -> None:
        query = """
            UPDATE wh.documents
            SET
                scrape_status = 'error',
                last_error = %s,
                updated_at = NOW()
            WHERE id = %s;
        """

        with get_cursor(commit=True) as cur:
            cur.execute(query, (error[:1024], document_id))

    def list_documents(
        self,
        *,
        admin: Optional[str],
        scrape_status: Optional[str],
        limit: int,
        offset: int = 0,
    ) -> List[DocumentSummary]:
        base_query = [
            """
            SELECT id, admin, title, date_published, scrape_status
            FROM wh.documents
            """
        ]
        conditions = []
        params: List[object] = []

        if admin:
            conditions.append("admin = %s")
            params.append(admin)
        if scrape_status:
            conditions.append("scrape_status = %s")
            params.append(scrape_status)

        if conditions:
            base_query.append("WHERE " + " AND ".join(conditions))

        base_query.append("ORDER BY date_published DESC NULLS LAST, id DESC")
        base_query.append("LIMIT %s OFFSET %s")
        params.extend([limit, offset])

        query = "\n".join(base_query)

        with get_cursor(dict_cursor=True) as cur:
            cur.execute(query, params)
            rows = cur.fetchall()

        return [
            DocumentSummary(
                id=row["id"],
                admin=row["admin"],
                title=row["title"],
                date_published=row["date_published"],
                scrape_status=row["scrape_status"],
            )
            for row in rows
        ]

    def count_documents(
        self,
        *,
        admin: Optional[str],
        scrape_status: Optional[str],
    ) -> int:
        query = ["SELECT COUNT(*) FROM wh.documents"]
        conditions = []
        params: List[object] = []

        if admin:
            conditions.append("admin = %s")
            params.append(admin)
        if scrape_status:
            conditions.append("scrape_status = %s")
            params.append(scrape_status)

        if conditions:
            query.append("WHERE " + " AND ".join(conditions))

        sql_query = "\n".join(query)

        with get_cursor() as cur:
            cur.execute(sql_query, params or None)
            (total,) = cur.fetchone()

        return total

    def list_admins(self) -> List[str]:
        query = "SELECT DISTINCT admin FROM wh.documents ORDER BY admin;"
        with get_cursor() as cur:
            cur.execute(query)
            rows = cur.fetchall()
        return [row[0] for row in rows]

    def list_statuses(self) -> List[str]:
        query = "SELECT DISTINCT scrape_status FROM wh.documents ORDER BY scrape_status;"
        with get_cursor() as cur:
            cur.execute(query)
            rows = cur.fetchall()
        return [row[0] for row in rows]

    def get_document(self, document_id: int) -> Optional[DocumentDetail]:
        query = """
            SELECT
                id,
                admin,
                title,
                url,
                date_published,
                datetime_published,
                location,
                clean_text,
                scrape_status
            FROM wh.documents
            WHERE id = %s;
        """

        with get_cursor(dict_cursor=True) as cur:
            cur.execute(query, (document_id,))
            row = cur.fetchone()

        if not row:
            return None

        return DocumentDetail(
            id=row["id"],
            admin=row["admin"],
            title=row["title"],
            url=row["url"],
            date_published=row["date_published"],
            datetime_published=row["datetime_published"],
            location=row["location"],
            clean_text=row["clean_text"],
            scrape_status=row["scrape_status"],
        )
