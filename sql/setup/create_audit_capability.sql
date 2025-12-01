CREATE TABLE IF NOT EXISTS wh.table_mod_times (
    table_name    TEXT PRIMARY KEY,
    last_modified TIMESTAMPTZ NOT NULL
);

CREATE OR REPLACE FUNCTION wh.touch_table_mod_time()
RETURNS TRIGGER AS $$
DECLARE
    full_table_name TEXT;
BEGIN
    -- Construct the full table name: schema.table
    full_table_name := TG_TABLE_SCHEMA || '.' || TG_TABLE_NAME;

    -- Insert or update the last-modified timestamp
    INSERT INTO wh.table_mod_times (table_name, last_modified)
    VALUES (full_table_name, NOW())
    ON CONFLICT (table_name)
    DO UPDATE SET last_modified = EXCLUDED.last_modified;

    -- For statement-level AFTER triggers, the return value is ignored
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

-- Attach trigger to documents and document_chunk tables
CREATE TRIGGER trg_touch_documents_modtime
AFTER INSERT OR UPDATE OR DELETE
ON wh.documents
FOR EACH STATEMENT
EXECUTE FUNCTION wh.touch_table_mod_time();

CREATE TRIGGER trg_touch_document_chunks_modtime
AFTER INSERT OR UPDATE OR DELETE
ON wh.document_chunks
FOR EACH STATEMENT
EXECUTE FUNCTION wh.touch_table_mod_time();
