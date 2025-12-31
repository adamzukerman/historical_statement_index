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

    -- Future: embedding, model name, etc.
    -- embedding    vector(768),       -- once pgvector is installed
    -- embedding_model TEXT NOT NULL,

    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (document_id, chunk_index)
);

CREATE INDEX IF NOT EXISTS idx_document_chunks_document_id
    ON wh.document_chunks (document_id);
