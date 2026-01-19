CREATE OR REPLACE VIEW wh.document_status_overview AS
SELECT
    admin,
    scrape_status,
    COUNT(*) AS document_count
FROM wh.documents
GROUP BY admin, scrape_status
ORDER BY admin, scrape_status;
