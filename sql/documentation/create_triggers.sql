CREATE OR REPLACE FUNCTION wh.set_timestamp()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_set_timestamp_documents
BEFORE UPDATE ON wh.documents
FOR EACH ROW
EXECUTE FUNCTION wh.set_timestamp();

CREATE TRIGGER trg_set_timestamp_document_chunks
BEFORE UPDATE ON wh.document_chunks
FOR EACH ROW
EXECUTE FUNCTION wh.set_timestamp();

CREATE OR REPLACE FUNCTION wh.touch_table_mod_time()
RETURNS TRIGGER AS $$
DECLARE
    full_table_name TEXT;
BEGIN
    full_table_name := TG_TABLE_SCHEMA || '.' || TG_TABLE_NAME;

    INSERT INTO wh.table_mod_times (table_name, last_modified)
    VALUES (full_table_name, NOW())
    ON CONFLICT (table_name)
    DO UPDATE SET last_modified = EXCLUDED.last_modified;

    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_touch_documents_modtime
AFTER INSERT OR UPDATE OR DELETE ON wh.documents
FOR EACH STATEMENT
EXECUTE FUNCTION wh.touch_table_mod_time();

CREATE TRIGGER trg_touch_document_chunks_modtime
AFTER INSERT OR UPDATE OR DELETE ON wh.document_chunks
FOR EACH STATEMENT
EXECUTE FUNCTION wh.touch_table_mod_time();
