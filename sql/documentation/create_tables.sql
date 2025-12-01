CREATE SCHEMA IF NOT EXISTS wh AUTHORIZATION wh_user;

CREATE TABLE IF NOT EXISTS wh.documents (
    id                 SERIAL PRIMARY KEY,
    admin              TEXT NOT NULL,
    source_site        TEXT NOT NULL,
    content_type       TEXT NOT NULL,
    url                TEXT UNIQUE NOT NULL,

    title              TEXT,
    date_published     DATE,
    datetime_published TIMESTAMPTZ,
    location           TEXT,

    raw_html           TEXT,
    clean_text         TEXT,

    scrape_status      TEXT NOT NULL DEFAULT 'pending',
    last_error         TEXT,

    created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS wh.document_chunks (
    id           SERIAL PRIMARY KEY,
    document_id  INTEGER NOT NULL REFERENCES wh.documents(id) ON DELETE CASCADE,
    chunk_index  INTEGER NOT NULL,
    text         TEXT NOT NULL,

    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (document_id, chunk_index)
);

CREATE TABLE IF NOT EXISTS wh.table_mod_times (
    table_name    TEXT PRIMARY KEY,
    last_modified TIMESTAMPTZ NOT NULL
);
