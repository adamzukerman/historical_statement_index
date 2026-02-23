CREATE OR REPLACE VIEW wh.document_chunk_activity AS
WITH chunk_stats AS (
    SELECT
        c.document_id,
        c.embedding_model,
        MIN(c.created_at) AS min_chunk_created_at,
        MAX(c.created_at) AS max_chunk_created_at,
        MIN(c.updated_at) AS min_chunk_updated_at,
        MAX(c.updated_at) AS max_chunk_updated_at
    FROM wh.document_chunks c
    GROUP BY c.document_id, c.embedding_model
)
SELECT
    d.id AS document_id,
    d.title,
    cs.embedding_model,
    cs.min_chunk_created_at,
    cs.max_chunk_created_at,
    cs.min_chunk_updated_at,
    cs.max_chunk_updated_at
FROM wh.documents d
LEFT JOIN chunk_stats cs ON cs.document_id = d.id
WHERE d.scrape_status = 'scraped'
ORDER BY d.id, cs.embedding_model;

CREATE OR REPLACE VIEW wh.document_chunk_embedding_summary AS
WITH scraped_documents AS (
    SELECT id
    FROM wh.documents
    WHERE scrape_status = 'scraped'
),
document_chunk_counts AS (
    SELECT
        sd.id AS document_id,
        COUNT(c.id) AS chunk_count
    FROM scraped_documents sd
    LEFT JOIN wh.document_chunks c ON c.document_id = sd.id
    GROUP BY sd.id
),
missing_embeddings AS (
    SELECT COUNT(*) AS missing_chunks
    FROM wh.document_chunks
    WHERE embedding IS NULL
)
SELECT
    COALESCE(
        (SELECT COUNT(*) FROM document_chunk_counts WHERE chunk_count = 0),
        0
    ) AS documents_without_chunks,
    COALESCE(
        (SELECT missing_chunks FROM missing_embeddings),
        0
    ) AS chunks_without_embeddings;
