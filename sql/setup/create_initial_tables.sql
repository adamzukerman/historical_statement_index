CREATE EXTENSION IF NOT EXISTS vector;

DO $$
DECLARE
    current_version TEXT;
    major INT;
    minor INT;
BEGIN
    SELECT extversion INTO current_version
    FROM pg_extension
    WHERE extname = 'vector';

    IF current_version IS NULL THEN
        RAISE EXCEPTION 'pgvector extension is required (install via your Postgres package manager)';
    END IF;

    major := split_part(current_version, '.', 1)::INT;
    minor := split_part(current_version, '.', 2)::INT;

    IF NOT (major > 0 OR (major = 0 AND minor >= 5)) THEN
        RAISE EXCEPTION
            'pgvector >= 0.5.0 is required for ivfflat indexes (found %). Run ALTER EXTENSION vector UPDATE;',
            current_version;
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS wh.documents (
    id                 SERIAL PRIMARY KEY,
    admin              TEXT NOT NULL,              -- e.g. 'biden'
    source_site        TEXT NOT NULL,              -- e.g. 'bidenwhitehouse.archives.gov'
    content_type       TEXT NOT NULL,              -- e.g. 'press_briefing'
    url                TEXT UNIQUE NOT NULL,       -- canonical article URL

    title              TEXT,
    date_published     DATE,
    datetime_published TIMESTAMPTZ,
    location           TEXT,

    raw_html           TEXT,                       -- optional, for debugging/completeness
    clean_text         TEXT,                       -- cleaned transcript

    scrape_status      TEXT NOT NULL DEFAULT 'pending',  -- 'pending' | 'scraped' | 'error'
    last_error         TEXT,

    created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Fast filtering by scrape state
CREATE INDEX IF NOT EXISTS idx_documents_scrape_status
    ON wh.documents (scrape_status);

-- Fast filtering / sorting by date
CREATE INDEX IF NOT EXISTS idx_documents_date_published
    ON wh.documents (date_published);

CREATE TABLE IF NOT EXISTS wh.document_chunks (
    id           SERIAL PRIMARY KEY,
    document_id  INTEGER NOT NULL REFERENCES wh.documents(id) ON DELETE CASCADE,
    chunk_index  INTEGER NOT NULL,     -- 0, 1, 2, ...
    text         TEXT NOT NULL,        -- the chunk of transcript text
    embedding    vector(1536),
    embedding_model TEXT,
    embedding_dimensions INTEGER,
    embedding_updated_at TIMESTAMPTZ,

    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (document_id, chunk_index)
);

ALTER TABLE wh.document_chunks
    ADD COLUMN IF NOT EXISTS embedding vector(1536);

ALTER TABLE wh.document_chunks
    ADD COLUMN IF NOT EXISTS embedding_model TEXT;

ALTER TABLE wh.document_chunks
    ADD COLUMN IF NOT EXISTS embedding_dimensions INTEGER;

ALTER TABLE wh.document_chunks
    ADD COLUMN IF NOT EXISTS embedding_updated_at TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS idx_document_chunks_document_id
    ON wh.document_chunks (document_id);

CREATE INDEX IF NOT EXISTS idx_document_chunks_embedding
    ON wh.document_chunks
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);
