# Web Interface Concept

High-level view of the lightweight browsing experience for stored transcripts.

```
┌────────────┐       HTTPS        ┌────────────────────┐      psycopg2      ┌──────────────┐
│  Browser   │◀──────────────────▶│  FastAPI/Flask app │◀──────────────────▶│ PostgreSQL DB │
│ (Alpine.js │                    │  (wh_scraper.web)  │                    │  wh.documents │
│  frontend) │───────────────────▶│  Templates + API   │───────────────────▶│  + views      │
└────────────┘   AJAX (JSON/HTML) └────────────────────┘   repository layer └──────────────┘
```

## Components

- **Browser UI**
  - Filter controls for `admin` and `scrape_status`.
  - Scrollable list of document titles (paginated).
  - Detail pane that loads `clean_text` when a title is clicked.
  - Implemented with server-rendered HTML plus a tiny Alpine.js/vanilla JS helper for dynamic updates.

- **Web application (`wh_scraper.web`)**
  - Runs inside Uvicorn/Gunicorn.
  - Exposes endpoints:
    - `GET /documents` – returns filtered list (HTML fragment or JSON).
    - `GET /documents/{id}` – returns a single document’s metadata + clean text.
  - Renders templates for initial load and responds to AJAX updates.
  - Relies on new repository helpers for list/detail queries (reusing `DocumentRepository` connections via `db.py`).

- **Database interactions**
  - Reads from `wh.documents` and supporting views such as `wh.document_status_overview`.
  - Uses existing psycopg2 connection helpers; all filtering happens via SQL (`WHERE admin = %s AND scrape_status = %s` with pagination `LIMIT/OFFSET`).

## Request Flow

1. User loads the page → server renders HTML template plus initial dataset.
2. Selecting an administration or status triggers an AJAX request to `/documents?admin=biden&status=pending`.
3. Server fetches rows via repository, returns updated list fragment.
4. Clicking a title sends `GET /documents/{id}`; response injects title metadata + `clean_text` into detail pane.

## Deployment Notes

- Deploy web app alongside existing CLI tools; it shares the same virtual environment.
- Protect with HTTP auth if exposed publicly (only read access assumed).
- Optional caching: use HTTP caching headers or a tiny in-memory cache for frequent list queries.
