# Database Schema Overview (wh_briefings)

## Schemas

- `wh` – primary application schema
- `public` – unused for core app tables

## Tables

### `wh.documents`

Represents one full White House transcript (press briefing, etc.).

Key columns:

- `id` (PK)
- `admin` – which administration, e.g. `'biden'`
- `source_site` – e.g. `'bidenwhitehouse.archives.gov'`
- `content_type` – e.g. `'press_briefing'`, `'statement'`, etc.
- `url` (UNIQUE) – canonical source URL
- `title` – page title
- `date_published` / `datetime_published` – when the briefing occurred
- `location` – physical location if present
- `raw_html` – full HTML fetched from the site (optional)
- `clean_text` – cleaned, plain-text transcript
- `scrape_status` – `'pending' | 'scraped' | 'error'`
- `last_error` – error message if scraping failed
- `created_at` / `updated_at` – row timestamps (trigger keeps `updated_at` fresh)

Usage:

- Each row = one transcript.
- Scraper first inserts a row with status `pending`, then later fills `clean_text` and updates status to `scraped`.

---

### `wh.document_chunks`

Represents chunks of a document plus their vector embeddings.

Key columns:

- `id` (PK)
- `document_id` – FK → `wh.documents(id)`
- `chunk_index` – 0-based order of chunks per document
- `text` – chunk of the transcript
- `embedding` – pgvector column (currently 1536 dims)
- `embedding_model` / `embedding_dimensions` – metadata about the embedding
- `embedding_updated_at` – when the vector was last refreshed
- `created_at` / `updated_at`

Usage:

- Each document is split into multiple chunks for semantic search.
- ANN index (`ivfflat`) enables fast cosine-similarity retrieval.

---

### `wh.table_mod_times`

Tracks the last time any table was modified.

Key columns:

- `table_name` – e.g. `'wh.documents'`
- `last_modified` – last write (INSERT/UPDATE/DELETE) time on that table

Populated by:

- Trigger function `wh.touch_table_mod_time()` attached to:
  - `wh.documents`
  - `wh.document_chunks`

Usage:

- Monitoring, diagnostics, or sanity checks (e.g., “Has the scraper updated anything lately?”).

---

## Views

### `wh.document_status_overview`

Shows the number of `wh.documents` rows per administration and scrape status. Helpful for spotting how many links are pending, scraped, or errored for each admin.
