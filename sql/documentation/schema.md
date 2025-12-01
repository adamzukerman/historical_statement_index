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

Future-ready for vectorization. Represents chunks of a document.

Key columns:

- `id` (PK)
- `document_id` – FK → `wh.documents(id)`
- `chunk_index` – 0-based order of chunks per document
- `text` – chunk of the transcript
- `created_at` / `updated_at`

Usage:

- Later, we will add an `embedding` column here.
- Each document will be split into multiple chunks for semantic search.

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
