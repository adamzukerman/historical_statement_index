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

## Search Experience Expansion

### Goals

- Keep the existing scrape-status dashboard untouched while introducing a complementary search experience in the same Flask app.
- Let users run the existing simple or advanced semantic search workflows without leaving the browser UI.
- Maintain a familiar list + detail layout so search results feel consistent with the current document tracker.

### UX Flows

1. User switches from the default "Documents" tab to a new "Search" tab (or route). Scrape-status state is preserved so returning is instant.
2. Search form captures:
   - Query text input (hard limit: 200 characters, inline validation for empty/too-long strings).
   - Mode selector (simple vs. advanced) with contextual help about latency/cost.
   - Optional administration multi-select (default "All") and sort selector (relevance default, plus publish date asc/desc).
   - Low-priority toggle for "Include rejected chunks" (hidden/disabled until implemented).
3. Submitting the form triggers an async request to `/api/search`; a loading indicator replaces the results pane while the list remains disabled.
4. Response renders a paginated (25 rows) list showing title, administration, publish date, cosine score, snippet, and—when in advanced mode—the LLM verdict/status. Users can re-sort the list without resubmitting the query by requesting the backend with the stored query + new sort.
5. Selecting a result loads the chunk into the detail pane along with metadata and the canonical document link. The chunk is shown inline; a follow-up iteration may load the full transcript with highlighting.
6. Errors from the backend surface via a non-blocking popup with a concise message and dismiss button. Closing the popup re-enables the form so the user can continue working.

### Functional Requirements

- Query text validation: 1–200 characters; trim whitespace; show inline errors.
- Mode selector default = simple; advanced mode disabled if required env vars are missing (tooltip explains why). Switching modes reuses the same query text.
- Administration filter: multi-select or checklist pulled from known admins; default "All" (backend interprets as no filter).
- Sort options: relevance (default), publish date descending, publish date ascending. Backend enforces consistent pagination ordering.
- Pagination: fixed page size of 25. Controls mirror the existing document list UI.
- Results list displays per-item metadata plus chunk snippet. Advanced mode surfaces LLM verdict + rationale (when available). Simple mode hides those fields.
- Detail pane: shows chunk text, metadata, and "View full document" link. Full-document rendering with highlighted chunk remains out of scope for MVP.
- Rejected chunks toggle: UI placeholder noted but feature flagged off until prioritized; backend parameter defaults to `false`.
- Error handling: central popup component invoked for transport errors, validation failures, or backend exceptions. Message should be user-friendly; logs retain raw details.

### Non-Functional Requirements

- Performance: simple searches should generally respond within 1.5 seconds; advanced searches may take longer but must display progress and keep the page responsive.
- Reliability: failure in advanced mode must not impact the scrape-status dashboard; tabs/routes stay functional.
- Accessibility: ensure keyboard navigation across tabs, form controls, results, and popup dismiss action. Provide ARIA roles for the popup.
- Telemetry: log query text length (not contents), mode, filters, duration, and success/error outcome for monitoring.
- Security: continue using parameterized queries in repositories; sanitize/escape rendered text.

### Deferred / Open Items

- Full-document rendering with highlighted chunk context.
- Implementing the "Include rejected chunks" toggle and associated UI treatment.
- Pagination size configurability.
- Advanced error surfacing (stack traces, retry suggestions) beyond the simple popup message.

## Deployment Notes

- Deploy the Flask app alongside the CLI tools (same virtualenv). For production, wrap it in Gunicorn/uwsgi if needed, but `flask run --reload` is enough for local use.
- Protect with HTTP auth if exposed publicly (read-only data, but DB creds live on the server).
- Optional caching: rely on PostgreSQL query cache or add a simple in-process cache for the list endpoint if latency becomes an issue.
