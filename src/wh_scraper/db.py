"""Database helpers for PostgreSQL access."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator, Optional

import psycopg2
from psycopg2 import sql
from psycopg2.extras import RealDictCursor

from .config import SETTINGS


def get_connection() -> psycopg2.extensions.connection:  # type: ignore[name-defined]
    """Create a new PostgreSQL connection using environment settings."""

    return psycopg2.connect(  # type: ignore[return-value]
        host=SETTINGS.db_host,
        port=SETTINGS.db_port,
        dbname=SETTINGS.db_name,
        user=SETTINGS.db_user,
        password=SETTINGS.db_password,
    )


@contextmanager
def get_cursor(
    *,
    commit: bool = False,
    dict_cursor: bool = False,
) -> Iterator[psycopg2.extensions.cursor]:  # type: ignore[name-defined]
    """Yield a cursor and manage commit/rollback semantics automatically."""

    conn = get_connection()
    cursor_factory = RealDictCursor if dict_cursor else None
    cur = conn.cursor(cursor_factory=cursor_factory)

    try:
        yield cur
        if commit:
            conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


__all__ = ["get_connection", "get_cursor", "sql"]

