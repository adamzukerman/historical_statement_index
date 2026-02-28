# White House Transcript Scraper --- Design Document

*Last updated: 2025-11-28*

------------------------------------------------------------------------

# PART A --- Engineering Design (Current Implementation)

## 1. Project Goal (Phase 1)

Build a robust, resumable scraper that collects:

-   **Administrator:** President Biden
-   **Content Type:** Press Briefings
-   **Source:**
    -   Listing root:
        `https://bidenwhitehouse.archives.gov/briefing-room/press-briefings/`
    -   Paginated URLs: `/briefing-room/press-briefings/page/{n}/` for n
        = 1..116

The scraper must:

1.  Discover + store all briefing URLs and metadata.
2.  Scrape each briefing page and extract:
    -   Title
    -   URL
    -   Date / datetime (if present)
    -   Location (if present)
    -   Full transcript text
3.  Store everything cleanly in PostgreSQL.
4.  Be idempotent and resumable with **discover** and **scrape** modes.
5.  Support semantic search via chunking, embeddings, and ANN queries backed by pgvector.

------------------------------------------------------------------------

## 2. Technologies

### Language

-   Python 3.11+

### Python Packages

-   httpx or requests\
-   beautifulsoup4 + lxml\
-   tenacity (optional)\
-   python-dotenv\
-   psycopg or psycopg2-binary\
-   tqdm / rich (optional)

### Database

