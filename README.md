# White House Briefings Scraper

Collects and explores archived White House press briefings. The project has two entry points:

- CLI workers (`discover.py`, `scrape.py`) that fetch and store data into PostgreSQL.
- A lightweight Flask web app (`wh_scraper.web`) for filtering and reading stored transcripts.

## Running the web browser

1. Ensure dependencies are installed (`uv sync` or `pip install -e .`).
2. Export database settings or rely on the defaults in `src/wh_scraper/config.py`.
3. Start the Flask server:

   ```bash
   FLASK_APP=wh_scraper.web.app:create_app \
   FLASK_ENV=development \
   flask run --reload
   ```

   The server listens on `http://127.0.0.1:5000` by default.

4. Open the URL in a browser to filter by administration/status, scroll the title list, and load transcripts inline.

## CLI workflows

Discover listing pages:

```bash
python -m wh_scraper.discover --start-page 1 --end-page 116
```

Scrape pending documents:

```bash
python -m wh_scraper.scrape --limit 100000
```

## Semantic search workflow

1. Ensure PostgreSQL has the [`vector`](https://github.com/pgvector/pgvector) extension installed **and upgraded to ≥ 0.5** (the setup script now checks this and will raise if the version is too old).
2. Configure OpenAI access in `.env`:

   ```
   OPENAI_API_KEY=sk-...
   OPENAI_EMBEDDING_MODEL=text-embedding-3-small
   EMBEDDING_BATCH_SIZE=64
   CHUNK_MAX_TOKENS=400
   CHUNK_OVERLAP_TOKENS=40
   ```

3. Chunk scraped documents that have `clean_text` populated:

   ```bash
   python -m wh_scraper.chunk --limit 25
   ```

4. Generate embeddings for the pending chunks:

   ```bash
   python -m wh_scraper.embed --limit 200
   ```

5. Run a similarity search from the CLI:

   ```bash
   python -m wh_scraper.search "show me statements relating to Ukraine" --limit 5
   ```

   Results show chunk metadata (title, admin, date, URL) plus a snippet sorted by cosine similarity.

### Advanced search (LLM-assisted filtering)

- Optional environment variables for the relevance judge:

  ```
  OPENAI_RELEVANCE_MODEL=gpt-4o-mini
  RELEVANCE_BATCH_SIZE=5
  RELEVANCE_MAX_WORDS=350
  ```

  These default to reasonable values; override them in `.env` if needed.

- Run the CLI with `--advanced` to keep the ANN search while batching results through an LLM:

  ```bash
  python -m wh_scraper.search "white house foreign relations" --limit 10 --advanced
  ```

  Terminal output now includes each chunk’s LLM verdict (YES/NO), validity flag, and explanation.

- Combine `--advanced` and `--to-file` to produce a detailed export. The metadata header summarizes cosine scores plus LLM acceptance/rejection counts, and each section records chunk index, cosine distance, and the LLM response. Adding `--include-rejected` keeps “NO” chunks in the file, appended after the accepted ones so you can review everything.

### Monitoring chunking and embedding progress

Two helper views summarize where scraped documents sit in the chunking/embedding pipeline:

- `wh.document_chunk_activity` (per document + embedding model) lists the minimum/maximum chunk `created_at` and `updated_at` timestamps, making it obvious which scraped documents still lack chunks or haven’t been updated recently.
- `wh.document_chunk_embedding_summary` aggregates how many scraped documents have zero chunks and how many chunk rows are still missing embeddings.

Create or refresh these views via:

```bash
psql -h $DB_HOST -U $DB_USER -d $DB_NAME -f sql/setup/create_chunk_embedding_views.sql
```

(`sql/setup/create_document_status_view.sql` still provides the scrape-status overview.)
