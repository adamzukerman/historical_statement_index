# Search Endpoint Contract

Defines the JSON API used by the web UI to execute semantic searches (simple or advanced) without touching CLI code.

## Route

```
POST /api/search
Content-Type: application/json
```

## Request Body

| Field             | Type                | Required | Notes |
|-------------------|---------------------|----------|-------|
| `query`           | string              | yes      | Trimmed input; 1-200 chars enforced server-side. |
| `mode`            | enum                | yes      | `"simple"` (default) or `"advanced"`. Advanced disabled if backend lacks OpenAI credentials. |
| `admin_filter`    | array of strings    | no       | Administrations to filter (e.g., `["Biden"]`). Empty or omitted = all admins. |
| `sort`            | enum                | no       | `"relevance"` (default), `"date_desc"`, or `"date_asc"`. |
| `page`            | integer             | no       | 1-indexed page number; default 1. |
| `page_size`       | integer             | no       | Defaults to 25; capped at 25 for MVP to match UI. |
| `include_rejected`| boolean             | no       | Future use; defaults to `false`. Backend may ignore if advanced verdicts unavailable. |

### Validation Rules

- Reject requests missing `query` or exceeding 200 characters.
- `mode` must be `simple` or `advanced`. If the backend has `advanced_available=false`, requests forcing `advanced` should return a 400 with an explanatory error.
- `page` ≥ 1; `page_size` must equal the fixed UI size (25) until configurability is introduced.
- Unknown admins or sort values should yield 400 errors with human-friendly messages.

## Success Response

```json
{
  "query": "national security",
  "mode": "advanced",
  "advanced_available": true,
  "filters": {
    "admin": ["Biden"],
    "sort": "relevance",
    "include_rejected": false
  },
  "pagination": {
    "page": 1,
    "page_size": 25,
    "total_results": 73,
    "total_pages": 3
  },
  "results": [
    {
      "document_id": 1234,
      "title": "Press Briefing by Press Secretary",
      "admin": "Biden",
      "publish_date": "2024-04-05",
      "source_url": "https://...",
      "cosine_score": 0.8123,
      "chunk": "...",
      "chunk_index": 2,
      "verdict": "YES",
      "verdict_reason": "Mentions national security strategy",
      "rejected": false
    }
  ],
  "metadata": {
    "query_length": 18,
    "elapsed_ms": 920
  }
}
```

### Notes

- `advanced_available` remains `true` even when `mode=simple` so the UI knows whether to enable the toggle.
- `verdict`/`verdict_reason` appear only when `mode=advanced`. Simple mode can omit them or return `null`.
- `rejected=true` rows only show up if/when the UI opts in via `include_rejected=true`. Container UI should differentiate these visually.

## Error Responses

- **400 Bad Request** — validation issues (empty query, unsupported mode, etc.).

  ```json
  {
    "error": "Query must be between 1 and 200 characters."
  }
  ```

- **503 Service Unavailable** — dependencies missing (e.g., advanced mode requested but OpenAI key not configured).
- **500 Internal Server Error** — unexpected failures. Message should be user-friendly ("Something went wrong while searching. Please try again."). UI displays these via popup and logs the detailed stack server-side.

## Logging and Telemetry

- Log query length, mode, filters, duration, and result count (but never the full query text unless diagnostics explicitly enabled).
- Emit structured metrics/counters for success vs. failure to support monitoring.