-   PostgreSQL 15 or 16 with the [`vector`](https://github.com/pgvector/pgvector) extension (≥ 0.5) enabled. ANN search and cosine distance rely on ivfflat indexes provided by pgvector.

### Project Layout

    project/
      README.md
      DESIGN.md
      .env
      .env.example
      requirements.txt
      src/
        wh_scraper/
          __init__.py
          db.py
          models.py
          discover.py
          scrape.py
          utils.py
      sql/
        create_tables.sql
      logs/
        scraper.log

------------------------------------------------------------------------

## 3. Database Schema

Codex should create the following.

### Table: documents

  ----------------------------------------------------------------------------------------------
  Column                         Type                           Notes
  ------------------------------ ------------------------------ --------------------------------
  id                             SERIAL, PK                     

  admin                          TEXT NOT NULL                  "biden" (this phase)

  source_site                    TEXT NOT NULL                  "bidenwhitehouse.archives.gov"

  content_type                   TEXT NOT NULL                  "press_briefing"

  url                            TEXT UNIQUE NOT NULL           canonical article URL

  title                          TEXT                           

  date_published                 DATE                           

  datetime_published             TIMESTAMPTZ                    

  location                       TEXT                           

  raw_html                       TEXT                           

  clean_text                     TEXT                           full transcript

  scrape_status                  TEXT DEFAULT 'pending'         pending, scraped, error

  last_error                     TEXT                           

  created_at                     TIMESTAMPTZ DEFAULT now()      

  updated_at                     TIMESTAMPTZ DEFAULT now()      
  ----------------------------------------------------------------------------------------------

### Indices

-   index on scrape_status
-   index on date_published

### Additional Tables

-   `document_chunks` – stores transcript chunks plus embeddings and metadata used by the semantic-search pipeline.
-   (Future) `embedding_models` – reserved for richer metadata if we start juggling multiple embedding providers.

------------------------------------------------------------------------

## 4. Scraper Architecture

Four primary modules cover the ingest + retrieval pipeline:

------------------------------------------------------------------------

### A. discover.py --- Listing Page Crawler

**Goal:** Collect all URLs of Biden press briefings.

#### Algorithm

1.  Set `LISTING_ROOT` =
    `https://bidenwhitehouse.archives.gov/briefing-room/press-briefings/`
2.  Iterate pages 1..116 following `/page/{n}/`.
3.  For each page:
    -   GET HTML (1--2 second delay)
    -   Parse each briefing block:
        -   title
        -   relative URL
        -   date string
        -   category label ("Press Briefings")
    -   Normalize:
        -   Full URL
        -   Parse date string → DATE
    -   Insert or update the documents table (URL unique).
    -   Always set:
        -   admin='biden'
        -   source_site='bidenwhitehouse.archives.gov'
        -   content_type='press_briefing'
        -   scrape_status='pending' (only when newly discovered)
4.  Log progress.

------------------------------------------------------------------------

### B. scrape.py --- Detail Page Scraper

**Goal:** Populate full transcripts for pending URLs.

#### Algorithm

1.  SELECT rows WHERE scrape_status='pending'
2.  For each:
    -   GET article page HTML
    -   Extract:
        -   ```{=html}
            <h1>
            ```
            title

        -   Published date/datetime

        -   Location (if present)

        -   Main transcript block (paragraphs, Q&A, speakers)
    -   Normalize:
        -   Strip whitespace
        -   Join paras with blank lines
        -   Parse date/datetime
    -   UPDATE document row:
        -   raw_html
        -   clean_text
        -   date/datetime_published
        -   location
        -   scrape_status='scraped'
        -   updated_at=NOW()
3.  On error:
    -   UPDATE with scrape_status='error' + last_error
4.  1--2 second delay per request.

------------------------------------------------------------------------

### C. chunk.py --- Token-Aware Chunking

**Goal:** Split scraped transcripts into overlapping windows suitable for embeddings.

#### Algorithm

1.  Query `wh.documents` for rows that have `clean_text` but no entries in `wh.document_chunks`.
2.  Use `TextChunker` configured via `CHUNK_MAX_TOKENS` / `CHUNK_OVERLAP_TOKENS` to produce windows using the `cl100k_base` tokenizer.
3.  Insert each chunk into `wh.document_chunks (document_id, chunk_index, text)`, resetting embedding metadata so re-chunked docs will be re-embedded later.
4.  Log totals per document and exit when no pending docs remain.

------------------------------------------------------------------------

### D. embed.py --- Embedding Generation

**Goal:** Call OpenAI’s embedding API and persist vectors for chunks that are still missing embeddings.

#### Algorithm

1.  Fetch chunks where `embedding IS NULL`, honoring `--limit`.
2.  Batch texts according to `EMBEDDING_BATCH_SIZE` and call OpenAI with the configured `OPENAI_EMBEDDING_MODEL`.
3.  Update each chunk row with the embedding vector literal, model name, dimensions, and `embedding_updated_at`.
4.  Handle transient API errors defensively (log + retry later).

------------------------------------------------------------------------

### E. search.py --- Semantic & Advanced Search

**Goal:** Provide CLI-based retrieval over the stored vectors, optionally augmented with an LLM relevance judge.

#### Workflow

1.  Embed the user query via the same embedding model.
2.  Perform an ANN search using pgvector cosine distance (`embedding <=> %s`) against `wh.document_chunks`.
3.  CLI output shows ranked snippets; optional flags:
    -   `--to-file` writes metadata + full chunk text under `searches/`.
    -   `--separating-lines` / `--separating-char` control formatting.
4.  `--advanced` routes ANN hits through `LLMRelevanceJudge`, which:
    -   Batches trimmed chunk text.
    -   Calls a chat model (`OPENAI_RELEVANCE_MODEL`) with JSON-only prompts.
    -   Emits YES/NO decisions plus explanations for terminal display and file exports.

------------------------------------------------------------------------

## 5. Resumability & Modes

Codex should allow:

```
python -m wh_scraper.discover --start-page=1 --end-page=116
python -m wh_scraper.scrape --limit=100
python -m wh_scraper.chunk --limit=25
python -m wh_scraper.embed --limit=200
python -m wh_scraper.search "example query" --limit=5 [--advanced]
```

Rules:

-   discover never duplicates existing URL rows.
-   scrape only touches pending rows.
-   chunk and embed only operate on rows missing downstream artifacts so reruns are idempotent.
-   search tolerates empty databases (returns “No matches” rather than raising).
-   safe to kill and resume each stage independently.

------------------------------------------------------------------------

## 6. Configuration

Load DB settings from `.env` using python-dotenv.

    DB_HOST=localhost
    DB_PORT=5432
    DB_NAME=wh_briefings
    DB_USER=wh_user
    DB_PASSWORD=changeme

------------------------------------------------------------------------

## 7. Phase 2 – Web Search Integration

Scope adds a browser-based surface for the existing semantic search tooling while preserving all current scrape-status functionality.

- **Routes & Endpoints**
  - `GET /` continues to render the scrape-status dashboard.
  - New `GET /search` (or tab within `/`) hosts the search UI panel (see `web_interface_overview.md`).
  - `POST /api/search` provides a JSON contract for both simple and advanced searches (spec detailed in `search_endpoint.md`).
  - Existing `GET /api/documents/<id>` endpoint is reused for the detail pane regardless of entry point.
- **Backend orchestration**
  - Search endpoint delegates to the same repository/services used by the CLI (`wh_scraper.search`) so ANN queries, pgvector usage, and LLM judging stay centralized.
  - Pagination fixed at 25 per request to keep UI + API behavior aligned.
  - Administration filter and sort order are implemented server-side to maintain consistent ordering between requests.
- **Error handling**
  - Backend returns structured errors consumed by the UI popup; failures in advanced search do not impact the scrape-status route.
  - Missing OpenAI configuration disables advanced mode and surfaces an informative message via the contract (`advanced_available=false`).
- **Future hooks**
  - Placeholder bool for `include_rejected` (defaults false) so we can add rejected-chunk rendering later without breaking the contract.
  - MVP keeps detail pane chunk-only; a future enhancement may hydrate the full transcript and highlight the chunk server-side.

This section references UI/UX specifics in `web_interface_overview.md` and the request/response schema in `search_endpoint.md`.

------------------------------------------------------------------------

# PART B --- Context, Future Goals, and Notes (Not for Immediate Implementation)

Codex should NOT implement these now but must keep them in context.

------------------------------------------------------------------------

## 1. Long-Term Vision

Eventually scrape:

-   Biden
-   Trump
-   Obama
-   Current whitehouse.gov

Content types:

-   Press briefings
-   Speeches
-   Statements
-   Press gaggles
-   Official remarks

Final product: a unified time-aware semantic-searchable database of
public executive-branch communications.

------------------------------------------------------------------------

## 2. Vectorization (Current + Future Enhancements)

Already in place:

-   `document_chunks` table populated by `chunk.py`.
-   Embedding generation via OpenAI `text-embedding-3-small` (defaults configurable).
-   pgvector-powered ANN search exposed through `search.py`, including optional LLM-assisted filtering.

Future iterations may:

-   Experiment with additional embedding models (384–3072 dims) and capture metadata in a dedicated `embedding_models` table.
-   Integrate RAG-style summarization or question answering layers on top of the retrieved chunks.
-   Add background workers/queues for continuous chunk/embed refreshes rather than manual CLI runs.

------------------------------------------------------------------------

## 3. Performance Notes

-   Total pages across all sites: tens of thousands
-   Scraping dominated by network + politeness delays
-   Obama archive enforces 10-second crawl delay
-   Storage footprint modest
-   All achievable easily on a consumer laptop

------------------------------------------------------------------------

## 4. Docker Notes

Docker is optional but beneficial:

-   Postgres container restartability
-   Reproducible environment
-   Easy teardown (`docker compose down -v`)

Not to be implemented for Phase 1.

------------------------------------------------------------------------

## 5. Additional Project Context

-   User is a data scientist looking to build a research-grade dataset\
-   Goals: clarity, extensibility, correctness, clean schema\
-   Wants a modular, incremental scraping system\
-   Plans to use Codex to implement and iterate\
-   Codex should understand the history and design but only implement
    Phase 1 for now

------------------------------------------------------------------------

# END OF DESIGN DOCUMENT
