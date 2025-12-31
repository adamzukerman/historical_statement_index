# White House Transcript Scraper --- Design Document

*Last updated: 2025-11-28*

------------------------------------------------------------------------

# PART A --- Immediate Engineering Design (Implement This Now)

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
5.  Prepare for later vectorization but NOT implement vectorization now.

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

-   PostgreSQL 15 or 16

No pgvector needed yet.

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

### Future Tables (DO NOT CREATE YET)

-   document_chunks
-   embedding_models

------------------------------------------------------------------------

## 4. Scraper Architecture

Two modules:

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

## 5. Resumability & Modes

Codex should allow:

    python -m wh_scraper.discover
    python -m wh_scraper.scrape --limit=100

Rules:

-   discover never duplicates existing URL rows
-   scrape only touches pending rows
-   safe to kill and resume

------------------------------------------------------------------------

## 6. Configuration

Load DB settings from `.env` using python-dotenv.

    DB_HOST=localhost
    DB_PORT=5432
    DB_NAME=wh_briefings
    DB_USER=wh_user
    DB_PASSWORD=changeme

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

## 2. Vectorization (Later Phase)

Future work will:

-   Add document_chunks table
-   Chunk transcripts (300--500 tokens)
-   Compute embeddings using a smaller model (384--768 dims)
-   Store embeddings via pgvector or external vector DB

Query pipeline:

1.  Embed user query
2.  ANN search on embeddings
3.  Return ranked snippets with dates
4.  Build UI or CLI interface for historical lookup

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
