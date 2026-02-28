# Web Interface Concept

High-level view of the lightweight browsing experience for stored transcripts.

```
┌────────────┐        HTTP         ┌────────────────────┐      psycopg2      ┌──────────────┐
│  Browser   │◀───────────────────▶│  Flask app         │◀──────────────────▶│ PostgreSQL DB │
│ (vanilla   │   fetch()/HTML      │  (wh_scraper.web)  │                    │  wh.documents │
│   JS)      │────────────────────▶│  Templates + JSON  │───────────────────▶│  + views      │
└────────────┘                     └────────────────────┘   repository layer └──────────────┘
```

## Components

- **Browser UI**
  - Filter controls for `admin` and `scrape_status`.
  - Scrollable, paginated list of document titles rendered on the server.
  - Detail pane that loads `clean_text` when a title is clicked.
  - Implemented with server-rendered HTML plus a tiny vanilla-JS helper (`static/app.js`) that uses `fetch` to load details.

- **Web application (`wh_scraper.web`)**
  - Plain Flask app started via `flask run` (see README for env vars).
  - Endpoints:
    - `GET /` – renders the full page (template + filters + list) with pagination handled server-side.
    - `GET /api/documents/<id>` – returns JSON (`DocumentDetail`) used by the detail pane.
  - Reuses `DocumentRepository` for list/detail queries and pagination metadata.

- **Database interactions**
  - Reads from `wh.documents` and supporting views such as `wh.document_status_overview`.
  - Uses existing psycopg2 connection helpers; all filtering happens via SQL (`WHERE admin = %s AND scrape_status = %s` with pagination `LIMIT/OFFSET`).

## Request Flow

1. User loads `/` → server renders HTML template plus the first page of results based on any filter query params.
2. Changing filters submits the `<form>` (full reload) so pagination + totals always stay in sync with the server.
3. Clicking a title triggers `fetch(/api/documents/<id>)`; the JS helper injects the returned JSON into the detail pane and highlights the active list item.

## Deployment Notes

- Deploy the Flask app alongside the CLI tools (same virtualenv). For production, wrap it in Gunicorn/uwsgi if needed, but `flask run --reload` is enough for local use.
- Protect with HTTP auth if exposed publicly (read-only data, but DB creds live on the server).
- Optional caching: rely on PostgreSQL query cache or add a simple in-process cache for the list endpoint if latency becomes an issue.
